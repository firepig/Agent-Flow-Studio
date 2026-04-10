"""Lightweight local vector store with OpenAI embeddings + pure-Python fallback."""
from __future__ import annotations

import hashlib
import json
import math
import re
import uuid
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Cosine similarity (pure Python, no numpy needed)
# ---------------------------------------------------------------------------

def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _magnitude(v: list[float]) -> float:
    return math.sqrt(sum(x * x for x in v))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    mag_a, mag_b = _magnitude(a), _magnitude(b)
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return _dot(a, b) / (mag_a * mag_b)


# ---------------------------------------------------------------------------
# Embedding providers
# ---------------------------------------------------------------------------

async def embed_openai(texts: list[str], api_key: str, model: str = "text-embedding-3-small") -> list[list[float]]:
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=api_key)
    resp = await client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in sorted(resp.data, key=lambda d: d.index)]


def embed_fallback(texts: list[str], dim: int = 384) -> list[list[float]]:
    """Bag-of-words hashing fallback when no API key is available.

    Not as good as real embeddings but sufficient for basic similarity
    matching over small collections.
    """
    vectors = []
    for text in texts:
        vec = [0.0] * dim
        tokens = re.findall(r'\w+', text.lower())
        for i, token in enumerate(tokens):
            h = int(hashlib.md5(token.encode()).hexdigest(), 16)
            idx = h % dim
            weight = 1.0 / (1 + math.log1p(i))  # position decay
            vec[idx] += weight
            # bigram contribution
            if i > 0:
                bigram = tokens[i - 1] + "_" + token
                h2 = int(hashlib.md5(bigram.encode()).hexdigest(), 16)
                vec[h2 % dim] += weight * 0.5
        mag = _magnitude(vec)
        if mag > 0:
            vec = [v / mag for v in vec]
        vectors.append(vec)
    return vectors


async def get_embeddings(
    texts: list[str],
    settings: dict,
    model: str | None = None,
) -> list[list[float]]:
    api_key = settings.get("openai_api_key", "")
    if api_key and not api_key.startswith("*"):
        try:
            return await embed_openai(texts, api_key, model or "text-embedding-3-small")
        except Exception:
            pass
    return embed_fallback(texts)


# ---------------------------------------------------------------------------
# Local Vector Store  (JSON-file backed)
# ---------------------------------------------------------------------------

VECTOR_STORES_DIR = Path("vector_stores")


class VectorStore:
    """Simple file-backed vector store.  One JSON file per collection."""

    def __init__(self, collection: str):
        VECTOR_STORES_DIR.mkdir(exist_ok=True)
        self.collection = collection
        self.path = VECTOR_STORES_DIR / f"{collection}.json"
        self.docs: list[dict] = []
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self.docs = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.docs = []

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.docs), encoding="utf-8")

    def insert(
        self,
        texts: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> list[str]:
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        if metadatas is None:
            metadatas = [{} for _ in texts]
        for doc_id, text, emb, meta in zip(ids, texts, embeddings, metadatas):
            self.docs.append({
                "id": doc_id,
                "text": text,
                "embedding": emb,
                "metadata": meta,
            })
        self._save()
        return ids

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
        metadata_filter: dict | None = None,
    ) -> list[dict]:
        scored = []
        for doc in self.docs:
            if metadata_filter:
                match = all(doc.get("metadata", {}).get(k) == v for k, v in metadata_filter.items())
                if not match:
                    continue
            sim = cosine_similarity(query_embedding, doc["embedding"])
            if sim >= threshold:
                scored.append({**doc, "score": round(sim, 4)})
        scored.sort(key=lambda d: d["score"], reverse=True)
        for item in scored:
            item.pop("embedding", None)
        return scored[:top_k]

    def delete(self, doc_ids: list[str] | None = None, all_docs: bool = False) -> int:
        if all_docs:
            count = len(self.docs)
            self.docs = []
            self._save()
            return count
        if doc_ids:
            before = len(self.docs)
            self.docs = [d for d in self.docs if d["id"] not in set(doc_ids)]
            self._save()
            return before - len(self.docs)
        return 0

    def count(self) -> int:
        return len(self.docs)

    def list_ids(self) -> list[str]:
        return [d["id"] for d in self.docs]
