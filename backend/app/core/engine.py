"""
Sovereign AI Core — FastAPI Application Engine
Wires together the air-gap controller, vault, RAG engine, and model router
into a single FastAPI application instance.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Session, create_engine, select

from backend.app.config import settings
from backend.app.core.air_gap import air_gap
from backend.app.vault.auth_vault import SovereignVault

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("sovereign.engine")

# Configure the air-gap controller with the leak-log path now that settings are loaded.
air_gap._leak_log = settings.leak_log_file

# ── Vault ─────────────────────────────────────────────────────────────────────
vault = SovereignVault(key_file=settings.encryption_key_file)

# ── Database (SQLite, local) ───────────────────────────────────────────────────
_engine = create_engine(settings.db_url, echo=False)


class QueryRecord(SQLModel, table=True):
    """Persists every query locally for audit purposes."""
    __tablename__ = "query_log"  # type: ignore[assignment]

    id: Optional[int] = Field(default=None, primary_key=True)
    prompt_hash: str
    complexity: str
    used_rag: bool
    timestamp: str


SQLModel.metadata.create_all(_engine)


def _get_db() -> Session:
    with Session(_engine) as session:
        yield session


# ── ChromaDB RAG engine ───────────────────────────────────────────────────────
class LocalSovereignRAG:
    """
    Local-first Retrieval-Augmented Generation backed by ChromaDB.
    Uses the all-MiniLM-L6-v2 sentence-transformer for embeddings so
    everything runs 100 % on-device — no external API calls.
    """

    def __init__(self) -> None:
        # chromadb >= 0.4 uses PersistentClient instead of the removed DuckDB backend
        self._client = chromadb.PersistentClient(path=str(settings.vector_store_path))

        # Local embedding function — runs on CPU/GPU, zero cloud dependency
        self._embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        self._collection = self._client.get_or_create_collection(
            name="sovereign_brain",
            embedding_function=self._embed_fn,
        )
        logger.info(
            "RAG engine ready — vector store: %s  |  documents: %d",
            settings.vector_store_path,
            self._collection.count(),
        )

    def ingest_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Index a document into the local vector store."""
        self._collection.upsert(
            documents=[text],
            metadatas=[metadata or {}],
            ids=[doc_id],
        )
        logger.info("Ingested document id=%s (%d chars)", doc_id, len(text))

    def retrieve_context(self, query: str, top_k: int = 5) -> List[str]:
        """Return the top-k most relevant document snippets for *query*."""
        if self._collection.count() == 0:
            return []
        results = self._collection.query(query_texts=[query], n_results=min(top_k, self._collection.count()))
        return results["documents"][0] if results["documents"] else []


rag_engine = LocalSovereignRAG()


# ── Local Model Router ────────────────────────────────────────────────────────
class SovereignModelRouter:
    """
    Routes inference requests to a local Ollama instance via its HTTP API.
    Stays on loopback (127.0.0.1) — no data ever leaves the machine.
    """

    REGISTRY: Dict[str, Dict[str, Any]] = {
        "lite":     {"model": settings.lite_model,     "options": {"temperature": 0.2, "top_p": 0.9}},
        "standard": {"model": settings.standard_model, "options": {"temperature": 0.7, "top_p": 0.95}},
        "frontier": {"model": settings.frontier_model, "options": {"temperature": 0.8, "top_p": 1.0}},
    }

    async def execute_inference(self, prompt: str, complexity: str = "standard") -> str:
        """
        Send *prompt* to the local Ollama API and return the generated text.
        Falls back gracefully if Ollama is not running.
        """
        profile = self.REGISTRY.get(complexity, self.REGISTRY["standard"])
        model_name: str = profile["model"]
        options: Dict[str, Any] = profile["options"]

        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": options,
        }

        try:
            # httpx connects to loopback — this is explicitly permitted even in
            # sovereign mode (loopback is not blocked by the air-gap controller).
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{settings.ollama_base_url}/api/generate",
                    json=payload,
                )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "").strip()

        except httpx.ConnectError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Could not connect to Ollama at {settings.ollama_base_url}. "
                    "Make sure Ollama is running: https://ollama.com"
                ),
            )
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Ollama returned HTTP {exc.response.status_code}: {exc.response.text}",
            )


model_router = SovereignModelRouter()


# ── FastAPI application ───────────────────────────────────────────────────────
API_KEY_HEADER = APIKeyHeader(name="X-Sovereign-API-Key", auto_error=True)


def _require_api_key(api_key: str = Security(API_KEY_HEADER)) -> str:
    if api_key != settings.sovereign_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key.",
        )
    return api_key


