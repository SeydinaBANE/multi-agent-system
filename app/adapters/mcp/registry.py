"""Registre d'outils MCP — extensible sans modifier le code existant.

Pour ajouter un nouvel outil :
  1. Créer une classe héritant de MCPTool
  2. L'enregistrer dans build_mcp_registry() : registry.register(MonOutil())
"""
from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import Implementation

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("mcp_client")
PARALLEL_MCP_URL = "https://search.parallel.ai/mcp"
PROJECT_USER_AGENT = "multi-agent-system/1.0 (+https://github.com/SeydinaBANE/multi-agent-system)"
PARALLEL_TIMEOUT = 15


# ── Interface commune ──────────────────────────────────────────────────────

class MCPTool(ABC):
    """Contrat minimal que chaque outil MCP doit respecter."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    def is_available(self) -> bool:
        """Retourne True si l'outil est configuré et prêt à l'emploi."""
        return True

    @abstractmethod
    async def run(self, query: str) -> str:
        """Exécute l'outil et retourne le texte résultat (vide si rien trouvé)."""
        ...


# ── Outil Brave Search ─────────────────────────────────────────────────────

class BraveSearchTool(MCPTool):
    """Recherche web en temps réel via l'API Brave Search."""

    @property
    def name(self) -> str:
        return "brave_search"

    @property
    def description(self) -> str:
        return "Recherche web via Brave Search — résultats récents et fiables"

    def is_available(self) -> bool:
        return bool(settings.brave_api_key)

    async def run(self, query: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": 5},
                    headers={
                        "X-Subscription-Token": settings.brave_api_key or "",
                        "Accept": "application/json",
                    },
                )
                response.raise_for_status()
                data = response.json()
            results = data.get("web", {}).get("results", [])
            if not results:
                return ""
            lines = [
                f"- {r['title']} ({r['url']}): {r.get('description', '')}"
                for r in results
            ]
            return "\n".join(lines)
        except Exception as exc:
            log.warning("brave_search_failed", error=str(exc))
            return ""


class ParallelSearchTool(MCPTool):
    """Recherche anonyme via le transport Streamable HTTP de Parallel Search MCP."""

    @property
    def name(self) -> str:
        return "parallel_search"

    @property
    def description(self) -> str:
        return "Recherche web via Parallel Search MCP, sans clé API"

    async def run(self, query: str) -> str:
        try:
            # Borne aussi la découverte et la fermeture de session, pas seulement HTTP.
            async with asyncio.timeout(PARALLEL_TIMEOUT):
                async with httpx.AsyncClient(
                    headers={"User-Agent": PROJECT_USER_AGENT}, timeout=10,
                ) as client:
                    async with streamable_http_client(
                        PARALLEL_MCP_URL, http_client=client,
                    ) as (read, write, _):
                        async with ClientSession(
                            read, write,
                            client_info=Implementation(name="multi-agent-system", version="1.0"),
                        ) as session:
                            await session.initialize()
                            tools = await session.list_tools()
                            if not any(tool.name == "web_search" for tool in tools.tools):
                                raise RuntimeError("Parallel MCP web_search unavailable")
                            result = await session.call_tool(
                                "web_search",
                                arguments={"objective": query, "search_queries": [query]},
                            )
                            if result.isError:
                                raise RuntimeError("Parallel MCP search failed")
                            text = "\n".join(
                                block.text for block in result.content if block.type == "text"
                            )
                            if text:
                                return text
                            if result.structuredContent:
                                return json.dumps(result.structuredContent, ensure_ascii=False)
                            return ""
        except Exception as exc:
            log.warning("parallel_search_failed", error=str(exc))
            return ""


# ── Registre ───────────────────────────────────────────────────────────────

class MCPRegistry:
    """Registre des outils disponibles — thread-safe, extensible à chaud."""

    def __init__(self) -> None:
        self._tools: list[MCPTool] = []

    def register(self, tool: MCPTool) -> None:
        """Enregistre un outil s'il est disponible, l'ignore sinon."""
        if tool.is_available():
            self._tools.append(tool)
            log.info("mcp_tool_registered", name=tool.name)
        else:
            log.info("mcp_tool_skipped", name=tool.name, reason="not_configured")

    @property
    def available(self) -> list[MCPTool]:
        return list(self._tools)

    async def run_all(self, query: str) -> dict[str, str]:
        """Exécute tous les outils en parallèle, ignore les échecs individuels."""
        if not self._tools:
            return {}
        results = await asyncio.gather(
            *[t.run(query) for t in self._tools],
            return_exceptions=True,
        )
        output: dict[str, str] = {}
        for tool, result in zip(self._tools, results):
            if isinstance(result, asyncio.CancelledError):
                raise result
            elif isinstance(result, Exception):
                log.warning("mcp_tool_error", name=tool.name, error=str(result))
            elif result:
                output[tool.name] = result
        return output


def build_mcp_registry() -> MCPRegistry:
    """Construit un registre avec les outils MCP disponibles — appelé à la construction du Container.

    Pour ajouter un outil, ajouter une ligne registry.register(MonOutil()) ici.
    """
    registry = MCPRegistry()
    provider = settings.search_provider
    if provider == "auto":
        provider = "brave" if settings.brave_api_key else "parallel"
    if provider == "brave":
        registry.register(BraveSearchTool())
    elif provider == "parallel":
        registry.register(ParallelSearchTool())
    # registry.register(GitHubSearchTool())
    # registry.register(WikipediaTool())
    log.info("mcp_setup_complete", tools=[t.name for t in registry.available])
    return registry
