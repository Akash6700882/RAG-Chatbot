"""DB-backed conversation memory, keyed by (owner_id, session_id)."""

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ChatMessage


def get_recent_history(db: Session, owner_id: str, session_id: str) -> list[dict[str, str]]:
    """Returns the last N conversation turns, oldest first, for use in prompts."""
    settings = get_settings()
    limit = settings.conversation_history_turns * 2  # user + assistant per turn

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.owner_id == owner_id, ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    messages.reverse()
    return [{"role": message.role, "content": message.content} for message in messages]


def save_message(db: Session, owner_id: str, session_id: str, role: str, content: str) -> ChatMessage:
    message = ChatMessage(owner_id=owner_id, session_id=session_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