app = FastAPI(
    title="Sovereign AI Core",
    description=(
        "A local-first, air-gapped AI platform. "
        "Routes queries to local LLMs via Ollama with a ChromaDB RAG engine "
        "and AES-256 encrypted vault."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── Request / Response models ─────────────────────────────────────────────────
class AIQuery(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8192, description="The question or instruction.")
    complexity: str = Field("standard", description="One of: lite, standard, frontier.")
    use_rag: bool = Field(True, description="Augment the prompt with locally retrieved context.")


class IngestRequest(BaseModel):
    doc_id: str = Field(..., description="Unique identifier for the document.")
    text: str = Field(..., min_length=1, description="Document content to index.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Optional key/value metadata.")


class VaultRequest(BaseModel):
    plaintext: str = Field(..., description="Data to encrypt.")


class VaultDecryptRequest(BaseModel):
    token: str = Field(..., description="Hex-encoded Fernet token to decrypt.")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check (no auth required)")
async def health_check():
    """Public endpoint — returns service liveness."""
    return {"status": "ok", "service": "sovereign-ai-core"}


@app.get(
    "/system/status",
    tags=["System"],
    dependencies=[Security(_require_api_key)],
    summary="Full system status",
)
async def system_status():
    """Returns operational state of all subsystems."""
    return {
        "air_gap": {
            "enabled": air_gap.sovereign_mode,
            "blocked_attempts": air_gap.blocked_attempts,
        },
        "vault": "operational",
        "rag_engine": {
            "documents_indexed": rag_engine._collection.count(),
            "vector_store": str(settings.vector_store_path),
        },
        "model_registry": list(SovereignModelRouter.REGISTRY.keys()),
        "ollama_url": settings.ollama_base_url,
    }


@app.post(
    "/system/lock",
    tags=["System"],
    dependencies=[Security(_require_api_key)],
    summary="Enable air-gap kill-switch",
)
async def enable_air_gap():
    """Engages the network kill-switch — all outbound sockets will be blocked."""
    air_gap.enable()
    return {"air_gap": "enabled", "message": "All outbound network traffic is now blocked."}


@app.post(
    "/system/unlock",
    tags=["System"],
    dependencies=[Security(_require_api_key)],
    summary="Disable air-gap kill-switch",
)
async def disable_air_gap():
    """Disengages the network kill-switch — normal network access is restored."""
    air_gap.disable()
    return {"air_gap": "disabled", "message": "Network access restored."}


@app.post(
    "/ai/query",
    tags=["Inference"],
    dependencies=[Security(_require_api_key)],
    summary="Query a local LLM with optional RAG context",
)
async def sovereign_query(req: AIQuery):
    """
    Full local-first inference pipeline:

    1. (optional) Retrieve relevant context from the local vector store.
    2. Augment the prompt with retrieved context.
    3. Forward to the local Ollama model.
    4. Return the response — data never leaves the machine.
    """
    import hashlib
    from datetime import datetime, timezone

    context_docs: List[str] = []
    if req.use_rag:
        context_docs = rag_engine.retrieve_context(req.prompt)

    augmented_prompt = req.prompt
    if context_docs:
        context_block = "\n\n---\n\n".join(context_docs)
        augmented_prompt = (
            f"Use the following context to answer the question.\n\n"
            f"=== Context ===\n{context_block}\n\n"
            f"=== Question ===\n{req.prompt}"
        )

    response_text = await model_router.execute_inference(augmented_prompt, req.complexity)

    # Persist audit record locally
    with Session(_engine) as session:
        record = QueryRecord(
            prompt_hash=hashlib.sha256(req.prompt.encode()).hexdigest(),
            complexity=req.complexity,
            used_rag=req.use_rag,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        session.add(record)
        session.commit()

    return {
        "response": response_text,
        "model": SovereignModelRouter.REGISTRY.get(req.complexity, SovereignModelRouter.REGISTRY["standard"])["model"],
        "rag_context_used": bool(context_docs),
        "context_chunks": len(context_docs),
        "source": "local-sovereign-core",
    }


@app.post(
    "/rag/ingest",
    tags=["RAG"],
    dependencies=[Security(_require_api_key)],
    summary="Ingest a document into the local vector store",
)
async def ingest_document(req: IngestRequest):
    """Indexes a document for later retrieval via the RAG pipeline."""
    rag_engine.ingest_document(req.doc_id, req.text, req.metadata)
    return {
        "doc_id": req.doc_id,
        "status": "indexed",
        "total_documents": rag_engine._collection.count(),
    }


@app.get(
    "/rag/search",
    tags=["RAG"],
    dependencies=[Security(_require_api_key)],
    summary="Search the local vector store",
)
async def search_rag(query: str, top_k: int = 5):
    """Returns the most relevant document chunks for the given query."""
    chunks = rag_engine.retrieve_context(query, top_k=top_k)
    return {"query": query, "results": chunks, "count": len(chunks)}


@app.post(
    "/vault/encrypt",
    tags=["Vault"],
    dependencies=[Security(_require_api_key)],
    summary="Encrypt a plaintext string",
)
async def vault_encrypt(req: VaultRequest):
    """Encrypts *plaintext* with the local AES-256 vault key."""
    token = vault.encrypt(req.plaintext)
    return {"token": token.hex()}


@app.post(
    "/vault/decrypt",
    tags=["Vault"],
    dependencies=[Security(_require_api_key)],
    summary="Decrypt a vault token",
)
async def vault_decrypt(req: VaultDecryptRequest):
    """Decrypts a token previously produced by ``/vault/encrypt``."""
    try:
        plaintext = vault.decrypt(bytes.fromhex(req.token))
    except (ValueError, Exception) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"plaintext": plaintext}
