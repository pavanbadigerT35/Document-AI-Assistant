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
    def max_input_tokens(self) -> int | None: ...

    def token_count(self, text: str) -> int: ...

    def split_text(self, text: str, max_tokens: int) -> list[str]: ...

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

    @property
    def max_input_tokens(self) -> int:
        return int(self._load().max_seq_length)

    def token_count(self, text: str) -> int:
        model = self._load()
        return len(model.tokenizer.encode(text, add_special_tokens=True, truncation=False))

    def split_text(self, text: str, max_tokens: int) -> list[str]:
        if max_tokens < 2:
            raise ValueError("max_tokens must leave room for content and special tokens")
        tokenizer = self._load().tokenizer
        encoded = tokenizer(
            text,
            add_special_tokens=False,
            truncation=False,
            return_offsets_mapping=True,
        )
        offsets = encoded["offset_mapping"]
        special_tokens = tokenizer.num_special_tokens_to_add(pair=False)
        width = max_tokens - special_tokens
        if width < 1:
            raise ValueError("max_tokens is too small for the tokenizer's special tokens")

        pieces: list[str] = []
        cursor = 0
        while cursor < len(offsets):
            end = min(cursor + width, len(offsets))
            while end > cursor:
                start_char = offsets[cursor][0]
                end_char = offsets[end - 1][1]
                piece = text[start_char:end_char].strip()
                if piece and self.token_count(piece) <= max_tokens:
                    pieces.append(piece)
                    cursor = end
                    break
                end -= 1
            else:
                raise ValueError("The tokenizer could not split text within the model sequence limit")
        return pieces

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
    def max_input_tokens(self) -> int | None:
        return None

    def token_count(self, text: str) -> int:
        from app.services.chunking_service import estimate_tokens

        return estimate_tokens(text)

    def split_text(self, text: str, max_tokens: int) -> list[str]:
        from app.services.chunking_service import _split_long

        return _split_long(text, max_tokens)

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
