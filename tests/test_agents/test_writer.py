"""Tests de l'agent Writer."""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_state


@patch("app.agents.writer.chat_completion", new_callable=AsyncMock)
async def test_writer_sets_final_answer(mock_llm):
    from app.agents.writer import writer_node

    mock_llm.return_value = "Le RAG est une technique qui..."
    result = await writer_node(make_state(research=["Données de recherche."]))

    assert result["final_answer"] == "Le RAG est une technique qui..."


@patch("app.agents.writer.chat_completion", new_callable=AsyncMock)
async def test_writer_appends_message(mock_llm):
    from app.agents.writer import writer_node

    mock_llm.return_value = "Réponse finale."
    result = await writer_node(make_state(research=["..."]))

    assert result["messages"][0]["role"] == "writer"


@patch("app.agents.writer.chat_completion", new_callable=AsyncMock)
async def test_writer_uses_smart_model(mock_llm):
    from app.agents.writer import writer_node
    from app.core.config import settings

    mock_llm.return_value = "Réponse."
    await writer_node(make_state(research=["..."]))

    call_args = mock_llm.call_args
    used_model = call_args.kwargs.get("model") or call_args.args[0]
    assert used_model == settings.model_smart


@patch("app.agents.writer.chat_completion", new_callable=AsyncMock)
async def test_writer_includes_all_research(mock_llm):
    from app.agents.writer import writer_node

    mock_llm.return_value = "Réponse."
    state = make_state(research=["Recherche 1.", "Recherche 2."])

    await writer_node(state)

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "Recherche 1." in prompt_user
    assert "Recherche 2." in prompt_user
