"""Tests du classifieur de routage chat/pipeline."""

from unittest.mock import AsyncMock, patch


@patch("app.agents.router.chat_completion", new_callable=AsyncMock)
async def test_classify_returns_chat_for_greeting(mock_llm):
    from app.agents.router import classify

    mock_llm.return_value = "chat"
    mode = await classify("Bonjour !")
    assert mode == "chat"


@patch("app.agents.router.chat_completion", new_callable=AsyncMock)
async def test_classify_returns_pipeline_for_research(mock_llm):
    from app.agents.router import classify

    mock_llm.return_value = "pipeline"
    mode = await classify("Rédige un rapport comparatif sur RAG vs fine-tuning.")
    assert mode == "pipeline"


@patch("app.agents.router.chat_completion", new_callable=AsyncMock)
async def test_classify_first_word_parsing(mock_llm):
    """Le parser ne doit pas se laisser tromper par 'chat' ailleurs dans la réponse."""
    from app.agents.router import classify

    mock_llm.return_value = "pipeline — cette question dépasse un simple chat"
    mode = await classify("Analyse les tendances IA en 2025")
    assert mode == "pipeline"


@patch("app.agents.router.chat_completion", new_callable=AsyncMock)
async def test_classify_fallback_on_exception(mock_llm):
    """En cas d'erreur LLM, le router doit retourner 'chat' (fallback rapide)."""
    from app.agents.router import classify

    mock_llm.side_effect = RuntimeError("OpenRouter down")
    mode = await classify("Bonjour")
    assert mode == "chat"


@patch("app.agents.router.chat_completion", new_callable=AsyncMock)
async def test_classify_chat_when_llm_says_only_chat(mock_llm):
    from app.agents.router import classify

    mock_llm.return_value = "chat\n"
    mode = await classify("C'est quoi Python ?")
    assert mode == "chat"
