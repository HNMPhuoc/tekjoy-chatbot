import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, update
from sqlalchemy.future import select

from app.db.models import ChatSetting


# ----- DEFAULT CONFIG -----
def default_chat_setting(session_id: str):
    return {
        "id": str(uuid.uuid4()),
        "session_id": session_id,
        "model": "gpt-3.5-turbo",
        "system_prompt": "You are an AI assistant.",
        "max_tokens": 2048,
        "context_files": [],
        "domain": None,
        "is_history": True,
        "max_context_messages": 0,
        "using_document": True,
        "free_chat": False,
        "show_sources": True,
        "enable_streaming": True,
        "response_style": "concise",
        "language": "vi",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


# ----- LIST -----
async def list_chat_settings(db: AsyncSession):
    result = await db.execute(text("SELECT * FROM chat_settings"))
    return result.mappings().all()


# ----- GET ONE -----
async def get_settings(db: AsyncSession, session_id: str):
    result = await db.execute(
        text("SELECT * FROM chat_settings WHERE session_id = :sid"),
        {"sid": session_id}
    )
    return result.mappings().first()


# ----- EDIT -----
async def edit_chat_setting(db: AsyncSession, session_id: str, payload: dict):
    allowed_fields = {
        "model", "system_prompt", "max_tokens", "context_files",
        "domain", "is_history", "max_context_messages",
        "using_document", "free_chat", "show_sources",
        "enable_streaming", "response_style", "language",
    }

    update_data = {k: v for k, v in payload.items() if k in allowed_fields}
    if not update_data:
        return None, "No valid fields to update"

    result = await db.execute(select(ChatSetting).where(ChatSetting.session_id == session_id))
    setting = result.scalars().first()
    if not setting:
        return None, "Chat setting not found"

    for k, v in update_data.items():
        setattr(setting, k, v)
    setting.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(setting)

    return update_data, None


# ----- RESET -----
async def reset_chat_setting(db: AsyncSession, session_id: str):
    result = await db.execute(select(ChatSetting).where(ChatSetting.session_id == session_id))
    setting = result.scalars().first()
    if not setting:
        return None

    defaults = default_chat_setting(session_id)
    for k, v in defaults.items():
        setattr(setting, k, v)

    await db.commit()
    await db.refresh(setting)

    return defaults
