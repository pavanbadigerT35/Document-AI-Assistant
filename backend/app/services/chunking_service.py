"""Deterministic page-aware chunking with sentence boundaries and optional extracted headings."""
import math
import re
from dataclasses import dataclass
from typing import Callable

from app.services.pdf_service import Heading, PageText

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)
TokenCounter = Callable[[str], int]
TextSplitter = Callable[[str, int], list[str]]


@dataclass
class Chunk:
    index: int
    page: int
    text: str


@dataclass
class _Unit:
    text: str
    separator: str


def _normalise(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _token_cost(token: str) -> int:
    if token.isalnum() or "_" in token:
        return max(1, math.ceil(len(token) / 4))
    return 1


def estimate_tokens(text: str) -> int:
    """Approximate tokens only; production ingestion uses the embedding model tokenizer."""
    return sum(_token_cost(match.group()) for match in _TOKEN_RE.finditer(text))


def _split_long(text: str, size: int) -> list[str]:
    if size < 1:
        raise ValueError("chunk size must be at least one token")
    pieces: list[str] = []
    current: list[str] = []
    cost = 0
    for atom in re.findall(r"\S+", text):
        atom_cost = estimate_tokens(atom)
        if atom_cost > size:
            if current:
                pieces.append(" ".join(current))
                current, cost = [], 0
            matches = list(_TOKEN_RE.finditer(atom))
            fragment = ""
            fragment_cost = 0
            for match in matches:
                token = match.group()
                token_cost = _token_cost(token)
                if token_cost > size:
                    if fragment:
                        pieces.append(fragment)
                        fragment, fragment_cost = "", 0
                    width = max(1, size * 4)
                    pieces.extend(token[i : i + width] for i in range(0, len(token), width))
                    continue
                if fragment and fragment_cost + token_cost > size:
                    pieces.append(fragment)
                    fragment, fragment_cost = "", 0
                fragment += token
                fragment_cost += token_cost
            if fragment:
                pieces.append(fragment)
            continue
        if current and cost + atom_cost > size:
            pieces.append(" ".join(current))
            current, cost = [], 0
        current.append(atom)
        cost += atom_cost
    if current:
        pieces.append(" ".join(current))
    return [piece for piece in pieces if piece]


def _page_sections(text: str, headings: set[str]) -> list[tuple[str | None, list[str]]]:
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    paragraphs: list[str] = []
    lines: list[str] = []

    def flush_paragraph() -> None:
        paragraph = " ".join(part.strip() for part in lines if part.strip()).strip()
        if paragraph:
            paragraphs.append(paragraph)
        lines.clear()

    def flush_section() -> None:
        flush_paragraph()
        if current_heading is not None or paragraphs:
            sections.append((current_heading, paragraphs.copy()))
        paragraphs.clear()

    for line in _normalise(text).split("\n"):
        normalized = line.strip().rstrip(":").strip().casefold()
        if normalized and normalized in headings:
            flush_section()
            current_heading = line.strip()
        elif line.strip():
            lines.append(line)
        else:
            flush_paragraph()
    flush_section()
    return sections


def _render(units: list[_Unit], heading: str | None) -> str:
    body = "".join((unit.separator if i else "") + unit.text for i, unit in enumerate(units))
    return f"{heading}\n\n{body}" if heading and body else heading or body


def _sentence_units(
    paragraph: str,
    heading: str | None,
    max_size: int,
    overlap: int,
    token_counter: TokenCounter,
    text_splitter: TextSplitter,
) -> list[_Unit]:
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", paragraph) if part.strip()]
    units: list[_Unit] = []
    for sentence in sentences:
        separator = "\n\n" if not units else " "
        unit_limit = max(1, max_size - overlap)
        if token_counter(_render([_Unit(sentence, separator)], heading)) <= unit_limit:
            units.append(_Unit(sentence, separator))
            continue

        prefix_cost = token_counter(f"{heading}\n\n") if heading else token_counter("")
        budget = max(1, unit_limit - prefix_cost)
        pieces = text_splitter(sentence, budget)
        while any(token_counter(_render([_Unit(piece, separator)], heading)) > max_size for piece in pieces):
            budget -= 1
            if budget < 1:
                raise ValueError("Unable to split a sentence within the embedding model token limit")
            pieces = text_splitter(sentence, budget)
        for index, piece in enumerate(pieces):
            units.append(_Unit(piece, separator if index == 0 else " "))
    return units


def _overlap_suffix(
    units: list[_Unit], overlap: int, token_counter: TokenCounter, text_splitter: TextSplitter
) -> list[_Unit]:
    suffix: list[_Unit] = []
    total = 0
    for unit in reversed(units):
        cost = token_counter(unit.text)
        remaining = overlap - total
        if cost <= remaining:
            suffix.insert(0, unit)
            total += cost
            continue
        available = remaining - token_counter("")
        if available >= 2:
            pieces = text_splitter(unit.text, available)
            if pieces and token_counter(pieces[-1]) <= remaining:
                suffix.insert(0, _Unit(pieces[-1], " "))
        if total + cost > overlap:
            break
    return suffix


def _chunk_section(
    paragraphs: list[str],
    heading: str | None,
    size: int,
    max_size: int,
    overlap: int,
    token_counter: TokenCounter,
    text_splitter: TextSplitter,
) -> list[str]:
    units = [
        unit
        for paragraph in paragraphs
        for unit in _sentence_units(paragraph, heading, max_size, overlap, token_counter, text_splitter)
    ]
    if not units:
        return [heading] if heading else []

    chunks: list[str] = []
    current: list[_Unit] = []
    current_is_overlap = False
    for unit in units:
        candidate = current + [unit]
        candidate_text = _render(candidate, heading)
        if current_is_overlap:
            if token_counter(candidate_text) <= max_size:
                current = candidate
                current_is_overlap = False
                continue
            chunks.append(_render(current, heading))
            current = _overlap_suffix(current, overlap, token_counter, text_splitter)
            candidate = current + [unit]
            while current and token_counter(_render(candidate, heading)) > max_size:
                current.pop(0)
                candidate = current + [unit]
            current_is_overlap = bool(current)
            current = candidate
            continue
        if current and token_counter(candidate_text) > size:
            if token_counter(candidate_text) <= max_size and token_counter(unit.text) < max(1, size // 4):
                current = candidate
                continue
            chunks.append(_render(current, heading))
            current = _overlap_suffix(current, overlap, token_counter, text_splitter)
            candidate = current + [unit]
            while current and token_counter(_render(candidate, heading)) > max_size:
                current.pop(0)
                candidate = current + [unit]
            current_is_overlap = bool(current)

        if token_counter(_render(candidate, heading)) > max_size:
            if current:
                chunks.append(_render(current, heading))
            current = [unit]
            current_is_overlap = False
        else:
            current = candidate

    if current:
        final = _render(current, heading)
        if not chunks or final != chunks[-1]:
            chunks.append(final)
    return chunks


def chunk_page(
    text: str,
    size: int,
    overlap: int,
    *,
    max_size: int | None = None,
    headings: list[str] | None = None,
    token_counter: TokenCounter = estimate_tokens,
    text_splitter: TextSplitter = _split_long,
) -> list[str]:
    """Chunk one page; the supplied token counter includes any model special tokens."""
    max_size = size if max_size is None else max_size
    if size < 1 or max_size < size or overlap < 0 or overlap >= max_size:
        raise ValueError("chunk limits must satisfy 1 <= target <= maximum and 0 <= overlap < maximum")
    normalized = _normalise(text)
    if not normalized:
        return []
    heading_set = {
        _normalise(title).rstrip(":").strip().casefold()
        for title in (headings or [])
        if _normalise(title)
    }
    sections = _page_sections(normalized, heading_set)
    chunks: list[str] = []
    for heading, paragraphs in sections:
        chunks.extend(
            _chunk_section(paragraphs, heading, size, max_size, overlap, token_counter, text_splitter)
        )
    return chunks


def chunk_pages(
    pages: list[PageText],
    size: int,
    overlap: int,
    *,
    max_size: int | None = None,
    headings: list[Heading] | None = None,
    token_counter: TokenCounter = estimate_tokens,
    text_splitter: TextSplitter = _split_long,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        page_headings = [h.title for h in (headings or []) if h.page == page.page_number]
        for piece in chunk_page(
            page.text,
            size,
            overlap,
            max_size=max_size,
            headings=page_headings,
            token_counter=token_counter,
            text_splitter=text_splitter,
        ):
            chunks.append(Chunk(index=len(chunks), page=page.page_number, text=piece))
    return chunks
