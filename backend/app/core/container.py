"""Wires together settings, database, embedder, vector store and LLM."""
from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.db.models import FAILED, PENDING, PROCESSING, Document
from app.db.session import make_engine, make_session_factory
from app.services.embedding_service import Embedder, build_embedder
from app.services.llm_provider import GroqProvider, LLMProvider, UnconfiguredLLM
from app.services.quiz_service import QuizService
from app.services.rag_service import RagService
from app.services.retrieval_service import RetrievalService
from app.services.vector_store import VectorStore


@dataclass
class Container:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]
    embedder: Embedder
    store: VectorStore
    retrieval: RetrievalService
    llm: LLMProvider
    rag: RagService
    quiz: QuizService


def build_container(settings: Settings, llm: LLMProvider | None = None, embedder: Embedder | None = None) -> Container:
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings.sqlite_path)
    factory = make_session_factory(engine)
    embedder = embedder or build_embedder(settings.embedding_backend, settings.embedding_model)
    store = VectorStore(settings.chroma_dir)
    if llm is None:
        llm = (
            GroqProvider(
                settings.groq_api_key.get_secret_value().strip(), settings.groq_model, settings.groq_base_url,
                settings.llm_timeout_seconds, settings.groq_reasoning_effort,
            )
            if settings.llm_configured
            else UnconfiguredLLM(settings.groq_model)
        )
    retrieval = RetrievalService(embedder, store, settings.top_k, settings.min_score)
    container = Container(settings, engine, factory, embedder, store, retrieval, llm, RagService(llm), QuizService(llm, retrieval, store))
    _recover_interrupted(container)
    return container


def _recover_interrupted(c: Container) -> None:
    """A crash mid-ingestion would leave documents stuck in Pending/Processing; mark them Failed."""
    with c.session_factory() as db:
        stuck = db.query(Document).filter(Document.status.in_([PENDING, PROCESSING])).all()
        for doc in stuck:
            doc.status, doc.error_message = FAILED, "Processing was interrupted. Upload the file again to retry."
            c.store.delete_document(doc.id)
        db.commit()
