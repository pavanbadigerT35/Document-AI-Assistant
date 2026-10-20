from typing import Iterator

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.errors import AppError
from app.core.container import Container
from app.db.models import READY, Document


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_db(c: Container = Depends(get_container)) -> Iterator[Session]:
    with c.session_factory() as db:
        yield db


def resolve_scope(db: Session, document_ids: list[str] | None) -> list[str] | None:
    """Validate the requested documents. None means 'all Ready documents'."""
    ready = {d for (d,) in db.query(Document.id).filter(Document.status == READY)}
    if document_ids is None:
        if not ready:
            raise AppError(409, "no_ready_documents", "No documents are indexed yet. Upload a PDF first.")
        return None
    unknown = [d for d in document_ids if d not in ready]
    if unknown:
        raise AppError(404, "document_not_found", "One or more selected documents do not exist or are not ready.")
    return list(dict.fromkeys(document_ids))
