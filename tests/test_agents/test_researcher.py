"""Tests de l'agent Researcher."""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_state


@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_appends_to_research(mock_llm, mock_search):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Le RAG combine retrieval et génération."
    state = make_state(research=[])

    result = await researcher_node(state)

    assert len(result["research"]) == 1
    assert result["research"][0] == "Le RAG combine retrieval et génération."


@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_increments_iteration(mock_llm, mock_search):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Réponse."
    result = await researcher_node(make_state(iteration=0))

    assert result["iteration"] == 1


@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_includes_critique_on_second_pass(mock_llm, mock_search):
    from app.agents.researcher import researcher_node

    mock_search.return_value = []
    mock_llm.return_value = "Réponse enrichie."
    state = make_state(critique="REVISION_NEEDED: ajoute des exemples concrets", iteration=1)

    await researcher_node(state)

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "ajoute des exemples concrets" in prompt_user


@patch("app.agents.researcher.search", new_callable=AsyncMock)
@patch("app.agents.researcher.chat_completion", new_callable=AsyncMock)
async def test_researcher_uses_rag_context(mock_llm, mock_search):
    from app.agents.researcher import researcher_node

    mock_search.return_value = ["Document RAG pertinent."]
    mock_llm.return_value = "Réponse."

    await researcher_node(make_state())

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "Document RAG pertinent." in prompt_user
