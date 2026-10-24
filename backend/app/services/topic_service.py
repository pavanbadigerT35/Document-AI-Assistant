import re
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import READY, Document, Topic
from app.services.pdf_service import Heading
from app.services.vector_store import StoredChunk, VectorStore


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
_DURATION_RE = re.compile(r"\s+[\u2013\u2014\-�]\s+\d+\s*(?:hours?|hrs?|days?|weeks?)\s*$", re.I)
_TITLE_NOISE_RE = re.compile(r"\s*[\u2013\u2014\-:]?\s*(?:complete\s+)?study\s+notes\s*$", re.I)
_PREFIX_NOISE_RE = re.compile(r"^(?:introduction|overview|fundamentals|basics)\s+(?:to|of)\s+", re.I)
_WORDS_RE = re.compile(r"[a-z0-9]+", re.I)
_TRAILING_INCOMPLETE_RE = re.compile(r"\b(?:and|or|of|to|with|for|in|on|by|from|the|a|an)$", re.I)
_GENERIC_HEADINGS = {
    "abstract", "acknowledgements", "chapter", "contents", "conclusion",
    "references", "bibliography", "appendix", "index", "summary", "section",
    "unit", "module", "part", "study notes", "complete study notes",
}
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in",
    "into", "is", "of", "on", "or", "the", "to", "what", "when", "where",
    "which", "with",
}


def topic_label(title: str) -> str:
    """Remove common numbering, course prefixes, and extraction noise from a heading."""
    label = _TITLE_NOISE_RE.sub("", _DURATION_RE.sub("", title))
    label = re.sub(r"[�\ufffd]+", " ", label).strip()
    label = _NUMBER_RE.sub("", _PREFIX_RE.sub("", label)).strip(" \t:.-")
    label = _PREFIX_NOISE_RE.sub("", label).strip()
    return re.sub(r"\s+", " ", label)


def _heading_words(title: str) -> set[str]:
    return {word.casefold() for word in _WORDS_RE.findall(title) if word.casefold() not in _STOP_WORDS}


def _valid_heading(title: str) -> str | None:
    label = topic_label(title)
    words = _WORDS_RE.findall(label)
    if (
        len(label) < 3
        or label.casefold() in _GENERIC_HEADINGS
        or _TRAILING_INCOMPLETE_RE.search(label)
        or len(words) > 12
        or not _heading_words(label)
    ):
        return None
    return label


def _section_content(topic: Topic, page_chunks: list[StoredChunk]) -> str | None:
    label = _valid_heading(topic.title)
    if not label:
        return None
    title_words = _heading_words(label)
    matching: list[str] = []
    for chunk in page_chunks:
        if chunk.page != topic.page:
            continue
        text_words = _heading_words(chunk.text)
        if title_words.issubset(text_words):
            matching.append(chunk.text)
    if not matching:
        return None
    content = re.sub(r"\s+", " ", " ".join(matching)).strip()
    content = re.sub(r"(?<!\w)" + re.escape(label) + r"(?!\w)", " ", content, flags=re.I)
    if len(content) < 60 or len(_WORDS_RE.findall(content)) < 10:
        return None
    return re.sub(r"\s+", " ", content).strip()


def _question_for(label: str, content: str) -> tuple[str, str] | None:
    """Return one question only when the section contains cues that can answer it."""
    lower = content.casefold()
    phrase = label[:1].lower() + label[1:]
    if re.match(r"^how\s+", label, re.I):
        return f"What does the document explain about {phrase}?", "process"
    if re.match(r"^elements of (?:a|an|the)\s+", label, re.I):
        return f"What are the main {phrase}?", "components"
    rise = re.match(r"^(?:the\s+)?rise of\s+(.+)$", label, re.I)
    if rise:
        subject = rise.group(1)
        return f"What does the document say about the rise of {subject}?", "concept"
    if re.search(r"\b(?:steps?|first|then|finally)\b", lower):
        return f"How does {label} work, and what are its main steps?", "process"
    if re.search(r"\b(?:process|workflow|pipeline|algorithm|converts?|transforms?|produces?|generates?|schedules?)\b", lower):
        return f"How does {label} work?", "process"
    if re.search(r"\b(?:compared? with|versus|vs\.?|difference between|differ from)\b", lower):
        return f"What differences does the document describe for {label}?", "comparison"
    if re.search(r"\b(?:for example|examples?|such as|applications?)\b", lower):
        return f"What applications or examples of {label} does the document describe?", "examples"
    if re.search(r"\b(?:components?|principles?|properties|characteristics|consists of|comprises|includes)\b", lower):
        return f"What are the key components or principles of {label}?", "components"
    if re.search(r"\b(?:refers? to|defined as|means)\b", lower):
        return f"What does {label} mean, and how is it defined here?", "concept"
    if re.search(r"\b(?:helps?|allows?|enables?|used to)\b", lower):
        return f"What does {label} help accomplish?", "application"
    if re.search(r"\b(?:is|are)\b", lower):
        return f"What is {label}, and what role does it play?", "concept"
    return None


def _similar_topics(left: str, right: str) -> bool:
    a, b = _heading_words(left), _heading_words(right)
    return bool(a and b) and len(a & b) / min(len(a), len(b)) >= 0.8


def suggest_questions(
    db: Session,
    store: VectorStore,
    document_ids: list[str] | None,
    limit: int,
) -> list[dict]:
    """Build grounded, deterministic suggestions from stored headings and page chunks."""
    groups = list_topics(db, document_ids)
    chunks_by_document: dict[str, list[StoredChunk]] = defaultdict(list)
    for chunk in store.get_document_chunks([doc.id for doc, _ in groups]):
        chunks_by_document[chunk.document_id].append(chunk)

    per_doc: list[list[dict]] = []
    for doc, topics in groups:
        items: list[dict] = []
        for topic in topics:
            label = _valid_heading(topic.title)
            if not label:
                continue
            content = _section_content(topic, chunks_by_document[doc.id])
            if not content:
                continue
            question_intent = _question_for(label, content)
            if not question_intent:
                continue
            question, intent = question_intent
            if any(_similar_topics(label, item["topic"]) for item in items):
                continue
            items.append({
                "question": question,
                "document_id": doc.id,
                "filename": doc.filename,
                "page": topic.page,
                "topic": label,
                "intent": intent,
            })
        per_doc.append(items)

    out: list[dict] = []
    seen_topics: list[str] = []
    seen_intents: set[str] = set()
    for rank in range(max((len(p) for p in per_doc), default=0)):
        for items in per_doc:
            if rank >= len(items) or len(out) >= min(limit, 6):
                continue
            item = items[rank]
            if any(_similar_topics(item["topic"], prior) for prior in seen_topics):
                continue
            if item["intent"] in seen_intents and len(out) >= 3:
                continue
            seen_topics.append(item["topic"])
            seen_intents.add(item["intent"])
            out.append({key: value for key, value in item.items() if key not in {"topic", "intent"}})
    return out
