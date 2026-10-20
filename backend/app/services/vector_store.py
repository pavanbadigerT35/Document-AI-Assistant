"""Persistent ChromaDB storage. Every chunk keeps document id, filename, page and chunk index."""
from dataclasses import dataclass
from pathlib import Path

import chromadb
import numpy as np
from chromadb.config import Settings as ChromaSettings

from app.services.chunking_service import Chunk

COLLECTION = "document_chunks"
ADD_BATCH = 500  # Chroma rejects a single add() larger than its internal maximum batch size (a few thousand)


@dataclass
class StoredChunk:
    chunk_id: str
    document_id: str
    filename: str
    page: int
    chunk_index: int
    text: str
    score: float = 0.0


class VectorStore:
    def __init__(self, path: Path):
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path), settings=ChromaSettings(anonymized_telemetry=False))
        self._col = self._client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})

    @staticmethod
    def _where(document_ids: list[str] | None):
        return None if document_ids is None else {"document_id": {"$in": list(document_ids)}}

    def add_chunks(self, document_id: str, filename: str, chunks: list[Chunk], embeddings: list[list[float]]) -> None:
        if not chunks:
            return
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")
        self.delete_document(document_id)  # idempotent: never leave stale chunks behind
        for i in range(0, len(chunks), ADD_BATCH):
            part = chunks[i : i + ADD_BATCH]
            self._col.add(
                ids=[f"{document_id}:{c.index}" for c in part],
                embeddings=embeddings[i : i + ADD_BATCH],
                documents=[c.text for c in part],
                metadatas=[
                    {"document_id": document_id, "filename": filename, "page": c.page, "chunk_index": c.index}
                    for c in part
                ],
            )

    def delete_document(self, document_id: str) -> None:
        self._col.delete(where={"document_id": document_id})

    def count(self, document_id: str | None = None) -> int:
        if document_id is None:
            return self._col.count()
        return len(self._col.get(where={"document_id": document_id}, include=[])["ids"])

    def _matching(self, document_ids: list[str] | None) -> int:
        if document_ids is None:
            return self._col.count()
        return len(self._col.get(where=self._where(document_ids), include=[])["ids"])

    @staticmethod
    def _cosine(query: np.ndarray, stored) -> float:
        vec = np.asarray(stored, dtype=float)
        denom = float(np.linalg.norm(query) * np.linalg.norm(vec))
        return float(np.dot(query, vec) / denom) if denom else 0.0

    def query(self, embedding: list[float], top_k: int, document_ids: list[str] | None = None) -> list[StoredChunk]:
        if document_ids is not None and not document_ids:
            return []
        available = self._matching(document_ids)  # asking for more results than exist can raise in some Chroma versions
        if available == 0:
            return []
        res = self._col.query(
            query_embeddings=[embedding],
            n_results=min(top_k, available),
            where=self._where(document_ids),
            include=["documents", "metadatas", "embeddings"],
        )
        q = np.asarray(embedding, dtype=float)
        hits = []
        for cid, doc, meta, emb in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["embeddings"][0]):
            hits.append(
                StoredChunk(
                    chunk_id=cid,
                    document_id=meta["document_id"],
                    filename=meta["filename"],
                    page=int(meta["page"]),
                    chunk_index=int(meta["chunk_index"]),
                    text=doc,
                    # Cosine similarity computed here from the stored vector, so scores do not depend on which
                    # distance metric the Chroma version/collection happens to use (the setting is deprecated in 1.x).
                    # Embeddings are unit-length, so Euclidean and cosine give the same ranking.
                    score=round(self._cosine(q, emb), 4),
                )
            )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits

    def sample(self, document_ids: list[str] | None, limit: int) -> list[StoredChunk]:
        """Evenly spaced chunks in document order (used for quizzes when no topic is given)."""
        res = self._col.get(where=self._where(document_ids), include=["documents", "metadatas"])
        items = [
            StoredChunk(i, m["document_id"], m["filename"], int(m["page"]), int(m["chunk_index"]), d)
            for i, d, m in zip(res["ids"], res["documents"], res["metadatas"])
        ]
        items.sort(key=lambda c: (c.document_id, c.chunk_index))
        if len(items) <= limit:
            return items
        step = len(items) / limit
        return [items[int(i * step)] for i in range(limit)]
