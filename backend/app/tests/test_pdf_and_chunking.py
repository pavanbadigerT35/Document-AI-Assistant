import re

import pymupdf
import pytest

from app.services.chunking_service import _Unit, _overlap_suffix, chunk_page, chunk_pages, estimate_tokens
from app.services.embedding_service import SentenceTransformerEmbedder
from app.services.pdf_service import Heading, PageText, PDFExtractionError, extract_pdf, looks_scanned
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
    text = "A short paragraph fits in one useful chunk."
    assert chunk_page(text, 400, 50, max_size=500) == [text]


def test_long_page_splits_and_respects_maximum():
    text = "\n\n".join(
        f"Paragraph {i} explains a distinct testing concept. It includes useful supporting details."
        for i in range(100)
    )
    chunks = chunk_page(text, 100, 10, max_size=120)
    assert len(chunks) > 3
    assert all(estimate_tokens(chunk) <= 120 for chunk in chunks)


def test_paragraph_boundaries_are_preserved():
    text = "First paragraph has a complete thought.\n\nSecond paragraph adds another thought."
    chunks = chunk_page(text, 40, 5, max_size=50)
    assert len(chunks) == 1
    assert "\n\n" in chunks[0]


def test_extracted_headings_are_preserved_in_chunk_text():
    text = "Introductory material.\n\nModule 1: Basics\n\nThe section explains the central idea."
    chunks = chunk_page(text, 50, 5, max_size=60, headings=["Module 1: Basics"])
    assert any("Module 1: Basics" in chunk for chunk in chunks)
    assert any("central idea" in chunk for chunk in chunks)


def test_long_sentences_and_paragraphs_are_split_under_maximum():
    paragraph = " ".join(f"word{i}" for i in range(180))
    chunks = chunk_page(paragraph, 30, 5, max_size=40)
    assert len(chunks) > 1
    assert all(estimate_tokens(chunk) <= 40 for chunk in chunks)


@pytest.mark.parametrize("text", ["", "   \n\t  ", "\n\n"])
def test_empty_and_whitespace_pages_produce_no_chunks(text):
    assert chunk_page(text, 400, 50, max_size=500) == []


def test_unicode_punctuation_and_unusual_whitespace_are_safe():
    text = "Café\tuses Unicode—correctly.\n\nSymbols: “quotes”, naïve, 東京, and e\u0301."
    chunks = chunk_page(text, 30, 5, max_size=40)
    assert len(chunks) == 1
    assert "Café" in chunks[0] and "東京" in chunks[0] and "“quotes”" in chunks[0]
    assert estimate_tokens(chunks[0]) <= 40


def test_overlap_reuses_a_sentence_without_repeating_paragraphs():
    text = "Alpha begins. Beta follows. Gamma continues. Delta completes. Echo finishes."
    chunks = chunk_page(text, 8, 5, max_size=10)
    assert len(chunks) > 1
    assert all(left != right for left, right in zip(chunks, chunks[1:]))
    assert any(chunks[i].split(". ")[-1] in chunks[i + 1] for i in range(len(chunks) - 1))


@pytest.mark.parametrize(
    "text",
    [
        "Alpha begins. Beta follows.\n\nGamma continues. Delta completes.",
        "Alpha begins with a long explanation that continues for quite a while. Beta follows with another detailed explanation that is also quite long.",
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu.",
    ],
)
def test_overlap_carries_content_across_paragraph_and_sentence_chunks(text):
    chunks = chunk_page(text, 8, 5, max_size=10)
    assert len(chunks) > 1
    assert all(left != right for left, right in zip(chunks, chunks[1:]))
    assert all(set(left.split()) & set(right.split()) for left, right in zip(chunks, chunks[1:]))


def test_overlap_skips_partial_split_when_budget_cannot_fit_special_tokens():
    def token_counter(text):
        return len(text.split()) + 2

    def text_splitter(text, max_tokens):
        if max_tokens < 2:
            raise ValueError("max_tokens must leave room for content and special tokens")
        return [text]

    suffix = _overlap_suffix(
        [_Unit("one two three four", "\n\n"), _Unit("last", " ")],
        6,
        token_counter,
        text_splitter,
    )

    assert [unit.text for unit in suffix] == ["last"]


class _FakeTokenizer:
    pattern = re.compile(r"\w+|[^\w\s]", re.UNICODE)

    def num_special_tokens_to_add(self, pair=False):
        return 2

    def encode(self, text, add_special_tokens=True, truncation=False):
        tokens = self.pattern.findall(text)
        return ([0] + list(range(len(tokens))) + [1]) if add_special_tokens else list(range(len(tokens)))

    def __call__(self, text, add_special_tokens=False, truncation=False, return_offsets_mapping=False):
        return {
            "offset_mapping": [(match.start(), match.end()) for match in self.pattern.finditer(text)]
        }


class _FakeModel:
    max_seq_length = 8
    tokenizer = _FakeTokenizer()


def test_model_tokenizer_limit_includes_special_tokens_and_splits_without_truncation():
    embedder = SentenceTransformerEmbedder("fake-model")
    embedder._model = _FakeModel()
    assert embedder.max_input_tokens == 8
    pieces = embedder.split_text("one two three four five six seven", 8)
    assert len(pieces) > 1
    assert all(embedder.token_count(piece) <= 8 for piece in pieces)
    chunks = chunk_page(
        "one two three four five six seven eight nine ten.",
        6,
        2,
        max_size=8,
        token_counter=embedder.token_count,
        text_splitter=embedder.split_text,
    )
    assert len(chunks) > 1
    assert all(embedder.token_count(chunk) <= embedder.max_input_tokens for chunk in chunks)


def test_chunks_never_cross_pages_and_keep_page_numbers():
    pages = [PageText(1, "alpha " * 50), PageText(2, ""), PageText(3, "gamma " * 400)]
    chunks = chunk_pages(pages, 50, 10, max_size=60)
    assert {c.page for c in chunks} == {1, 3}
    assert all(("alpha" in c.text) == (c.page == 1) for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert all(c.text.strip() for c in chunks)


def test_single_huge_line_is_hard_split():
    chunks = chunk_page("x" * 5000, 100, 10, max_size=120)
    assert all(estimate_tokens(c) <= 120 for c in chunks) and len(chunks) >= 5


def test_chunk_pages_preserves_page_heading_and_deterministic_global_indexes():
    pages = [PageText(4, "Title One\n\nAn explanation."), PageText(5, "Title Two\n\nAnother explanation.")]
    headings = [Heading("Title One", 4, 1), Heading("Title Two", 5, 1)]
    first = chunk_pages(pages, 40, 5, max_size=50, headings=headings)
    second = chunk_pages(pages, 40, 5, max_size=50, headings=headings)
    assert [chunk.index for chunk in first] == [0, 1]
    assert [(chunk.index, chunk.page, chunk.text) for chunk in first] == [
        (chunk.index, chunk.page, chunk.text) for chunk in second
    ]
    assert first[0].page == 4 and "Title One" in first[0].text
    assert first[1].page == 5 and "Title Two" in first[1].text
