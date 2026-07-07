"""Tests de l'agent Critic."""

from unittest.mock import AsyncMock

from tests.conftest import make_state


async def test_critic_stores_critique():
    from app.agents.critic import make_critic_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "APPROVED: recherche complète."
    critic_node = make_critic_node(mock_llm)

    result = await critic_node(make_state(research=["Synthèse RAG."]))

    assert result["critique"] == "APPROVED: recherche complète."


async def test_critic_emits_revision_needed():
    from app.agents.critic import make_critic_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "REVISION_NEEDED: manque des exemples."
    critic_node = make_critic_node(mock_llm)

    result = await critic_node(make_state(research=["Synthèse trop courte."]))

    assert "REVISION_NEEDED" in result["critique"]


async def test_critic_appends_message():
    from app.agents.critic import make_critic_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "APPROVED: ok."
    critic_node = make_critic_node(mock_llm)

    result = await critic_node(make_state(research=["..."]))

    assert result["messages"][0]["role"] == "critic"


async def test_critic_joins_multiple_research_entries():
    from app.agents.critic import make_critic_node

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "APPROVED: ok."
    critic_node = make_critic_node(mock_llm)
    state = make_state(research=["Partie 1.", "Partie 2."])

    await critic_node(state)

    prompt_user = mock_llm.chat_completion.call_args[1]["messages"][-1]["content"]
    assert "Partie 1." in prompt_user
    assert "Partie 2." in prompt_user
