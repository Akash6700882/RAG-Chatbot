"""FastAPI application factory and entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api import api_router
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.db.session import init_db

settings = get_settings()
logger = get_logger(__name__)

OPENAPI_TAGS = [
    {"name": "system", "description": "Health and liveness checks."},
    {"name": "auth", "description": "User registration and JWT login."},
    {
        "name": "documents",
        "description": "Multi-format document ingestion and management (PDF/DOCX/TXT/MD).",
    },
    {
        "name": "chat",
        "description": "LangGraph-orchestrated RAG chat and conversation history.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_db()
    logger.info(
        "Application startup complete (env=%s, vector_db=%s)",
        settings.app_env,
        settings.vector_db,
    )
    yield
    logger.info("Application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise RAG Chatbot",
        description=(
            "A production-grade Retrieval-Augmented Generation chatbot API. "
            "Supports multi-format document ingestion, ChromaDB/FAISS vector search, "
            "a LangGraph-orchestrated RAG pipeline with hallucination checking, "
            "and JWT-secured REST endpoints."
        ),
        version="1.0.0",
        lifespan=lifespan,
        openapi_tags=OPENAPI_TAGS,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
