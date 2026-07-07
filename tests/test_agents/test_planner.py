"""Tests de l'agent Planner."""

from unittest.mock import AsyncMock

from tests.conftest import make_state


async def test_planner_splits_response_into_steps():
    from app.agents.planner import make_planner_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "1. Définir le RAG\n2. Expliquer la recherche vectorielle\n3. Comparer au fine-tuning"
    planner_node = make_planner_node(mock_llm)

    result = await planner_node(make_state(plan=[]))

    assert len(result["plan"]) == 3
    assert result["plan"][0] == "1. Définir le RAG"


async def test_planner_ignores_blank_lines():
    from app.agents.planner import make_planner_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "1. Étape A\n\n2. Étape B\n"
    planner_node = make_planner_node(mock_llm)

    result = await planner_node(make_state(plan=[]))

    assert len(result["plan"]) == 2


async def test_planner_appends_message():
    from app.agents.planner import make_planner_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "1. Seule étape"
    planner_node = make_planner_node(mock_llm)

    result = await planner_node(make_state(plan=[]))

    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "planner"


async def test_planner_uses_fast_model():
    from app.agents.planner import make_planner_node
    from app.core.config import settings

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "1. Step"
    planner_node = make_planner_node(mock_llm)

    await planner_node(make_state(plan=[]))

    call_args = mock_llm.chat_completion.call_args
    used_model = call_args.kwargs.get("model") or call_args.args[0]
    assert used_model == settings.model_fast
