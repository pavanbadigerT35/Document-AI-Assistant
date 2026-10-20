import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.errors import install_error_handlers
from app.api.routes import chat, documents, health, quiz, search, topics
from app.core.config import Settings, get_settings
from app.core.container import Container, build_container
from app.core.logging import setup_logging
from app.services.embedding_service import Embedder
from app.services.llm_provider import LLMProvider

log = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, llm: LLMProvider | None = None, embedder: Embedder | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = build_container(settings, llm=llm, embedder=embedder)
        c: Container = app.state.container
        log.info("Embeddings: %s | LLM configured: %s (%s)", c.embedder.name, c.llm.configured, c.llm.model)
        if not c.llm.configured:
            log.warning("GROQ_API_KEY is not set: upload and search work, chat and quizzes are disabled.")
        yield

    app = FastAPI(title="Document-Based AI Learning Assistant", version="1.0.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
    install_error_handlers(app)
    for module in (health, documents, search, chat, topics, quiz):
        app.include_router(module.router)
    return app


app = create_app()
