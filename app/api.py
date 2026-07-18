"""Aggregates all versioned API routers."""

from fastapi import APIRouter

from app.auth.router import router as auth_router
from app.chat.router import router as chat_router
from app.documents.router import router as documents_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(documents_router)
api_router.include_router(chat_router)
