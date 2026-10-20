import math

from app.services.chunking_service import Chunk
from app.services.vector_store import ADD_BATCH, VectorStore


def vec(i: int) -> list[float]:
    return [math.cos(i), math.sin(i), 0.5, 0.1]


def test_large_documents_are_added_in_batches(tmp_path):
    store = VectorStore(tmp_path / "chroma")
    n = ADD_BATCH * 2 + 137  # more than one batch
    chunks = [Chunk(index=i, page=i // 10 + 1, text=f"chunk {i}") for i in range(n)]
    store.add_chunks("doc1", "big.pdf", chunks, [vec(i) for i in range(n)])
    assert store.count("doc1") == n and store.count() == n


def test_query_scores_are_cosine_similarity_and_sorted(tmp_path):
    store = VectorStore(tmp_path / "chroma")
    chunks = [Chunk(index=i, page=i + 1, text=f"chunk {i}") for i in range(20)]
    store.add_chunks("doc1", "a.pdf", chunks, [vec(i) for i in range(20)])
    hits = store.query(vec(7), top_k=5)
    assert hits[0].chunk_id == "doc1:7" and hits[0].page == 8 and abs(hits[0].score - 1.0) < 1e-3
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    assert all(-1.0 <= h.score <= 1.0 for h in hits)


def test_asking_for_more_results_than_a_filtered_document_has(tmp_path):
    store = VectorStore(tmp_path / "chroma")
    store.add_chunks("a", "a.pdf", [Chunk(0, 1, "only chunk of a")], [vec(1)])
    store.add_chunks("b", "b.pdf", [Chunk(i, 1, f"b{i}") for i in range(6)], [vec(i + 10) for i in range(6)])
    hits = store.query(vec(1), top_k=5, document_ids=["a"])
    assert [h.document_id for h in hits] == ["a"]
    assert store.query(vec(1), top_k=5, document_ids=["missing"]) == []
    assert store.query(vec(1), top_k=5, document_ids=[]) == []


def test_re_adding_a_document_replaces_its_chunks(tmp_path):
    store = VectorStore(tmp_path / "chroma")
    store.add_chunks("d", "d.pdf", [Chunk(i, 1, f"v1 {i}") for i in range(5)], [vec(i) for i in range(5)])
    store.add_chunks("d", "d.pdf", [Chunk(i, 1, f"v2 {i}") for i in range(3)], [vec(i) for i in range(3)])
    assert store.count("d") == 3
    store.delete_document("d")
    assert store.count("d") == 0 and store.count() == 0
