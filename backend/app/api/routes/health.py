from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.container import Container
from app.api.deps import get_container

router = APIRouter()


@router.get("/health", tags=["health"])
def health():
    return {"status": "ok"}


@router.get("/api/v1/ready", tags=["health"])
def ready(c: Container = Depends(get_container)):
    checks: dict = {}
    try:
        with c.session_factory() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
    try:
        checks["vector_store"] = {"status": "ok", "chunks": c.store.count()}
    except Exception:
        checks["vector_store"] = {"status": "error"}
    checks["embeddings"] = {"model": c.embedder.name, "loaded": c.embedder.loaded}
    checks["llm"] = {
        "configured": c.llm.configured,
        "provider": c.llm.provider,
        "model": c.llm.model,
        "message": None if c.llm.configured else "Set GROQ_API_KEY in backend/.env to enable chat and quizzes. Upload and search still work.",
    }
    ok = checks["database"] == "ok" and checks["vector_store"]["status"] == "ok"
    return {"status": "ok" if ok else "degraded", "checks": checks}
