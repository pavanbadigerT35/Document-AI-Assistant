"""Embedding backends. The SAME embedder instance is used for indexing and for queries."""
import hashlib
import math
import re
import threading
from typing import Protocol


class Embedder(Protocol):
    name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def loaded(self) -> bool: ...


class SentenceTransformerEmbedder:
    """Free local embeddings. The model is downloaded from Hugging Face on first use, then cached."""

    def __init__(self, model_name: str):
        self.name = model_name
        self._model = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer  # imported lazily: slow import

                self._model = SentenceTransformer(self.name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return [v.tolist() for v in vectors]


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder.

    FOR AUTOMATED TESTS AND OFFLINE EVALUATION ONLY. It matches shared words, not meaning,
    so it is much weaker than a real embedding model and must not be used in production.
    """

    DIM = 384
    _STOP = {"the", "a", "an", "of", "and", "or", "to", "in", "is", "are", "for", "on", "what", "how", "does", "do", "with"}

    def __init__(self):
        self.name = "hash-test-embedder"

    @property
    def loaded(self) -> bool:
        return True

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.DIM
            for token in re.findall(r"[a-z0-9]+", text.lower()):
                if token in self._STOP:
                    continue
                digest = hashlib.md5(token.encode()).digest()
                vec[int.from_bytes(digest[:4], "big") % self.DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def build_embedder(backend: str, model_name: str) -> Embedder:
    return HashEmbedder() if backend == "hash" else SentenceTransformerEmbedder(model_name)
