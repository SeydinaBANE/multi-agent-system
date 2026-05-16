"""Tests de l'agent Researcher."""

from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import make_state


def _mock_registry(mcp_results: dict | None = None):
    """Retourne un mock du registre MCP."""
    registry = MagicMock()
    registry.run_all = AsyncMock(return_value=mcp_results or {})
    return registry


@patch("app.agents.researcher.get_registry")
@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_appends_to_research(mock_llm, mock_search, mock_get_registry):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Le RAG combine retrieval et génération."
    mock_get_registry.return_value = _mock_registry()
    state = make_state(research=[])

    result = await researcher_node(state)

    assert len(result["research"]) == 1
    assert result["research"][0] == "Le RAG combine retrieval et génération."


@patch("app.agents.researcher.get_registry")
@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_increments_iteration(mock_llm, mock_search, mock_get_registry):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Réponse."
    mock_get_registry.return_value = _mock_registry()
    result = await researcher_node(make_state(iterations=0))

    assert result["iterations"] == 1


@patch("app.agents.researcher.get_registry")
@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_includes_critique_on_second_pass(mock_llm, mock_search, mock_get_registry):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Réponse enrichie."
    mock_get_registry.return_value = _mock_registry()
    state = make_state(critique="REVISION_NEEDED: ajoute des exemples concrets", iterations=1)

    await researcher_node(state)

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "ajoute des exemples concrets" in prompt_user


@patch("app.agents.researcher.get_registry")
@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_uses_rag_context(mock_llm, mock_search, mock_get_registry):
    from app.agents.researcher import researcher_node

    mock_search.return_value = ["Document RAG pertinent."]
    mock_llm.return_value = "Réponse."
    mock_get_registry.return_value = _mock_registry()

    await researcher_node(make_state())

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "Document RAG pertinent." in prompt_user


@patch("app.agents.researcher.get_registry")
@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_injects_mcp_results_in_prompt(mock_llm, mock_search, mock_get_registry):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Réponse avec web."
    mock_get_registry.return_value = _mock_registry({"brave_search": "Résultat Brave Search pertinent."})

    await researcher_node(make_state())

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "Résultat Brave Search pertinent." in prompt_user
    assert "brave_search" in prompt_user


@patch("app.agents.researcher.get_registry")
@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_works_without_mcp(mock_llm, mock_search, mock_get_registry):
    from app.agents.researcher import researcher_node

    mock_search.return_value = ["Contexte RAG."]
    mock_llm.return_value = "Réponse sans web."
    mock_get_registry.return_value = _mock_registry({})  # aucun outil MCP

    result = await researcher_node(make_state())

    assert result["research"][0] == "Réponse sans web."
    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "Contexte web" not in prompt_user
