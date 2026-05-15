# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
cp .env.example .env          # puis renseigner OPENROUTER_API_KEY

# Lancer tous les services (hot-reload activé via volume mount)
docker compose up -d

# Tests (hors Docker)
pip install -r requirements-dev.txt
pytest                        # tous les tests
pytest tests/test_agents/ -v  # un dossier précis
pytest tests/test_agents/test_orchestrator.py::test_should_revise_when_revision_needed_and_under_limit -v

# API
# http://localhost:8000/docs  — Swagger interactif
# http://localhost:8000/health
```

## Architecture

Pipeline 4-agents orchestré par **LangGraph**, exposé via **FastAPI** (REST + WebSocket).

```
planner → researcher → critic ──(REVISION_NEEDED + iter < 2)──→ researcher
                                └──(otherwise)──────────────────→ writer → END
```

- **Planner** — décompose la tâche en étapes (`model_fast`)
- **Researcher** — RAG (Qdrant) + LLM (`model_default`) ; intègre le feedback du Critic au 2e passage
- **Critic** — évalue ; émet `REVISION_NEEDED:` ou `APPROVED:` (`model_fast`)
- **Writer** — rédige la réponse finale (`model_smart`)

La boucle est limitée à 2 itérations (`state["iteration"] < 2` dans `should_revise`).

### AgentState

Défini dans `app/agents/state.py` (séparé de l'orchestrateur pour éviter l'import circulaire) :

```python
task, plan, research, critique, final_answer, iteration, messages
```

`messages` est `Annotated[list, operator.add]` — chaque agent appende, n'écrase jamais.

### Streaming WebSocket via Redis pub/sub

```
Client WS → subscribe("run:{session_id}")
          → asyncio.create_task(stream_and_publish)
                └→ stream_workflow → LangGraph astream_events v2
                └→ publish("run:{session_id}", json_event)
          → pubsub.listen() → send_json au client
          → reçoit {"type":"done"} → break
```

`_format_langgraph_event` dans `orchestrator.py` convertit les événements LangGraph bruts en `agent_start | token | agent_done | done | error`.

### Services

| Service | Rôle | Port |
|---|---|---|
| FastAPI (uvicorn) | REST + WebSocket | 8000 |
| PostgreSQL 16 | Persistance `conversations` + `runs` | 5432 |
| Redis 7 | Pub/sub pour le streaming WebSocket | 6379 |
| Qdrant | Mémoire vectorielle RAG (collection `research_memory`, dim 1536) | 6333 |
| OpenRouter | Broker LLM — modèle par défaut : `anthropic/claude-haiku-4-5` | external |

### Key files

- `app/agents/state.py` — `AgentState` TypedDict
- `app/agents/orchestrator.py` — graph LangGraph, `should_revise`, `stream_and_publish`
- `app/api/routes.py` — `POST /api/v1/run`, `GET /api/v1/sessions/{id}/runs`
- `app/api/documents.py` — `POST /api/v1/documents`, `POST /api/v1/documents/batch`
- `app/api/websocket.py` — handler WebSocket, souscription Redis
- `app/services/llm.py` — `chat_completion` + `embed` via OpenRouter
- `app/services/vector_store.py` — `search` + `upsert` Qdrant
- `app/services/cache.py` — `publish` + `subscribe` Redis
- `app/db/session.py` — engine async, `init_db()` (appelé au lifespan), `get_session` Depends
- `app/core/config.py` — `Settings` pydantic-settings (`model_fast`, `model_default`, `model_smart`)

### Checkpointing

`MemorySaver` en dev. Pour la prod, remplacer `_checkpointer` dans `orchestrator.py` par un checkpointer PostgreSQL.

### Tests

46 tests, 0 warning. Chaque agent est testé avec `chat_completion` mocké. Les endpoints API utilisent `app.dependency_overrides[get_session]` pour isoler la base. `stream_and_publish` est testé en mockant `stream_workflow` comme async generator.
