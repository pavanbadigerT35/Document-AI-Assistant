import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import READY, Document, Topic
from app.services.pdf_service import Heading


def save_topics(db: Session, document_id: str, headings: list[Heading]) -> None:
    db.query(Topic).filter(Topic.document_id == document_id).delete()
    for pos, h in enumerate(headings):
        db.add(Topic(document_id=document_id, title=h.title[:300], page=h.page, level=h.level, position=pos))


def list_topics(db: Session, document_ids: list[str] | None = None) -> list[tuple[Document, list[Topic]]]:
    stmt = select(Document).where(Document.status == READY).order_by(Document.uploaded_at.desc())
    if document_ids:
        stmt = stmt.where(Document.id.in_(document_ids))
    out = []
    for doc in db.scalars(stmt):
        topics = sorted(doc.topics, key=lambda t: t.position)
        out.append((doc, topics))
    return out


_PREFIX_RE = re.compile(r"^(?:Module|Chapter|Unit|Section|Part)\s+\d+\s*[:\-\u2013]\s*", re.I)
_NUMBER_RE = re.compile(r"^(?:\d+(?:\.\d+)+[.)]?|\d+[.)])\s+")  # "1.2 ", "1. ", "3) " but not "2024 Roadmap"
_DURATION_RE = re.compile(r"\s+[\u2013\-]\s+\d+\s*(?:hours?|hrs?|days?|weeks?)\s*$", re.I)


def topic_label(title: str) -> str:
    """'Module 1: Prompt Engineering for QA \u2013 4 Hours' -> 'Prompt Engineering for QA'; '1.2 Anatomy' -> 'Anatomy'."""
    label = _DURATION_RE.sub("", _NUMBER_RE.sub("", _PREFIX_RE.sub("", title.strip()))).strip()
    return label or title.strip()


def suggest_questions(db: Session, document_ids: list[str] | None, limit: int) -> list[dict]:
    """Questions built from REAL headings found in the indexed documents (template-based, not LLM).

    Documents take turns, so with several PDFs the suggestions are not all from the newest one.
    """
    per_doc: list[list[dict]] = []
    for doc, topics in list_topics(db, document_ids):
        pool = [t for t in topics if t.level <= 2] or topics
        items, seen = [], set()
        for t in pool:
            label = topic_label(t.title)
            if label.lower() in seen:
                continue
            seen.add(label.lower())
            items.append({"question": f"What does the document cover about {label}?", "document_id": doc.id, "filename": doc.filename, "page": t.page})
        per_doc.append(items)
    out: list[dict] = []
    for rank in range(max((len(p) for p in per_doc), default=0)):
        for items in per_doc:
            if rank < len(items) and len(out) < limit:
                out.append(items[rank])
    return out
