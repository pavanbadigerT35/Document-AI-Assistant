import pymupdf
import pytest

from app.services.chunking_service import chunk_page, chunk_pages
from app.services.pdf_service import PageText, PDFExtractionError, extract_pdf, looks_scanned
from app.tests.conftest import make_pdf


def test_extraction_preserves_page_numbers(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(make_pdf(["First page text about apples and oranges for the test.", "Second page text about kernels and schedulers."]))
    r = extract_pdf(f)
    assert r.page_count == 2
    assert [p.page_number for p in r.pages] == [1, 2]
    assert "apples" in r.pages[0].text and "kernels" in r.pages[1].text


def test_headings_detected_from_font_style(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(make_pdf(["Body text that is long enough to be normal paragraph content in the document."], {0: ["Module 1: Basics"]}))
    titles = [(h.title, h.level, h.page) for h in extract_pdf(f).headings]
    assert ("Module 1: Basics", 1, 1) in titles


def test_scanned_pdf_is_detected(tmp_path):
    doc = pymupdf.open()
    doc.new_page(); doc.new_page()
    f = tmp_path / "blank.pdf"
    f.write_bytes(doc.tobytes())
    assert looks_scanned(extract_pdf(f))


def test_corrupt_pdf_raises(tmp_path):
    f = tmp_path / "bad.pdf"
    f.write_bytes(b"%PDF-1.4 this is not really a pdf")
    with pytest.raises(PDFExtractionError):
        extract_pdf(f)


def test_short_page_is_single_chunk():
    assert chunk_page("hello world", 2000, 300) == ["hello world"]


def test_long_page_splits_with_overlap_and_respects_size():
    text = "\n".join(f"Line number {i} describes a distinct testing concept in detail." for i in range(80))
    chunks = chunk_page(text, 500, 100)
    assert len(chunks) > 3
    assert all(len(c) <= 500 for c in chunks)
    for prev, nxt in zip(chunks, chunks[1:]):
        assert prev[-40:].split()[-1] in nxt  # trailing words of one chunk reappear at the start of the next


def test_chunks_never_cross_pages_and_keep_page_numbers():
    pages = [PageText(1, "alpha " * 50), PageText(2, ""), PageText(3, "gamma " * 400)]
    chunks = chunk_pages(pages, 500, 75)
    assert {c.page for c in chunks} == {1, 3}
    assert all(("alpha" in c.text) == (c.page == 1) for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_single_huge_line_is_hard_split():
    chunks = chunk_page("x" * 5000, 1000, 100)
    assert all(len(c) <= 1000 for c in chunks) and len(chunks) >= 5
