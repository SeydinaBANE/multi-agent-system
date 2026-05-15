# Multi-Agent System

Pipeline multi-agents orchestré par **LangGraph**, exposé via **FastAPI**, avec streaming WebSocket temps réel via **Redis pub/sub**.

## Architecture

```
FastAPI (REST + WebSocket)
    └── LangGraph Orchestrateur
            ├── Agent Planner     → décompose la tâche (modèle fast)
            ├── Agent Researcher  → collecte via RAG + LLM (modèle default)
            ├── Agent Critic      → évalue la qualité (modèle fast)
            └── Agent Writer      → rédige la réponse finale (modèle smart)

Services :
  OpenRouter  → broker LLM (Claude Haiku 4.5 par défaut)
  PostgreSQL  → persistance conversations et runs
  Redis       → pub/sub pour le streaming WebSocket temps réel
  Qdrant      → mémoire vectorielle pour le RAG
```

## Démarrage rapide

```bash
# 1. Copier les variables d'environnement
cp .env.example .env
# → Renseigner OPENROUTER_API_KEY dans .env

# 2. Lancer tous les services
docker compose up -d

# 3. L'API est disponible sur http://localhost:8000
# Documentation interactive : http://localhost:8000/docs
```

## Utilisation

### Ingérer des documents dans le RAG
```bash
# Document unique
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{"text": "Le RAG combine recherche vectorielle et génération LLM.", "id": "doc-1"}'

# Lot de documents
curl -X POST http://localhost:8000/api/v1/documents/batch \
  -H "Content-Type: application/json" \
  -d '{"documents": [{"text": "...", "id": "doc-2"}, {"text": "...", "id": "doc-3"}]}'
```

### REST — lancer un workflow
```bash
curl -X POST http://localhost:8000/api/v1/run \
  -H "Content-Type: application/json" \
  -d '{"task": "Explique les avantages du RAG vs fine-tuning", "session_id": "session-1"}'
```

### REST — historique d'une session
```bash
curl http://localhost:8000/api/v1/sessions/session-1/runs
```

### WebSocket — streaming temps réel
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/run");

ws.onopen = () => ws.send(JSON.stringify({
  task: "Analyse les tendances IA en 2025",
  session_id: "session-2"
}));

ws.onmessage = (e) => {
  const event = JSON.parse(e.data);
  // event.type: "agent_start" | "token" | "agent_done" | "done" | "error"
  console.log(event);
};
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest              # 46 tests, ~0.2s
pytest -v           # détail par test
```

## Structure du projet

```
├── app/
│   ├── main.py                  # Point d'entrée FastAPI + lifespan
│   ├── agents/
│   │   ├── state.py             # AgentState TypedDict (partagé entre agents)
│   │   ├── orchestrator.py      # Graph LangGraph + stream_and_publish
│   │   ├── planner.py           # Agent 1 : décomposition
│   │   ├── researcher.py        # Agent 2 : recherche + RAG
│   │   ├── critic.py            # Agent 3 : évaluation qualité
│   │   └── writer.py            # Agent 4 : rédaction finale
│   ├── api/
│   │   ├── routes.py            # POST /run, GET /sessions/{id}/runs
│   │   ├── documents.py         # POST /documents, POST /documents/batch
│   │   └── websocket.py         # Streaming WebSocket via Redis pub/sub
│   ├── core/
│   │   └── config.py            # Configuration pydantic-settings
│   ├── services/
│   │   ├── llm.py               # Wrapper OpenRouter (chat + embed)
│   │   ├── vector_store.py      # Client Qdrant
│   │   └── cache.py             # Client Redis pub/sub
│   └── db/
│       ├── models.py            # Modèles SQLAlchemy (Conversation, Run)
│       └── session.py           # Engine async + get_session
├── tests/
│   ├── conftest.py              # Fixtures partagées (client HTTP, mock DB)
│   ├── test_agents/             # Tests unitaires des 4 agents + orchestrateur
│   └── test_api/                # Tests endpoints REST, documents, WebSocket
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── requirements-dev.txt
```

## Ce qui rend ce projet intéressant pour un recruteur

| Point fort | Détail |
|---|---|
| **Multi-agent avec feedback loop** | Le Critic peut renvoyer au Researcher jusqu'à 2x |
| **Streaming Redis pub/sub** | Découple pipeline et client — N abonnés simultanés possibles |
| **RAG opérationnel** | Qdrant + embeddings OpenRouter + endpoint d'ingestion |
| **Routing LLM intelligent** | Modèle cheap pour Planner/Critic, smart pour Writer |
| **Checkpointing LangGraph** | État persisté entre requêtes via session_id |
| **Stack production-ready** | Docker Compose, health checks, async partout, 46 tests |
