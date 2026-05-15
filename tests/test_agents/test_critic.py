"""Tests de l'agent Critic."""

from unittest.mock import AsyncMock, patch

from tests.conftest import make_state


@patch("app.agents.critic.chat_completion", new_callable=AsyncMock)
async def test_critic_stores_critique(mock_llm):
    from app.agents.critic import critic_node

    mock_llm.return_value = "APPROVED: recherche complète."
    result = await critic_node(make_state(research=["Synthèse RAG."]))

    assert result["critique"] == "APPROVED: recherche complète."


@patch("app.agents.critic.chat_completion", new_callable=AsyncMock)
async def test_critic_emits_revision_needed(mock_llm):
    from app.agents.critic import critic_node

    mock_llm.return_value = "REVISION_NEEDED: manque des exemples."
    result = await critic_node(make_state(research=["Synthèse trop courte."]))

    assert "REVISION_NEEDED" in result["critique"]


@patch("app.agents.critic.chat_completion", new_callable=AsyncMock)
async def test_critic_appends_message(mock_llm):
    from app.agents.critic import critic_node

    mock_llm.return_value = "APPROVED: ok."
    result = await critic_node(make_state(research=["..."]))

    assert result["messages"][0]["role"] == "critic"


@patch("app.agents.critic.chat_completion", new_callable=AsyncMock)
async def test_critic_joins_multiple_research_entries(mock_llm):
    from app.agents.critic import critic_node

    mock_llm.return_value = "APPROVED: ok."
    state = make_state(research=["Partie 1.", "Partie 2."])

    await critic_node(state)

    prompt_user = mock_llm.call_args[1]["messages"][-1]["content"]
    assert "Partie 1." in prompt_user
    assert "Partie 2." in prompt_user
