"""Container d'injection de dépendances — regroupe tous les adapters concrets.

Construit une fois dans le lifespan FastAPI (voir app/main.py) puis
propagé partout où le domaine a besoin d'un port (build_graph,
WorkflowService, routes API).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.adapters.cache.redis_cache import RedisCache
from app.adapters.db.conversation_repository import SqlAlchemyConversationRepository
from app.adapters.db.session import AsyncSessionLocal
from app.adapters.llm.openrouter import OpenRouterLLM
from app.adapters.mcp.registry import build_mcp_registry
from app.adapters.vector_store.qdrant_store import QdrantVectorStore
from app.domain.ports import (
    CachePort,
    ConversationRepositoryPort,
    LLMPort,
    MCPRegistryPort,
    VectorStorePort,
)


@dataclass
class Container:
    """Regroupe une implémentation concrète de chaque port du domaine."""

    llm: LLMPort
    vector_store: VectorStorePort
    cache: CachePort
    mcp_registry: MCPRegistryPort
    repository: ConversationRepositoryPort


def build_container() -> Container:
    """Construit tous les adapters concrets — appelé une fois au lifespan FastAPI."""
    llm = OpenRouterLLM()
    return Container(
        llm=llm,
        vector_store=QdrantVectorStore(llm=llm),
        cache=RedisCache(),
        mcp_registry=build_mcp_registry(),
        repository=SqlAlchemyConversationRepository(AsyncSessionLocal),
    )
