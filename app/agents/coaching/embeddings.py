import hashlib
import math
import re
from collections import Counter
from typing import Protocol

from app.agents.coaching.settings import Settings

TOKEN_RE = re.compile(r"[a-z0-9_+#.-]+", re.IGNORECASE)


class EmbeddingService(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]:
        ...


class HashEmbeddingService:
    """Small local fallback embedding.

    This is not as semantically strong as a transformer embedding model, but it
    is deterministic, dependency-light, and good enough to validate pgvector
    retrieval before heavier embedding infrastructure is configured.
    """

    def __init__(self, dimension: int) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        tokens = TOKEN_RE.findall(text.lower())
        if not tokens:
            tokens = ["empty"]

        bigrams = [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        counts = Counter(tokens + bigrams)
        vector = [0.0] * self.dimension

        for token, count in counts.items():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign * (1.0 + math.log(count))

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class SentenceTransformerEmbeddingService:
    def __init__(self, model_name: str, dimension: int) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        raw = self.model.encode(text, normalize_embeddings=True)
        vector = [float(value) for value in raw]
        if len(vector) == self.dimension:
            return vector
        if len(vector) > self.dimension:
            return vector[: self.dimension]
        return vector + [0.0] * (self.dimension - len(vector))


def build_embedding_service(settings: Settings) -> EmbeddingService:
    if settings.embedding_provider == "sentence_transformers":
        try:
            return SentenceTransformerEmbeddingService(
                settings.embedding_model_name,
                settings.embedding_dimension,
            )
        except Exception:
            return HashEmbeddingService(settings.embedding_dimension)
    return HashEmbeddingService(settings.embedding_dimension)


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
