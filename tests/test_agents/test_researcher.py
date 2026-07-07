"""Tests de l'agent Researcher."""

from unittest.mock import AsyncMock, MagicMock

from tests.conftest import make_state


def _mock_registry(mcp_results: dict | None = None):
    """Retourne un mock du registre MCP."""
    registry = MagicMock()
    registry.run_all = AsyncMock(return_value=mcp_results or {})
    return registry


def _make_node(llm_response: str, rag_hits: list[str] | None = None, mcp_results: dict | None = None):
    from app.agents.researcher import make_researcher_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = llm_response
    mock_vector_store = AsyncMock()
    mock_vector_store.search.return_value = rag_hits or []
    mock_registry = _mock_registry(mcp_results)
    return make_researcher_node(mock_llm, mock_vector_store, mock_registry), mock_llm


async def test_researcher_appends_to_research():
    node, _ = _make_node("Le RAG combine retrieval et génération.")
    state = make_state(research=[])

    result = await node(state)

    assert len(result["research"]) == 1
    assert result["research"][0] == "Le RAG combine retrieval et génération."


async def test_researcher_increments_iteration():
    node, _ = _make_node("Réponse.")

    result = await node(make_state(iterations=0))

    assert result["iterations"] == 1


async def test_researcher_includes_critique_on_second_pass():
    node, mock_llm = _make_node("Réponse enrichie.")
    state = make_state(critique="REVISION_NEEDED: ajoute des exemples concrets", iterations=1)

    await node(state)

    prompt_user = mock_llm.chat_completion.call_args[1]["messages"][-1]["content"]
    assert "ajoute des exemples concrets" in prompt_user


async def test_researcher_uses_rag_context():
    node, mock_llm = _make_node("Réponse.", rag_hits=["Document RAG pertinent."])

    await node(make_state())

    prompt_user = mock_llm.chat_completion.call_args[1]["messages"][-1]["content"]
    assert "Document RAG pertinent." in prompt_user


async def test_researcher_injects_mcp_results_in_prompt():
    node, mock_llm = _make_node(
        "Réponse avec web.",
        mcp_results={"brave_search": "Résultat Brave Search pertinent."},
    )

    await node(make_state())

    prompt_user = mock_llm.chat_completion.call_args[1]["messages"][-1]["content"]
    assert "Résultat Brave Search pertinent." in prompt_user
    assert "brave_search" in prompt_user


async def test_researcher_works_without_mcp():
    node, mock_llm = _make_node(
        "Réponse sans web.",
        rag_hits=["Contexte RAG."],
        mcp_results={},
    )

    result = await node(make_state())

    assert result["research"][0] == "Réponse sans web."
    prompt_user = mock_llm.chat_completion.call_args[1]["messages"][-1]["content"]
    assert "Contexte web" not in prompt_user
