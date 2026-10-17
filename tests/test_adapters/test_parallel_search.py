"""Contrat HTTP MCP et consommation réelle des résultats par le Researcher.

Le serveur HTTP et le LLM sont simulés ; le SDK MCP, le registre et le Researcher
sont exécutés sans remplacement.
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.adapters.mcp import registry as mcp
from app.agents.researcher import make_researcher_node
from app.core.config import Settings
from tests.conftest import make_state


@pytest.fixture
def config(monkeypatch):
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    monkeypatch.delenv("SEARCH_PROVIDER", raising=False)
    settings = Settings(_env_file=None, openrouter_api_key="test-key")
    monkeypatch.setattr(mcp, "settings", settings)
    return settings


@pytest.fixture
def server(monkeypatch):
    requests = []
    clients = []
    started = asyncio.Event()
    state = {"mode": "success"}
    client_class = httpx.AsyncClient

    async def handle(request):
        requests.append(request)
        assert str(request.url) == mcp.PARALLEL_MCP_URL
        assert request.headers["user-agent"] == mcp.PROJECT_USER_AGENT
        assert "authorization" not in request.headers
        if request.method != "POST":
            return httpx.Response(405)
        payload = json.loads(request.content)
        method = payload["method"]
        if method.startswith("notifications/"):
            return httpx.Response(202)
        if method == "initialize":
            result = {
                "protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                "serverInfo": {"name": "test-search", "version": "1.0"},
            }
        elif method == "tools/list":
            result = {"tools": [] if state["mode"] == "missing" else [{
                "name": "web_search", "inputSchema": {"type": "object"},
            }]}
        elif method == "tools/call":
            assert payload["params"]["name"] == "web_search"
            arguments = payload["params"]["arguments"]
            assert arguments["objective"] == "LangGraph research sources"
            assert arguments["search_queries"] == ["LangGraph research sources"]
            started.set()
            if state["mode"] == "wait":
                await asyncio.Event().wait()
            if state["mode"] == "timeout":
                raise httpx.ReadTimeout("test timeout", request=request)
            if state["mode"] == "http_error":
                return httpx.Response(503)
            if state["mode"] == "malformed":
                return httpx.Response(200, content="invalid", headers={"content-type": "application/json"})
            if state["mode"] == "rpc_error":
                return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"],
                                                "error": {"code": -32603, "message": "Search failed"}})
            content = {"results": [{"title": "LangGraph", "url": "https://example.org/docs?q=a&lang=fr",
                                    "excerpts": ["Source vérifiée pour le Researcher."]}]}
            result = {"content": [{"type": "text", "text": json.dumps(content)}]}
            if state["mode"] == "tool_error":
                result = {"isError": True, "content": [{"type": "text", "text": "Service unavailable"}]}
            elif state["mode"] == "structured":
                result = {"content": [], "structuredContent": content}
        else:
            raise AssertionError(method)
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": payload["id"], "result": result})

    def client_factory(*args, **kwargs):
        client = client_class(*args, transport=httpx.MockTransport(handle), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(mcp.httpx, "AsyncClient", client_factory)
    return state, requests, clients, started


def make_node():
    llm = AsyncMock()
    llm.chat_completion.return_value = "Synthèse avec source."
    vector_store = AsyncMock()
    vector_store.search.return_value = ["Contexte RAG"]
    node = make_researcher_node(llm, vector_store, mcp.build_mcp_registry())
    return node, llm


@pytest.mark.parametrize("mode", ["success", "structured"])
async def test_fresh_config_search_reaches_researcher_prompt(config, server, mode):
    state, requests, clients, _ = server
    state["mode"] = mode
    node, llm = make_node()
    result = await node(make_state(task="LangGraph research sources"))
    prompt = llm.chat_completion.call_args.kwargs["messages"][-1]["content"]
    assert "parallel_search" in prompt
    assert "https://example.org/docs?q=a&lang=fr" in prompt
    assert "Source" in prompt and "Researcher" in prompt
    assert "Contexte RAG" in prompt
    assert result["research"] == ["Synthèse avec source."]
    methods = [json.loads(r.content)["method"] for r in requests if r.method == "POST"]
    assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/call"]
    assert all(c.is_closed for c in clients)


@pytest.mark.parametrize("provider,key,expected", [
    ("auto", None, ["parallel_search"]),
    ("auto", "saved-brave-key", ["brave_search"]),
    ("parallel", "saved-brave-key", ["parallel_search"]),
    ("brave", "saved-brave-key", ["brave_search"]),
    ("brave", None, []),
    ("none", None, []),
    ("none", "saved-brave-key", []),
])
def test_provider_selection_preserves_choices(config, provider, key, expected):
    config.search_provider = provider
    config.brave_api_key = key
    assert [t.name for t in mcp.build_mcp_registry().available] == expected


def test_saved_settings_and_environment_override(config, monkeypatch, tmp_path):
    saved = tmp_path / ".env"
    saved.write_text("BRAVE_API_KEY=saved-key\nSEARCH_PROVIDER=brave\n")
    settings = Settings(_env_file=saved, openrouter_api_key="test")
    monkeypatch.setattr(mcp, "settings", settings)
    assert [t.name for t in mcp.build_mcp_registry().available] == ["brave_search"]
    monkeypatch.setenv("SEARCH_PROVIDER", "none")
    monkeypatch.setattr(mcp, "settings", Settings(_env_file=saved, openrouter_api_key="test"))
    assert mcp.build_mcp_registry().available == []


def test_invalid_provider_is_rejected(config):
    with pytest.raises(ValueError):
        Settings(_env_file=None, openrouter_api_key="test", search_provider="typo")


async def test_disabled_search_makes_no_request(config, server):
    config.search_provider = "none"
    node, llm = make_node()
    await node(make_state(task="LangGraph research sources"))
    assert server[1] == []
    assert "Contexte web" not in llm.chat_completion.call_args.kwargs["messages"][-1]["content"]


@pytest.mark.parametrize("mode", ["timeout", "http_error", "rpc_error", "tool_error", "malformed", "missing"])
async def test_failure_keeps_researcher_running_without_fallback(config, server, mode, monkeypatch):
    monkeypatch.setattr(mcp, "PARALLEL_TIMEOUT", 0.5)
    config.search_provider = "parallel"
    config.brave_api_key = "must-not-be-used"
    server[0]["mode"] = mode
    node, llm = make_node()
    result = await node(make_state(task="LangGraph research sources"))
    assert result["research"] == ["Synthèse avec source."]
    assert "Contexte web" not in llm.chat_completion.call_args.kwargs["messages"][-1]["content"]
    assert server[1] and all(c.is_closed for c in server[2])


async def test_whole_mcp_operation_has_deadline(config, server, monkeypatch):
    server[0]["mode"] = "wait"
    monkeypatch.setattr(mcp, "PARALLEL_TIMEOUT", 0.1)
    node, llm = make_node()
    await asyncio.wait_for(node(make_state(task="LangGraph research sources")), timeout=2)
    assert llm.chat_completion.await_count == 1
    assert all(c.is_closed for c in server[2])


async def test_workflow_cancellation_propagates_and_closes_client(config, server):
    server[0]["mode"] = "wait"
    node, llm = make_node()
    task = asyncio.create_task(node(make_state(task="LangGraph research sources")))
    await asyncio.wait_for(server[3].wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    llm.chat_completion.assert_not_awaited()
    assert all(c.is_closed for c in server[2])


async def test_individually_cancelled_tool_is_not_injected_as_context():
    tool = MagicMock()
    tool.run = AsyncMock(side_effect=asyncio.CancelledError())
    registry = mcp.MCPRegistry()
    registry.register(tool)
    with pytest.raises(asyncio.CancelledError):
        await registry.run_all("query")
