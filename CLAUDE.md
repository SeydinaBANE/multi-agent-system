# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
cp .env.example .env          # puis renseigner OPENROUTER_API_KEY

# Services
make up                       # docker compose up -d
make down                     # docker compose down
make logs                     # docker compose logs -f api
make migrate                  # alembic upgrade head (dans le conteneur)
make shell                    # bash dans le conteneur api

# Tests (hors Docker)
pip install -r requirements-dev.txt
pytest                        # 78 tests
pytest tests/test_agents/ -v
pytest tests/test_agents/test_orchestrator.py::test_should_revise_when_revision_needed_and_under_limit -v

# URLs
# http://localhost:3000        — Interface Next.js
# http://localhost:8000        — API FastAPI (ancienne SPA + Swagger)
# http://localhost:8000/docs   — Swagger interactif
# http://localhost:8000/health — Health check
```

## Architecture

### Routage automatique chat / pipeline

Chaque message passe d'abord par un **Router** (LLM rapide) qui décide :

```
Message utilisateur
      ↓
  🔀 Router (model_fast)
      ├── "chat"     → stream_completion (model_smart) — réponse directe streamée
      └── "pipeline" → planner → researcher → critic → writer
```

- **chat** : salutations, questions simples, explications rapides, calculs — réponse directe sans pipeline
- **pipeline** : recherche approfondie, analyse, rapport, raisonnement multi-étapes

L'événement `{"type": "mode", "mode": "chat"|"pipeline"}` est publié en premier sur Redis, le frontend grisce/affiche le pipeline en conséquence.

### Pipeline 4-agents (mode pipeline uniquement)

```
planner → researcher → critic ──(REVISION_NEEDED + iter < 2)──→ researcher
                                └──(otherwise)──────────────────→ writer → END
```

- **Planner** — décompose la tâche en étapes (`model_fast`)
- **Researcher** — RAG (Qdrant) + outils MCP en parallèle + LLM (`model_default`) ; intègre le feedback du Critic au 2e passage
- **Critic** — évalue ; émet `REVISION_NEEDED:` ou `APPROVED:` (`model_fast`)
- **Writer** — rédige la réponse finale (`model_smart`)

La boucle est limitée à 2 itérations (`state["iterations"] < 2` dans `should_revise`).

### AgentState

Défini dans `app/agents/state.py` (séparé de l'orchestrateur pour éviter l'import circulaire) :

```python
task, plan, research, critique, final_answer, iterations, messages
```

`messages` est `Annotated[list, operator.add]` — chaque agent appende, n'écrase jamais.

### Streaming WebSocket via Redis pub/sub

```
Client WS → subscribe("run:{session_id}")
          → asyncio.create_task(stream_and_publish)
                └→ enregistré dans app.state.background_tasks (graceful shutdown)
                └→ classify(task) → "chat" | "pipeline"
                └→ publish({"type":"mode", "mode": ...})
                ├── chat     → stream_completion → tokens → publish
                └── pipeline → stream_workflow (LangGraph astream_events v2) → publish
          → pubsub.listen() → send_json au client
          → reçoit {"type":"done", "final_answer": "...", "iterations": N}
                └→ _persist_run() → PostgreSQL (Conversation + Run)
                └→ break
