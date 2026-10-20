import time
from dataclasses import dataclass, field

from app.services.embedding_service import Embedder
from app.services.vector_store import StoredChunk, VectorStore


@dataclass
class RetrievalResult:
    hits: list[StoredChunk]            # chunks at or above the similarity threshold
    candidates: list[StoredChunk]      # everything the vector search returned (for debugging)
    latency_ms: float
    top_k: int
    min_score: float
    top_score: float | None = field(default=None)

    @property
    def sufficient(self) -> bool:
        return bool(self.hits)


class RetrievalService:
    def __init__(self, embedder: Embedder, store: VectorStore, default_top_k: int, default_min_score: float):
        self.embedder, self.store = embedder, store
        self.default_top_k, self.default_min_score = default_top_k, default_min_score

    def search(self, query: str, document_ids: list[str] | None = None, top_k: int | None = None, min_score: float | None = None) -> RetrievalResult:
        top_k = top_k or self.default_top_k
        min_score = self.default_min_score if min_score is None else min_score
        start = time.perf_counter()
        vector = self.embedder.embed([query])[0]
        candidates = self.store.query(vector, top_k, document_ids)
        hits = [c for c in candidates if c.score >= min_score]
        return RetrievalResult(
            hits=hits,
            candidates=candidates,
            latency_ms=round((time.perf_counter() - start) * 1000, 1),
            top_k=top_k,
            min_score=min_score,
            top_score=candidates[0].score if candidates else None,
        )
