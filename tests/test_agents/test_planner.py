"""Tests de l'agent Planner."""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_state


@patch("app.agents.planner.chat_completion", new_callable=AsyncMock)
async def test_planner_splits_response_into_steps(mock_llm):
    from app.agents.planner import planner_node

    mock_llm.return_value = "1. Définir le RAG\n2. Expliquer la recherche vectorielle\n3. Comparer au fine-tuning"
    state = make_state(plan=[])

    result = await planner_node(state)

    assert len(result["plan"]) == 3
    assert result["plan"][0] == "1. Définir le RAG"


@patch("app.agents.planner.chat_completion", new_callable=AsyncMock)
async def test_planner_ignores_blank_lines(mock_llm):
    from app.agents.planner import planner_node

    mock_llm.return_value = "1. Étape A\n\n2. Étape B\n"
    result = await planner_node(make_state(plan=[]))

    assert len(result["plan"]) == 2


@patch("app.agents.planner.chat_completion", new_callable=AsyncMock)
async def test_planner_appends_message(mock_llm):
    from app.agents.planner import planner_node

    mock_llm.return_value = "1. Seule étape"
    result = await planner_node(make_state(plan=[]))

    assert len(result["messages"]) == 1
    assert result["messages"][0]["role"] == "planner"


@patch("app.agents.planner.chat_completion", new_callable=AsyncMock)
async def test_planner_uses_fast_model(mock_llm):
    from app.agents.planner import planner_node
    from app.core.config import settings

    mock_llm.return_value = "1. Step"
    await planner_node(make_state(plan=[]))

    call_args = mock_llm.call_args
    used_model = call_args.kwargs.get("model") or call_args.args[0]
    assert used_model == settings.model_fast
