"""Client Qdrant asynchrone — recherche sémantique et persistance des embeddings."""

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from app.core.config import settings
from app.services.llm import embed

COLLECTION = "research_memory"
VECTOR_SIZE = 1536  # text-embedding-3-small

_client: AsyncQdrantClient | None = None


async def _get() -> AsyncQdrantClient:
    """Retourne le client Qdrant (singleton lazy)."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _client


async def _ensure_collection() -> None:
    """Crée la collection Qdrant si elle n'existe pas encore."""
    client = await _get()
    existing = {c.name for c in (await client.get_collections()).collections}
    if COLLECTION not in existing:
        await client.create_collection(
            collection_name=COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )


async def search(query: str, limit: int = 3) -> list[str]:
    """Retourne les `limit` passages les plus proches sémantiquement de la requête."""
    await _ensure_collection()
    client = await _get()
    vector = await embed(query)
    hits = await client.search(collection_name=COLLECTION, query_vector=vector, limit=limit)
    return [h.payload.get("text", "") for h in hits]


async def upsert(text: str, doc_id: str) -> None:
    """Insère ou met à jour un document dans la collection par son identifiant."""
    await _ensure_collection()
    client = await _get()
    vector = await embed(text)
    point_id = abs(hash(doc_id)) % (2**63)
    await client.upsert(
        collection_name=COLLECTION,
        points=[PointStruct(id=point_id, vector=vector, payload={"text": text})],
    )
