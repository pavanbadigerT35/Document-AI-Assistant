from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.rag import DocumentTopics, Suggestion, TopicOut, TopicsResponse
from app.services.topic_service import list_topics, suggest_questions

router = APIRouter(prefix="/api/v1", tags=["topics"])


@router.get("/topics", response_model=TopicsResponse)
def topics(document_id: str | None = None, db: Session = Depends(get_db)):
    groups = list_topics(db, [document_id] if document_id else None)
    return TopicsResponse(documents=[
        DocumentTopics(document_id=d.id, filename=d.filename, topics=[TopicOut(title=t.title, page=t.page, level=t.level) for t in ts])
        for d, ts in groups
    ])


@router.get("/suggestions", response_model=list[Suggestion])
def suggestions(document_id: str | None = None, limit: int = Query(6, ge=1, le=20), db: Session = Depends(get_db)):
    return [Suggestion(**s) for s in suggest_questions(db, [document_id] if document_id else None, limit)]
