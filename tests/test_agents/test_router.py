"""Tests du classifieur de routage chat/pipeline."""

from unittest.mock import AsyncMock


async def test_classify_returns_chat_for_greeting():
    from app.agents.router import make_classifier

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "chat"
    classify = make_classifier(mock_llm)

    mode = await classify("Bonjour !")
    assert mode == "chat"


async def test_classify_returns_pipeline_for_research():
    from app.agents.router import make_classifier

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "pipeline"
    classify = make_classifier(mock_llm)

    mode = await classify("Rédige un rapport comparatif sur RAG vs fine-tuning.")
    assert mode == "pipeline"


async def test_classify_first_word_parsing():
    """Le parser ne doit pas se laisser tromper par 'chat' ailleurs dans la réponse."""
    from app.agents.router import make_classifier

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "pipeline — cette question dépasse un simple chat"
    classify = make_classifier(mock_llm)

    mode = await classify("Analyse les tendances IA en 2025")
    assert mode == "pipeline"


async def test_classify_fallback_on_exception():
    """En cas d'erreur LLM, le router doit retourner 'chat' (fallback rapide)."""
    from app.agents.router import make_classifier

    mock_llm = AsyncMock()
    mock_llm.chat_completion.side_effect = RuntimeError("OpenRouter down")
    classify = make_classifier(mock_llm)

    mode = await classify("Bonjour")
    assert mode == "chat"


async def test_classify_chat_when_llm_says_only_chat():
    from app.agents.router import make_classifier

    mock_llm = AsyncMock()
    mock_llm.chat_completion.return_value = "chat\n"
    classify = make_classifier(mock_llm)

    mode = await classify("C'est quoi Python ?")
    assert mode == "chat"
