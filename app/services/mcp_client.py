"""Registre d'outils MCP — extensible sans modifier le code existant.

Pour ajouter un nouvel outil :
  1. Créer une classe héritant de MCPTool
  2. L'enregistrer dans setup_mcp() : registry.register(MonOutil())
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import httpx

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("mcp_client")


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
            if isinstance(result, Exception):
                log.warning("mcp_tool_error", name=tool.name, error=str(result))
            elif result:
                output[tool.name] = result
        return output


# ── Singleton ──────────────────────────────────────────────────────────────

_registry: MCPRegistry | None = None


def get_registry() -> MCPRegistry:
    """Retourne le registre global (singleton lazy)."""
    global _registry
    if _registry is None:
        _registry = MCPRegistry()
    return _registry


def setup_mcp() -> None:
    """Enregistre les outils MCP disponibles — appelé au lifespan FastAPI.

    Pour ajouter un outil, ajouter une ligne registry.register(MonOutil()) ici.
    """
    global _registry
    _registry = MCPRegistry()  # réinitialise pour éviter les doublons au redémarrage
    registry = _registry
    registry.register(BraveSearchTool())
    # registry.register(GitHubSearchTool())
    # registry.register(WikipediaTool())
    log.info("mcp_setup_complete", tools=[t.name for t in registry.available])


async def close_mcp() -> None:
    """Libère les ressources MCP au shutdown (utile pour outils avec connexions persistantes)."""
    global _registry
    _registry = None
    log.info("mcp_closed")
