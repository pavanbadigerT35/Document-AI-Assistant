"""PDF text and heading extraction with PyMuPDF. Page numbers are 1-based and match the PDF."""
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pymupdf


class PDFExtractionError(Exception):
    """Raised with a user-safe message when a PDF cannot be read."""


@dataclass
class PageText:
    page_number: int
    text: str


@dataclass
class Heading:
    title: str
    page: int
    level: int  # 1 = module/section, 2 = sub-section, 3 = minor


@dataclass
class ExtractedPDF:
    page_count: int
    pages: list[PageText]
    headings: list[Heading]

    @property
    def char_count(self) -> int:
        return sum(len(p.text.strip()) for p in self.pages)


_BULLETS = ("●", "○", "•", "▪", "-", "*", "–", "■")
_MODULE_RE = re.compile(r"^(Module|Chapter|Unit|Section|Part)\s+\d+\s*[:\-–]\s*\S", re.I)
_NUMBERED_RE = re.compile(r"^(\d+(?:\.\d+)+)[.)]?\s+\S")


def _is_bold(span: dict) -> bool:
    return bool(span.get("flags", 0) & 16) or "bold" in span.get("font", "").lower()


def _table_boxes(page) -> list[tuple]:
    try:
        return [t.bbox for t in page.find_tables().tables]
    except Exception:  # table detection is best-effort only
        return []


def _inside(box: tuple, bbox: tuple) -> bool:
    cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
    return box[0] <= cx <= box[2] and box[1] <= cy <= box[3]


def _page_lines(page) -> list[dict]:
    lines = []
    tables = _table_boxes(page)  # text inside tables is cell content, not headings
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            spans = [s for s in line.get("spans", []) if s.get("text", "").strip()]
            if not spans or any(_inside(t, line["bbox"]) for t in tables):
                continue
            text = re.sub(r"\s+", " ", "".join(s["text"] for s in spans)).strip()
            lines.append(
                {
                    "text": text,
                    "size": round(max(s["size"] for s in spans), 1),
                    "bold": all(_is_bold(s) for s in spans),
                    "chars": sum(len(s["text"]) for s in spans),
                }
            )
    return lines


def _detect_headings(all_lines: list[tuple[int, dict]]) -> list[Heading]:
    sizes: Counter = Counter()
    for _, ln in all_lines:
        sizes[ln["size"]] += ln["chars"]
    body = sizes.most_common(1)[0][0] if sizes else 11.0

    found: list[Heading] = []
    prev_style = None
    for page, ln in all_lines:
        text = ln["text"].rstrip(":").strip()
        if len(text) < 3 or len(text) > 90 or text.startswith(_BULLETS + ("“", '"')) or text.endswith("”"):
            prev_style = None
            continue
        level = None
        if _MODULE_RE.match(text):
            level = 1
        elif _NUMBERED_RE.match(text):
            level = 2 if text.split()[0].rstrip(".)").count(".") == 1 else 3
        elif (ln["size"] >= body * 1.2) or (ln["bold"] and not text.endswith((".", ",", ";"))):
            level = 1 if ln["size"] >= body * 1.5 else 3
        if level is None:
            prev_style = None
            continue
        style = (page, ln["size"], ln["bold"], level)
        # a heading wrapped over two lines (same style, un-numbered) is merged into one
        if prev_style == style and level == 3 and found and not _NUMBERED_RE.match(text):
            found[-1].title = f"{found[-1].title} {text}"
        else:
            found.append(Heading(title=text, page=page, level=level))
        prev_style = style if level == 3 else None

    seen: set[str] = set()
    unique: list[Heading] = []
    for h in found:
        key = h.title.lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)
    return unique


def extract_pdf(path: Path) -> ExtractedPDF:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # corrupt files raise several different exception types
        raise PDFExtractionError("The file could not be opened as a PDF (it may be corrupt).") from exc
    try:
        if doc.needs_pass:
            raise PDFExtractionError("The PDF is password-protected. Remove the password and upload it again.")
        pages, lines = [], []
        for index, page in enumerate(doc, start=1):
            pages.append(PageText(page_number=index, text=page.get_text("text")))
            lines.extend((index, ln) for ln in _page_lines(page))
        return ExtractedPDF(page_count=len(pages), pages=pages, headings=_detect_headings(lines))
    except PDFExtractionError:
        raise
    except Exception as exc:
        raise PDFExtractionError("Text extraction failed for this PDF.") from exc
    finally:
        doc.close()


MIN_CHARS_PER_PAGE = 40


def looks_scanned(extracted: ExtractedPDF) -> bool:
    """True when the PDF has pages but almost no selectable text (typical of scanned images)."""
    return extracted.page_count > 0 and extracted.char_count < MIN_CHARS_PER_PAGE * extracted.page_count
