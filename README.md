# Sovereign AI Core

**Local LLM + local RAG + encrypted vault + kill-switch. Zero cloud calls.**

<!-- hero: 1600x600 diagram of the air-gapped inference stack -->

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![Ollama](https://img.shields.io/badge/LLM-Ollama-000000?logo=ollama&logoColor=white)
![ChromaDB](https://img.shields.io/badge/RAG-ChromaDB-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

A local-first, air-gapped AI platform. Routes queries to Ollama, retrieves context from a local ChromaDB, stores sensitive data in an AES-256 encrypted vault, exposes a FastAPI gateway — and can flip a network kill-switch to guarantee no data ever leaves the box.

---

## Why this exists

You can't run a hospital, a law firm, or an internal HR chatbot on hosted APIs — the data can't leave the premises. Sovereign AI Core is what that deployment actually looks like: local model, local retrieval, encrypted storage, one API key for the front door, and a hard network guard rail so misconfiguration can't leak. Not "privacy-conscious" — actually air-gapped.

---

## Try it in 60 seconds

```bash
git clone https://github.com/Danush-Aries/sovereign-ai-core
cd sovereign-ai-core
docker compose up --build
```

Ollama pulls a model, ChromaDB starts, FastAPI comes up at http://localhost:8080. Query:

```bash
curl -H "X-API-Key: $KEY" -X POST http://localhost:8080/ai/query \
  -d '{"query":"summarise the intake document"}'
```

---

## How it works

```
User Query
    |
    v
FastAPI Gateway --(API key auth)--> /ai/query
    |
    +-- RAG Engine (ChromaDB + sentence-transformers)
    |       retrieves relevant local docs
    |
    +-- Model Router
    |       augmented prompt -> Ollama (loopback)
    |
    +-- Encrypted Vault (AES-256)
    |       sensitive PII / secrets storage
    |
    +-- Kill-switch
            iptables egress guard
            enforces network isolation
```

Every layer is optional but they compose — the kill-switch works whether or not RAG is on, RAG works with any Ollama model, the vault is a standalone key-value API.

---

## Screenshots

<!-- screenshot: architecture.png -->
<!-- screenshot: killswitch-status.png -->

---

## Stack

| Layer | Tech |
|---|---|
| Gateway | FastAPI + Uvicorn (API-key auth) |
| LLM | Ollama (any local model) |
| RAG | ChromaDB + sentence-transformers |
| Vault | AES-256 encrypted key-value store |
| Isolation | iptables egress kill-switch |
| Deploy | docker-compose |

---

## More from Danush

Part of a broader stack of AI + security tooling:

- [jarvis](https://github.com/Danush-Aries/jarvis) — portable multi-provider AI assistant (voice/web/CLI)
- [breachintel](https://github.com/Danush-Aries/breachintel) — OSINT breach intelligence aggregator
- [cve-advisor](https://github.com/Danush-Aries/cve-advisor) — AI-powered CVE triage and patch recommendation
- [llm-fragility-lab](https://github.com/Danush-Aries/llm-fragility-lab) — adversarial testing lab for LLM robustness
- [network-intrusion-analyzer](https://github.com/Danush-Aries/network-intrusion-analyzer) — Suricata + Claude AI intrusion triage
- [autonomous-coding-agent](https://github.com/Danush-Aries/autonomous-coding-agent) — two-agent autonomous coding system

Built by [Dhanush](https://github.com/Danush-Aries) — AI engineering + cybersecurity.

## License

MIT.
