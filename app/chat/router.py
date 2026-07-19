"""Chat endpoints: RAG-backed /chat and /history."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.chat.schemas import ChatRequest, ChatResponse, HistoryMessage
from app.core.logging import get_logger
from app.db.models import ChatMessage, User
from app.db.session import get_db
from app.memory.conversation import get_recent_history, save_message
from app.rag.graph import get_rag_graph

router = APIRouter(tags=["chat"])
logger = get_logger(__name__)


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    session_id = payload.session_id or str(uuid.uuid4())
    history = get_recent_history(db, current_user.id, session_id)

    graph = get_rag_graph()
    result = graph.invoke(
        {
            "question": payload.message,
            "owner_id": current_user.id,
            "chat_history": history,
            "retry_count": 0,
        }
    )

    save_message(db, current_user.id, session_id, "user", payload.message)
    save_message(db, current_user.id, session_id, "assistant", result["answer"])

    # Only cite sources when the answer actually came from generated, grounded
    # content — not when the fallback path was used (context was insufficient,
    # or the answer was rejected as ungrounded after retries).
    sources = (
        []
        if result.get("used_fallback")
        else sorted(
            {
                doc.metadata.get("filename", "unknown")
                for doc in result.get("retrieved_docs", [])
            }
        )
    )
    logger.info(
        "Chat answered for user=%s session=%s grounded=%s retries=%s",
        current_user.id,
        session_id,
        result.get("is_grounded"),
        result.get("retry_count", 0),
    )
    return ChatResponse(session_id=session_id, answer=result["answer"], sources=sources)


@router.get("/history", response_model=list[HistoryMessage])
def history(
    session_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ChatMessage]:
    query = db.query(ChatMessage).filter(ChatMessage.owner_id == current_user.id)
    if session_id:
        query = query.filter(ChatMessage.session_id == session_id)
    return query.order_by(ChatMessage.created_at.asc()).all()
