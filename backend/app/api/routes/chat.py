from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_db, resolve_scope
from app.api.errors import AppError, request_id
from app.api.routes.search import retrieval_meta
from app.core.container import Container
from app.schemas.rag import ChatRequest, ChatResponse, LLMInfo, Source
from app.services.llm_provider import LLMError, LLMNotConfigured

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    scope = resolve_scope(db, body.document_ids)
    retrieval = await run_in_threadpool(c.retrieval.search, body.question, scope, body.top_k)
    try:
        result = await run_in_threadpool(c.rag.answer, body.question, retrieval)
    except LLMNotConfigured as exc:
        raise AppError(503, "llm_not_configured", str(exc))
    except LLMError as exc:
        raise AppError(502, "llm_error", str(exc))
    sources = [
        Source(source_id=sid, chunk_id=ch.chunk_id, document_id=ch.document_id, filename=ch.filename, page=ch.page, excerpt=ch.text, score=ch.score)
        for sid, ch in result.sources
    ]
    return ChatResponse(
        answer=result.answer,
        sources=sources,
        insufficient_evidence=result.insufficient_evidence,
        warning=result.warning,
        retrieval=retrieval_meta(retrieval),
        llm=None if result.insufficient_evidence and not retrieval.sufficient else LLMInfo(provider=c.llm.provider, model=c.llm.model),
        request_id=request_id(request),
    )
