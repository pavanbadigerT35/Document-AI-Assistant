"""Page-aware chunking: a chunk never spans two pages, so its page number is always exact."""
import re
from dataclasses import dataclass

from app.services.pdf_service import PageText


@dataclass
class Chunk:
    index: int
    page: int
    text: str


def _normalise(text: str) -> str:
    text = text.replace("\r", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _split_long(unit: str, size: int) -> list[str]:
    pieces: list[str] = []
    while len(unit) > size:
        cut = unit.rfind(" ", 0, size)
        cut = cut if cut > size // 2 else size
        pieces.append(unit[:cut].strip())
        unit = unit[cut:].strip()
    if unit:
        pieces.append(unit)
    return pieces


def _overlap_tail(text: str, overlap: int) -> str:
    if overlap <= 0 or len(text) <= overlap:
        return text if overlap > 0 else ""
    tail = text[-overlap:]
    first_space = tail.find(" ")
    return tail[first_space + 1 :] if 0 <= first_space < len(tail) - 1 else tail


def chunk_page(text: str, size: int, overlap: int) -> list[str]:
    text = _normalise(text)
    if not text:
        return []
    if len(text) <= size:
        return [text]
    units: list[str] = []
    for line in text.split("\n"):
        units.extend(_split_long(line, size) if len(line) > size else [line])
    chunks: list[str] = []
    buf = ""
    for unit in units:
        candidate = f"{buf}\n{unit}" if buf else unit
        if len(candidate) <= size:
            buf = candidate
            continue
        if buf:
            chunks.append(buf)
            tail = _overlap_tail(buf, overlap)
            buf = f"{tail}\n{unit}" if tail and len(tail) + 1 + len(unit) <= size else unit
        else:
            buf = unit
    if buf:
        chunks.append(buf)
    return chunks


def chunk_pages(pages: list[PageText], size: int, overlap: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        for piece in chunk_page(page.text, size, overlap):
            chunks.append(Chunk(index=len(chunks), page=page.page_number, text=piece))
    return chunks
