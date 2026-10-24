"""Upload -> extract -> chunk -> embed -> store. Safe to re-run for the same document."""
import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.container import Container
from app.db.models import FAILED, PROCESSING, READY, Activity, Document
from app.services.chunking_service import chunk_pages
from app.services.pdf_service import PDFExtractionError, extract_pdf, looks_scanned
from app.services.topic_service import save_topics

log = logging.getLogger(__name__)
EMBED_BATCH = 64


def ingest_document(c: Container, db: Session, doc: Document, path: Path) -> Document:
    doc.status, doc.error_message = PROCESSING, None
    db.commit()
    try:
        extracted = extract_pdf(path)
        doc.page_count, doc.char_count = extracted.page_count, extracted.char_count
        if extracted.page_count == 0:
            raise PDFExtractionError("The PDF has no pages.")
        if looks_scanned(extracted):
            raise PDFExtractionError(
                "No selectable text was found. This looks like a scanned PDF; OCR is not implemented in this version."
            )
        model_limit = c.embedder.max_input_tokens
        max_tokens = min(c.settings.chunk_max_tokens, model_limit) if model_limit is not None else c.settings.chunk_max_tokens
        target_tokens = min(c.settings.chunk_target_tokens, max_tokens)
        chunks = chunk_pages(
            extracted.pages,
            target_tokens,
            c.settings.chunk_overlap_tokens,
            max_size=max_tokens,
            headings=extracted.headings,
            token_counter=c.embedder.token_count,
            text_splitter=c.embedder.split_text,
        )
        embeddings: list[list[float]] = []
        for i in range(0, len(chunks), EMBED_BATCH):
            embeddings.extend(c.embedder.embed([ch.text for ch in chunks[i : i + EMBED_BATCH]]))
        c.store.add_chunks(doc.id, doc.filename, chunks, embeddings)
        save_topics(db, doc.id, extracted.headings)
        doc.chunk_count, doc.embedding_model, doc.status = len(chunks), c.embedder.name, READY
        db.add(Activity(kind="upload", message=f"Indexed {doc.filename} ({extracted.page_count} pages, {len(chunks)} chunks)"))
    except PDFExtractionError as exc:
        _fail(c, db, doc, str(exc))
    except Exception:  # embedding model download problems, chroma errors, ...
        log.exception("Ingestion failed for %s", doc.id)
        _fail(c, db, doc, "Indexing failed. Check the backend log (often the embedding model could not be downloaded).")
    db.commit()
    return doc


def _fail(c: Container, db: Session, doc: Document, message: str) -> None:
    try:
        c.store.delete_document(doc.id)  # never leave partial chunks behind
    except Exception:
        log.exception("Cleanup of partial chunks failed for %s", doc.id)
    doc.status, doc.error_message, doc.chunk_count = FAILED, message, 0
    db.add(Activity(kind="failed", message=f"Could not index {doc.filename}: {message}"[:400]))