```

Les tâches WebSocket sont trackées dans `app.state.background_tasks` — le lifespan les attend au shutdown pour garantir que `_persist_run()` se termine même si le client se déconnecte.

### Ingestion RAG — 4 sources

| Endpoint | Source | Parsing |
|---|---|---|
| `POST /api/v1/documents` | Texte brut JSON | — |
| `POST /api/v1/documents/batch` | Lot de textes JSON | — |
| `POST /api/v1/documents/upload` | Fichier multipart | pdfplumber (PDF), python-docx (DOCX), UTF-8 (TXT) |
| `POST /api/v1/documents/url` | URL JSON | httpx + BeautifulSoup + lxml |

### Services

| Service | Rôle | Port |
|---|---|---|
| Next.js 14 | Frontend (App Router + Tailwind + TypeScript) | 3000 |
| FastAPI (uvicorn) | REST + WebSocket | 8000 |
| PostgreSQL 16 | Persistance `conversations` + `runs` | 5432 |
| Redis 7 | Pub/sub pour le streaming WebSocket | 6379 |
| Qdrant | Mémoire vectorielle RAG (collection `research_memory`, dim 1536) | 6333 |
| Adminer | Interface web PostgreSQL | 8080 |
| RedisInsight | Interface web Redis | 5540 |
| OpenRouter | Broker LLM — modèle par défaut : `anthropic/claude-haiku-4-5` | external |

### Key files

- `frontend-next/src/app/page.tsx` — page principale Next.js (state, WS, routing mode)
- `frontend-next/src/components/` — Pipeline, ChatArea, Sidebar, DocumentUpload
- `app/agents/router.py` — `classify(task) -> "chat" | "pipeline"` via LLM rapide
- `app/agents/state.py` — `AgentState` TypedDict
- `app/agents/orchestrator.py` — `stream_and_publish`, `_stream_direct_chat`, `_stream_pipeline`
- `app/api/routes.py` — `POST /api/v1/run`, `GET /api/v1/sessions/{id}/runs`
- `app/api/documents.py` — ingestion texte + fichier + URL
- `app/api/websocket.py` — handler WebSocket, `_persist_run`, souscription Redis
- `app/services/llm.py` — `chat_completion` + `stream_completion` + `embed` via OpenRouter
- `app/services/document_parser.py` — extraction texte PDF/DOCX/TXT/URL
- `app/services/vector_store.py` — `search` (via `query_points`) + `upsert` Qdrant (qdrant-client >= 1.7)
- `app/services/cache.py` — `publish` + `subscribe` Redis
- `app/services/mcp_client.py` — `MCPTool` ABC + `MCPRegistry` + `BraveSearchTool` ; `setup_mcp()` / `close_mcp()` appelés au lifespan
- `app/db/session.py` — engine async, `init_db()` (lifespan), `get_session` Depends
- `app/core/config.py` — `Settings` pydantic-settings (`model_fast`, `model_default`, `model_smart`)
- `app/core/logging.py` — structlog — logs structurés dans chaque agent et route
- `alembic/versions/0001_initial_schema.py` — migration initiale (`conversations` + `runs`)

### Alembic — note déploiement

`alembic.ini` contient `prepend_sys_path = .` (requis pour que `from app.core.config import settings` fonctionne dans le conteneur Docker).

Si la DB a été initialisée par `init_db()` avant la première migration, utiliser `alembic stamp head` pour synchroniser Alembic sans rejouer le DDL.

### MCP — Outils externes

`MCPRegistry` dans `app/services/mcp_client.py` — registre extensible d'outils appelés en parallèle dans le Researcher.

**Ajouter un outil :** créer une classe `MCPTool` + `registry.register(MonOutil())` dans `setup_mcp()`.

**Brave Search :** activé si `BRAVE_API_KEY` est renseignée dans `.env` — ignoré sinon.

**Garanties :** outil absent → ignoré au démarrage. Outil qui plante → `log.warning`, pipeline continue.

### Checkpointing

`AsyncPostgresSaver` (psycopg3 + `AsyncConnectionPool`) initialisé dans le lifespan FastAPI via `setup_checkpointer()`. Le graph est précompilé avec le bon checkpointer avant la première requête. Fallback automatique vers `MemorySaver` si psycopg3 est absent (tests unitaires).

### Frontend Next.js

App Router (`src/app/`), composants client (`'use client'`), Tailwind CSS, TypeScript.
Connexion WebSocket auto-reconnectée toutes les 3s. URL API configurée via `NEXT_PUBLIC_API_URL` (défaut : `http://localhost:8000`).
En prod VPS : renseigner `VPS_IP` dans `.env` pour le build Docker du frontend.

### Tests

78 tests, 0 warning. Chaque agent est testé avec `chat_completion` mocké. Les endpoints API utilisent `app.dependency_overrides[get_session]` pour isoler la base. `stream_and_publish` est testé en mockant `stream_workflow` comme async generator. `_load_chat_history`, `_persist_run` et le fallback `setup_checkpointer` sont testés avec `AsyncSessionLocal` mocké. `MCPRegistry`, `BraveSearchTool` et l'intégration Researcher/MCP sont testés dans `tests/test_services/test_mcp_client.py`. Le CI GitHub Actions lance les tests sur Python 3.11 et 3.12 à chaque push.
