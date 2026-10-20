from fastapi import APIRouter, Depends, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.deps import get_container, get_db, resolve_scope
from app.api.errors import AppError, request_id
from app.core.container import Container
from app.schemas.rag import QuizHealth, QuizQuestion, QuizRequest, QuizResponse, QuizSource
from app.services.llm_provider import LLMError, LLMNotConfigured
from app.services.quiz_service import QuizError

router = APIRouter(prefix="/api/v1/quiz", tags=["quiz"])


@router.get("/health", response_model=QuizHealth)
def quiz_health(c: Container = Depends(get_container)):
    if c.llm.configured:
        return QuizHealth(available=True)
    return QuizHealth(available=False, reason="Quiz generation needs an LLM. Set GROQ_API_KEY in backend/.env and restart the backend.")


@router.post("/generate", response_model=QuizResponse)
async def generate(body: QuizRequest, request: Request, db: Session = Depends(get_db), c: Container = Depends(get_container)):
    scope = resolve_scope(db, body.document_ids)
    try:
        items = await run_in_threadpool(c.quiz.generate, scope, body.topic, body.num_questions, body.kind)
    except LLMNotConfigured as exc:
        raise AppError(503, "llm_not_configured", str(exc))
    except LLMError as exc:
        raise AppError(502, "llm_error", str(exc))
    except QuizError as exc:
        raise AppError(422, "quiz_failed", str(exc))
    questions = [
        QuizQuestion(
            question=i.question, options=i.options, correct_index=i.correct_index, answer=i.answer, explanation=i.explanation,
            source=QuizSource(chunk_id=i.source.chunk_id, document_id=i.source.document_id, filename=i.source.filename, page=i.source.page, excerpt=i.source.text),
        )
        for i in items
    ]
    return QuizResponse(questions=questions, request_id=request_id(request))
