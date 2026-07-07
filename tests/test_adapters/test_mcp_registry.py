"""Tests du registre MCP et de l'outil Brave Search."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.adapters.mcp.registry import BraveSearchTool, MCPRegistry, MCPTool, build_mcp_registry


# ── MCPTool (outil fictif pour les tests) ─────────────────────────────────

class AlwaysAvailableTool(MCPTool):
    @property
    def name(self) -> str:
        return "always_on"

    @property
    def description(self) -> str:
        return "Outil toujours disponible"

    async def run(self, query: str) -> str:
        return f"résultat pour : {query}"


class NeverAvailableTool(MCPTool):
    @property
    def name(self) -> str:
        return "never_on"

    @property
    def description(self) -> str:
        return "Outil jamais disponible"

    def is_available(self) -> bool:
        return False

    async def run(self, query: str) -> str:
        return "ne devrait jamais être appelé"


# ── MCPRegistry ────────────────────────────────────────────────────────────

def test_registry_registers_available_tool():
    registry = MCPRegistry()
    registry.register(AlwaysAvailableTool())
    assert len(registry.available) == 1
    assert registry.available[0].name == "always_on"


def test_registry_skips_unavailable_tool():
    registry = MCPRegistry()
    registry.register(NeverAvailableTool())
    assert registry.available == []


async def test_registry_run_all_returns_results():
    registry = MCPRegistry()
    registry.register(AlwaysAvailableTool())
    results = await registry.run_all("test query")
    assert results == {"always_on": "résultat pour : test query"}


async def test_registry_run_all_empty_when_no_tools():
    registry = MCPRegistry()
    results = await registry.run_all("test")
    assert results == {}


async def test_registry_run_all_ignores_tool_exception():
    class FailingTool(MCPTool):
        @property
        def name(self) -> str:
            return "failing"

        @property
        def description(self) -> str:
            return "Outil qui plante"

        async def run(self, query: str) -> str:
            raise RuntimeError("timeout")

    registry = MCPRegistry()
    registry._tools.append(FailingTool())  # bypass register() check
    results = await registry.run_all("test")
    assert results == {}


async def test_registry_run_all_skips_empty_results():
    class EmptyTool(MCPTool):
        @property
        def name(self) -> str:
            return "empty"

        @property
        def description(self) -> str:
            return "Outil qui ne retourne rien"

        async def run(self, query: str) -> str:
            return ""

    registry = MCPRegistry()
    registry._tools.append(EmptyTool())
    results = await registry.run_all("test")
    assert results == {}


# ── BraveSearchTool ────────────────────────────────────────────────────────

def test_brave_search_unavailable_without_key():
    with patch("app.adapters.mcp.registry.settings") as mock_settings:
        mock_settings.brave_api_key = None
        tool = BraveSearchTool()
        assert tool.is_available() is False


def test_brave_search_available_with_key():
    with patch("app.adapters.mcp.registry.settings") as mock_settings:
        mock_settings.brave_api_key = "bsv-test-key"
        tool = BraveSearchTool()
        assert tool.is_available() is True


async def test_brave_search_run_returns_formatted_results():
    fake_response = {
        "web": {
            "results": [
                {"title": "LangGraph docs", "url": "https://example.com/lg", "description": "Graph framework"},
                {"title": "RAG guide", "url": "https://example.com/rag", "description": ""},
            ]
        }
    }

    mock_response = MagicMock()
    mock_response.json.return_value = fake_response
    mock_response.raise_for_status = MagicMock()

    with patch("app.adapters.mcp.registry.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.brave_api_key = "bsv-test-key"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        tool = BraveSearchTool()
        result = await tool.run("LangGraph RAG")

    assert "LangGraph docs" in result
    assert "https://example.com/lg" in result
    assert "Graph framework" in result


async def test_brave_search_run_returns_empty_on_http_error():
    with patch("app.adapters.mcp.registry.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.brave_api_key = "bsv-test-key"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("403"))
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        tool = BraveSearchTool()
        result = await tool.run("query")

    assert result == ""


async def test_brave_search_run_returns_empty_when_no_web_results():
    fake_response = {"web": {"results": []}}

    mock_response = MagicMock()
    mock_response.json.return_value = fake_response
    mock_response.raise_for_status = MagicMock()

    with patch("app.adapters.mcp.registry.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_cls:
        mock_settings.brave_api_key = "bsv-test-key"
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        tool = BraveSearchTool()
        result = await tool.run("nothing found")

    assert result == ""


# ── build_mcp_registry ─────────────────────────────────────────────────────

def test_build_mcp_registry_registers_brave_when_key_present():
    with patch("app.adapters.mcp.registry.settings") as mock_settings:
        mock_settings.brave_api_key = "bsv-test-key"
        registry = build_mcp_registry()
        names = [t.name for t in registry.available]
        assert "brave_search" in names


def test_build_mcp_registry_skips_brave_when_no_key():
    with patch("app.adapters.mcp.registry.settings") as mock_settings:
        mock_settings.brave_api_key = None
        registry = build_mcp_registry()
        names = [t.name for t in registry.available]
        assert "brave_search" not in names
