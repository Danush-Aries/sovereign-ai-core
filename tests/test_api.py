"""Integration-style tests for the FastAPI gateway (no Ollama required)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.core.engine import app
from backend.app.config import settings

# Use the configured API key so auth tests pass.
HEADERS = {"X-Sovereign-API-Key": settings.sovereign_api_key}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ── Health ────────────────────────────────────────────────────────────────────

def test_health_no_auth_required(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_status_requires_api_key(client: TestClient) -> None:
    resp = client.get("/system/status")
    assert resp.status_code == 403


def test_status_with_valid_key(client: TestClient) -> None:
    resp = client.get("/system/status", headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "air_gap" in data
    assert "rag_engine" in data


# ── Air-gap toggle ────────────────────────────────────────────────────────────

def test_lock_and_unlock(client: TestClient) -> None:
    resp = client.post("/system/lock", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["air_gap"] == "enabled"

    resp = client.post("/system/unlock", headers=HEADERS)
    assert resp.status_code == 200
    assert resp.json()["air_gap"] == "disabled"


# ── Vault ─────────────────────────────────────────────────────────────────────

def test_vault_encrypt_decrypt_roundtrip(client: TestClient) -> None:
    secret = "my-sensitive-data"
    enc_resp = client.post("/vault/encrypt", json={"plaintext": secret}, headers=HEADERS)
    assert enc_resp.status_code == 200
    token = enc_resp.json()["token"]
    assert isinstance(token, str)

    dec_resp = client.post("/vault/decrypt", json={"token": token}, headers=HEADERS)
    assert dec_resp.status_code == 200
    assert dec_resp.json()["plaintext"] == secret


def test_vault_decrypt_bad_token(client: TestClient) -> None:
    resp = client.post("/vault/decrypt", json={"token": "deadbeef"}, headers=HEADERS)
    assert resp.status_code == 400


# ── RAG ───────────────────────────────────────────────────────────────────────

def test_ingest_and_search(client: TestClient) -> None:
    ingest_resp = client.post(
        "/rag/ingest",
        json={"doc_id": "test-doc-1", "text": "The sky is blue and stars are bright.", "metadata": {"source": "test"}},
        headers=HEADERS,
    )
    assert ingest_resp.status_code == 200
    assert ingest_resp.json()["status"] == "indexed"

    search_resp = client.get("/rag/search", params={"query": "sky color", "top_k": 3}, headers=HEADERS)
    assert search_resp.status_code == 200
    results = search_resp.json()["results"]
    assert isinstance(results, list)


# ── AI Query (mocked Ollama) ──────────────────────────────────────────────────

def test_ai_query_mocked(client: TestClient) -> None:
    with patch(
        "backend.app.core.engine.model_router.execute_inference",
        new=AsyncMock(return_value="This is a local AI response."),
    ):
        resp = client.post(
            "/ai/query",
            json={"prompt": "What is 2+2?", "complexity": "lite", "use_rag": False},
            headers=HEADERS,
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["response"] == "This is a local AI response."
    assert data["source"] == "local-sovereign-core"


def test_ai_query_invalid_complexity_falls_back(client: TestClient) -> None:
    """Unknown complexity should fall back to 'standard' without crashing."""
    with patch(
        "backend.app.core.engine.model_router.execute_inference",
        new=AsyncMock(return_value="fallback response"),
    ):
        resp = client.post(
            "/ai/query",
            json={"prompt": "Hello", "complexity": "unknown-tier", "use_rag": False},
            headers=HEADERS,
        )
    assert resp.status_code == 200
