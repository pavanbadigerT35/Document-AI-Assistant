from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_db, resolve_scope
from app.api.errors import request_id
from app.core.container import Container
from app.schemas.rag import Passage, RetrievalMeta, SearchRequest, SearchResponse
from app.services.retrieval_service import RetrievalResult

router = APIRouter(prefix="/api/v1", tags=["search"])


def retrieval_meta(r: RetrievalResult) -> RetrievalMeta:
    return RetrievalMeta(top_k=r.top_k, min_score=r.min_score, candidates=len(r.candidates), above_threshold=len(r.hits), top_score=r.top_score, latency_ms=r.latency_ms)


@router.post("/search", response_model=SearchResponse)
def search(body: SearchRequest, request: Request, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    scope = resolve_scope(db, body.document_ids)
    result = c.retrieval.search(body.query, scope, body.top_k, body.min_score)
    passages = [Passage(chunk_id=h.chunk_id, document_id=h.document_id, filename=h.filename, page=h.page, text=h.text, score=h.score) for h in result.hits]
    return SearchResponse(results=passages, retrieval=retrieval_meta(result), request_id=request_id(request))
