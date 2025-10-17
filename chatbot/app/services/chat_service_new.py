# file: app/services/chat_service_new.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc
from sqlalchemy.dialects.postgresql import UUID

from app.db.models import ChatSession, ChatMessage

async def list_user_sessions(db: AsyncSession, user_id: str):
    """
    Retrieve all sessions for a given user, sorted by last activity.
    """
    stmt = select(ChatSession).where(ChatSession.user_id == user_id).order_by(desc(ChatSession.last_activity_at))
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    
    # Optional: You can format the output here to be more specific, like including the first message.
    formatted_sessions = []
    for s in sessions:
        formatted_sessions.append({
            "id": str(s.id),
            "user_id": str(s.user_id),
            "title": s.title,
            "last_activity_at": s.last_activity_at.isoformat() if s.last_activity_at else None,
            "created_at": s.created_at.isoformat()
        })
    return formatted_sessions

async def edit_session_title(db: AsyncSession, session_id: str, new_title: str):
    """
    Update the title of a chat session by its ID.
    """
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalars().first()
    
    if not session:
        return None
    
    session.title = new_title
    await db.commit()
    await db.refresh(session)
    
    return {
        "id": str(session.id),
        "user_id": str(session.user_id),
        "title": session.title,
        "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None
    }

async def get_session_history(db: AsyncSession, session_id: UUID):
    """
    Retrieve all chat messages for a given session, in chronological order.
    """
    stmt = select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    result = await db.execute(stmt)
    messages = result.scalars().all()
    
    if not messages:
        return [] 

    formatted_messages = []
    for msg in messages:
        formatted_messages.append({
            "id": msg.id,
            "sender_type": msg.sender_type,
            "message_text": msg.message_text,
            "created_at": msg.created_at.isoformat()
        })
    return formatted_messages