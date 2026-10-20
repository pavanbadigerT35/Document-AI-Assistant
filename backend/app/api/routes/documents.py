import hashlib
import logging
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_db
from app.api.errors import AppError, request_id
from app.core.container import Container
from app.db.models import FAILED, READY, Activity, Document
from app.schemas.documents import ActivityOut, DocumentOut, StatsOut, UploadResponse, UploadResult
from app.services.ingestion_service import ingest_document

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["documents"])
ALLOWED_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream", "", None}


def _safe_display_name(name: str | None) -> str:
    base = re.split(r"[\\/]", name or "document.pdf")[-1]
    base = re.sub(r"[\x00-\x1f]", "", base).strip()
    return (base or "document.pdf")[:255]


async def _save(upload: UploadFile, dest: Path, limit: int) -> tuple[str, int]:
    sha, size, first = hashlib.sha256(), 0, True
    with dest.open("wb") as out:
        while chunk := await upload.read(1024 * 1024):
            if first:
                if not chunk.startswith(b"%PDF-"):
                    raise ValueError("The file content is not a PDF.")
                first = False
            size += len(chunk)
            if size > limit:
                raise ValueError(f"The file is larger than the {limit // (1024 * 1024)} MB limit.")
            sha.update(chunk)
            out.write(chunk)
    if size == 0:
        raise ValueError("The file is empty.")
    return sha.hexdigest(), size


def _process(c: Container, doc_id: str, path: Path) -> Document:
    with c.session_factory() as db:
        doc = db.get(Document, doc_id)
        return ingest_document(c, db, doc, path)


@router.post("/documents", response_model=UploadResponse)
async def upload_documents(request: Request, response: Response, files: list[UploadFile] = File(...), c: Container = Depends(get_container)):
    if len(files) > c.settings.max_files_per_request:
        raise AppError(413, "too_many_files", f"Upload at most {c.settings.max_files_per_request} files at a time.")
    results: list[UploadResult] = []
    for up in files:
        name = _safe_display_name(up.filename)
        if not name.lower().endswith(".pdf"):
            results.append(UploadResult(filename=name, outcome="rejected", message="Only .pdf files are accepted."))
            continue
        if up.content_type not in ALLOWED_TYPES:
            results.append(UploadResult(filename=name, outcome="rejected", message=f"Unexpected content type '{up.content_type}'."))
            continue
        stored_name = f"{uuid.uuid4().hex}.pdf"  # internal name; the uploaded filename never touches the filesystem
        dest = c.settings.upload_dir / stored_name
        try:
            digest, size = await _save(up, dest, c.settings.max_upload_bytes)
        except ValueError as exc:
            dest.unlink(missing_ok=True)
            results.append(UploadResult(filename=name, outcome="rejected", message=str(exc)))
            continue

        with c.session_factory() as db:
            existing = db.query(Document).filter(Document.file_hash == digest).one_or_none()
            if existing and existing.status == READY:
                dest.unlink(missing_ok=True)
                results.append(UploadResult(filename=name, outcome="duplicate", message=f"Already indexed as '{existing.filename}'. Nothing was added.", document=DocumentOut.model_validate(existing)))
                continue
            if existing:  # earlier attempt failed or was interrupted: retry on the same record
                (c.settings.upload_dir / existing.stored_name).unlink(missing_ok=True)
                existing.stored_name, existing.filename, existing.size_bytes = stored_name, name, size
                doc_id = existing.id
            else:
                doc_id = str(uuid.uuid4())
                db.add(Document(id=doc_id, filename=name, stored_name=stored_name, file_hash=digest, size_bytes=size))
            db.commit()
        doc = await run_in_threadpool(_process, c, doc_id, dest)
        outcome = "created" if doc.status == READY else "failed"
        message = "Uploaded and indexed." if doc.status == READY else (doc.error_message or "Indexing failed.")
        results.append(UploadResult(filename=name, outcome=outcome, message=message, document=DocumentOut.model_validate(doc)))

    outcomes = {r.outcome for r in results}
    response.status_code = 201 if "created" in outcomes else 200 if outcomes == {"duplicate"} else 400
    return UploadResponse(results=results, request_id=request_id(request))


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)):
    return db.query(Document).order_by(Document.uploaded_at.desc()).all()


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise AppError(404, "document_not_found", "Document not found.")
    return doc


@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    doc = db.get(Document, document_id)
    if not doc:
        raise AppError(404, "document_not_found", "Document not found.")
    # Order matters: vectors first. If this fails the DB row stays, so the user can retry and nothing is orphaned.
    try:
        c.store.delete_document(doc.id)
        if c.store.count(doc.id) != 0:
            raise RuntimeError("chunks remain after delete")
    except Exception:
        log.exception("Vector delete failed for %s", doc.id)
        raise AppError(500, "delete_failed", "Could not remove the document's indexed content. Nothing was deleted; try again.")
    (c.settings.upload_dir / doc.stored_name).unlink(missing_ok=True)
    db.add(Activity(kind="delete", message=f"Deleted {doc.filename}"))
    db.delete(doc)
    db.commit()
    return Response(status_code=204)


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db), c: Container = Depends(get_container)):
    ready = db.query(Document).filter(Document.status == READY)
    pages, chunks = db.query(func.coalesce(func.sum(Document.page_count), 0), func.coalesce(func.sum(Document.chunk_count), 0)).filter(Document.status == READY).one()
    return StatsOut(
        total_documents=db.query(Document).count(),
        ready_documents=ready.count(),
        failed_documents=db.query(Document).filter(Document.status == FAILED).count(),
        total_pages=int(pages),
        total_chunks=int(chunks),
        recent_documents=[DocumentOut.model_validate(d) for d in db.query(Document).order_by(Document.uploaded_at.desc()).limit(5)],
        recent_activity=[ActivityOut.model_validate(a) for a in db.query(Activity).order_by(Activity.id.desc()).limit(8)],
        llm_configured=c.llm.configured,
    )
