"""Tests de l'agent Writer."""

from unittest.mock import AsyncMock

from tests.conftest import make_state


async def test_writer_sets_final_answer():
    from app.agents.writer import make_writer_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "Le RAG est une technique qui..."
    writer_node = make_writer_node(mock_llm)

    result = await writer_node(make_state(research=["Données de recherche."]))

    assert result["final_answer"] == "Le RAG est une technique qui..."


async def test_writer_appends_message():
    from app.agents.writer import make_writer_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "Réponse finale."
    writer_node = make_writer_node(mock_llm)

    result = await writer_node(make_state(research=["..."]))

    assert result["messages"][0]["role"] == "writer"


async def test_writer_uses_smart_model():
    from app.agents.writer import make_writer_node
    from app.core.config import settings

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "Réponse."
    writer_node = make_writer_node(mock_llm)

    await writer_node(make_state(research=["..."]))

    call_args = mock_llm.chat_completion.call_args
    used_model = call_args.kwargs.get("model") or call_args.args[0]
    assert used_model == settings.model_smart


async def test_writer_includes_all_research():
    from app.agents.writer import make_writer_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "Réponse."
    writer_node = make_writer_node(mock_llm)
    state = make_state(research=["Recherche 1.", "Recherche 2."])

    await writer_node(state)

    prompt_user = mock_llm.chat_completion.call_args[1]["messages"][-1]["content"]
    assert "Recherche 1." in prompt_user
    assert "Recherche 2." in prompt_user
