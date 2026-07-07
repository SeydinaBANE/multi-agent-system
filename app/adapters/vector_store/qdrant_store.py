"""Adapter mémoire vectorielle — implémente VectorStorePort via Qdrant."""
from __future__ import annotations

import hashlib

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.ports import LLMPort

log = get_logger("vector_store")

COLLECTION = "research_memory"
VECTOR_SIZE = 1536  # text-embedding-3-small


class QdrantVectorStore:
    """Implémentation de VectorStorePort adossée à Qdrant.

    Qdrant Cloud : définir QDRANT_API_KEY + QDRANT_HOST=xyz.cloud.qdrant.io
    Local        : QDRANT_HOST=localhost (pas de clé requise)
    """

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm
        self._client: AsyncQdrantClient | None = None

    async def _get(self) -> AsyncQdrantClient:
        if self._client is None:
            if settings.qdrant_api_key:
                self._client = AsyncQdrantClient(
                    url=f"https://{settings.qdrant_host}:{settings.qdrant_port}",
                    api_key=settings.qdrant_api_key,
                )
            else:
                self._client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        return self._client

    async def _ensure_collection(self) -> None:
        client = await self._get()
        existing = {c.name for c in (await client.get_collections()).collections}
        if COLLECTION not in existing:
            await client.create_collection(
                collection_name=COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )

    async def search(self, query: str, limit: int = 3) -> list[str]:
        """Retourne les `limit` passages les plus proches sémantiquement de la requête."""
        try:
            await self._ensure_collection()
            client = await self._get()
            vector = await self._llm.embed(query)
            result = await client.query_points(collection_name=COLLECTION, query=vector, limit=limit)
            return [h.payload.get("text", "") for h in result.points]
        except Exception as exc:
            log.warning("qdrant_search_failed", error=str(exc))
            return []

    async def upsert(self, text: str, doc_id: str) -> None:
        """Insère ou met à jour un document dans la collection par son identifiant."""
        try:
            await self._ensure_collection()
            client = await self._get()
            vector = await self._llm.embed(text)
            point_id = int(hashlib.sha256(doc_id.encode()).hexdigest(), 16) % (2**63)
            await client.upsert(
                collection_name=COLLECTION,
                points=[PointStruct(id=point_id, vector=vector, payload={"text": text})],
            )
        except Exception as exc:
            log.warning("qdrant_upsert_failed", doc_id=doc_id, error=str(exc))
            raise
