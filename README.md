# Sovereign AI Core

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-orange)
![License](https://img.shields.io/badge/license-MIT-green)
![Ollama](https://img.shields.io/badge/LLM-Ollama-black?logo=ollama)

A **local-first, air-gapped AI platform** that routes queries to local LLMs via [Ollama](https://ollama.com), augments them with a local ChromaDB RAG engine, stores sensitive data in an AES-256 encrypted vault, and exposes everything through a FastAPI gateway — with a network kill-switch to enforce total data isolation.

No data ever leaves your machine.

---

## What It Does

Sovereign AI Core is a self-contained inference stack for teams and individuals who need AI capabilities without sending data to cloud providers.

```
User Query
    │
    ▼
FastAPI Gateway  ──(API key auth)──►  /ai/query
    │
    ├── RAG Engine (ChromaDB + sentence-transformers)
    │       └── retrieves relevant local documents
    │
    ├── Model Router
    │       └── forwards augmented prompt → Ollama (loopback)
    │
    └── Encrypted Vault (AES-256 / Fernet)
            └── persists keys and sensitive payloads locally
```

The **air-gap kill-switch** monkey-patches `socket.socket` at the OS level so that, when engaged, no library anywhere in the process can open an outbound connection.

---

## Features

- **Local-first inference** — connects only to `127.0.0.1:11434` (Ollama). No cloud API keys required.
- **ChromaDB RAG engine** — indexes your documents with `all-MiniLM-L6-v2` embeddings entirely on-device.
- **AES-256 encrypted vault** — Fernet-based encryption for any sensitive payload; key stored in a local file with `0600` permissions.
- **Air-gap kill-switch** — `/system/lock` blocks every outbound socket at the Python runtime level and logs all blocked attempts.
- **Multi-tier model routing** — `lite` (phi3), `standard` (llama3), and `frontier` (mixtral) profiles configurable via environment variables.
- **API key authentication** — all sensitive endpoints protected with a header-based key.
- **Local SQLite audit log** — every query is hashed and stored locally for compliance.
- **Docker-ready** — one `docker-compose up` starts the API and a local Ollama container.
- **Portable** — zero hardcoded paths; all storage rooted under a configurable `SOVEREIGN_DATA_DIR`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API Gateway | FastAPI + Uvicorn |
| LLM Backend | Ollama (Llama 3, Phi-3, Mixtral) |
| Vector Store | ChromaDB (persistent, local) |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` |
| Encryption | cryptography (Fernet / AES-256) |
| ORM / DB | SQLModel + SQLite |
| HTTP Client | httpx (async) |
| Config | pydantic-settings + `.env` |
| Tests | pytest |
| Container | Docker + docker-compose |

---

## Installation

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- At least one model pulled, e.g. `ollama pull llama3`

### Local setup

```bash
# 1. Clone
git clone https://github.com/Dhanush-Aries/sovereign-ai-core.git
cd sovereign-ai-core

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Edit .env — set SOVEREIGN_API_KEY and confirm OLLAMA_BASE_URL

# 5. Run
python main.py
# or: uvicorn main:app --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive docs: `http://127.0.0.1:8000/docs`

### Docker setup

```bash
cp .env.example .env
# Edit .env as above

docker-compose up --build -d

# Pull a model into the Ollama container
docker exec sovereign-ollama ollama pull llama3
```

---

## Usage

All protected endpoints require the `X-Sovereign-API-Key` header.

### Query the local LLM

```bash
curl -X POST http://127.0.0.1:8000/ai/query \
  -H "Content-Type: application/json" \
  -H "X-Sovereign-API-Key: your-api-key" \
  -d '{
    "prompt": "Summarise the key principles of zero-trust security.",
    "complexity": "standard",
    "use_rag": false
  }'
```

```json
{
  "response": "Zero-trust security assumes no implicit trust ...",
  "model": "llama3",
  "rag_context_used": false,
  "context_chunks": 0,
  "source": "local-sovereign-core"
}
```

### Ingest a document for RAG

```bash
curl -X POST http://127.0.0.1:8000/rag/ingest \
  -H "Content-Type: application/json" \
  -H "X-Sovereign-API-Key: your-api-key" \
  -d '{
    "doc_id": "policy-001",
    "text": "Our data retention policy requires all logs to be purged after 90 days.",
    "metadata": {"source": "internal-policy", "version": "2024-Q1"}
  }'
```

Now queries about data retention will retrieve this context automatically.

### Search the vector store

```bash
curl "http://127.0.0.1:8000/rag/search?query=data+retention&top_k=3" \
  -H "X-Sovereign-API-Key: your-api-key"
```

### Encrypt / decrypt a secret

```bash
# Encrypt
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/vault/encrypt \
  -H "Content-Type: application/json" \
  -H "X-Sovereign-API-Key: your-api-key" \
  -d '{"plaintext": "super-secret-value"}' | jq -r .token)

# Decrypt
curl -X POST http://127.0.0.1:8000/vault/decrypt \
  -H "Content-Type: application/json" \
  -H "X-Sovereign-API-Key: your-api-key" \
  -d "{\"token\": \"$TOKEN\"}"
```

### Engage the air-gap kill-switch

```bash
# Lock — blocks all outbound sockets
curl -X POST http://127.0.0.1:8000/system/lock \
  -H "X-Sovereign-API-Key: your-api-key"

# Unlock
curl -X POST http://127.0.0.1:8000/system/unlock \
  -H "X-Sovereign-API-Key: your-api-key"

# Check status
curl http://127.0.0.1:8000/system/status \
  -H "X-Sovereign-API-Key: your-api-key"
```

---

## Configuration

All configuration is read from environment variables (or `.env`).

| Variable | Default | Description |
|---|---|---|
| `SOVEREIGN_API_KEY` | `dev-insecure-key-change-me` | Secret for `X-Sovereign-API-Key` header |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | URL of the running Ollama instance |
| `LITE_MODEL` | `phi3` | Model name for `complexity=lite` |
| `STANDARD_MODEL` | `llama3` | Model name for `complexity=standard` |
| `FRONTIER_MODEL` | `mixtral` | Model name for `complexity=frontier` |
| `SOVEREIGN_DATA_DIR` | `<project-root>/.sovereign` | Root for vault, vector store, and DB |
| `HOST` | `127.0.0.1` | Bind address for uvicorn |
| `PORT` | `8000` | Listen port |

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## Project Structure

```
sovereign-ai-core/
├── main.py                        # Entry point (uvicorn launcher)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── backend/
│   └── app/
│       ├── config.py              # Pydantic-settings configuration
│       ├── core/
│       │   ├── air_gap.py         # Network kill-switch
│       │   └── engine.py          # FastAPI app + all route handlers
│       └── vault/
│           └── auth_vault.py      # AES-256 encrypted vault
└── tests/
    ├── test_vault.py
    ├── test_air_gap.py
    └── test_api.py
```

---

## License

MIT — see [LICENSE](LICENSE).
