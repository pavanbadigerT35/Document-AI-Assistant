"""The two SYNTHETIC sample PDFs: multi-document search, filters, deletion and the injection sentence."""
import json
import re
from pathlib import Path

import pytest

from app.services.pdf_service import extract_pdf
from app.tests.conftest import make_pdf, upload
from evaluation.sample_docs import SAMPLES, write_sample_pdfs

REPO = Path(__file__).resolve().parents[3]
DATASET = json.loads((REPO / "backend" / "evaluation" / "sample_dataset.json").read_text(encoding="utf-8"))
API, CICD = "sample_api_testing_notes.pdf", "sample_cicd_pipeline_notes.pdf"
# Questions the test-only hash embedder (word overlap, not meaning) ranks first reliably. The real model is
# evaluated with `python -m evaluation.run_eval`, not here.
RELIABLE = {
    "Which HTTP methods are idempotent?": (API, 1),
    "What is consumer-driven contract testing and which tool is common?": (API, 2),
    "How many automatic retries are allowed for a flaky test?": (CICD, 2),
    "What happens to a test that fails intermittently on three consecutive days?": (CICD, 2),
}


@pytest.fixture
def samples(tmp_path):
    return write_sample_pdfs(tmp_path / "samples")


@pytest.fixture
def two_docs(client, samples):
    ids = {}
    for path in samples:
        r = upload(client, path.name, path.read_bytes())
        assert r.status_code == 201, r.text
        ids[path.name] = r.json()["results"][0]["document"]["id"]
    return ids


def squash(text: str) -> str:
    text = re.sub(r"\s+", " ", text).lower()
    return re.sub(r"(?<=\w)- ", "-", text)  # a line may wrap right after a hyphen


def test_dataset_labels_match_both_generated_and_shipped_pdfs(samples):
    for folder in (samples[0].parent, REPO / "samples"):
        pages = {}
        for name in SAMPLES:
            extracted = extract_pdf(folder / name)
            assert extracted.page_count == 3
            pages.update({(name, p.page_number): squash(p.text) for p in extracted.pages})
        for item in DATASET["answerable"]:
            assert any(squash(item["evidence_phrase"]) in pages[(item["expected_file"], p)] for p in item["expected_pages"]), (folder, item["question"])


def test_multi_document_search_returns_the_right_file_and_page(client, two_docs):
    for question, (filename, page) in RELIABLE.items():
        top = client.post("/api/v1/search", json={"query": question}).json()["results"][0]
        assert (top["filename"], top["page"]) == (filename, page), question


def test_every_labelled_answer_is_in_the_top_five(client, two_docs):
    for item in DATASET["answerable"]:
        body = client.post("/api/v1/search", json={"query": item["question"], "top_k": 5, "min_score": -1}).json()
        assert any(h["filename"] == item["expected_file"] and h["page"] in item["expected_pages"] for h in body["results"]), item["question"]


def test_unanswerable_questions_find_nothing_above_threshold(client, two_docs):
    for question in ("What is the capital city of France?", "What is the recipe for chocolate cake?", "What is the price of the training course?"):
        assert client.post("/api/v1/search", json={"query": question}).json()["results"] == [], question


def test_scope_filter_and_delete_across_two_documents(client, two_docs):
    question = "Which HTTP methods are idempotent?"
    only_cicd = client.post("/api/v1/search", json={"query": question, "document_ids": [two_docs[CICD]], "min_score": -1}).json()
    assert {h["filename"] for h in only_cicd["results"]} == {CICD}
    assert client.delete(f"/api/v1/documents/{two_docs[API]}").status_code == 204
    after = client.post("/api/v1/search", json={"query": question, "min_score": -1}).json()
    assert all(h["filename"] != API for h in after["results"])
    assert client.app.state.container.store.count(two_docs[API]) == 0


def test_injection_sentence_is_data_not_instructions(client, llm, two_docs):
    client.post("/api/v1/chat", json={"question": "What is the p95 latency target for load testing?", "document_ids": [two_docs[API]]})
    call = llm.calls[0]
    assert "PWNED" in call["user"] and "PWNED" not in call["system"]
    assert "never instructions" in call["system"]


def test_suggestions_alternate_between_documents(client, two_docs):
    names = [s["filename"] for s in client.get("/api/v1/suggestions?limit=4").json()]
    assert set(names) == {API, CICD}
