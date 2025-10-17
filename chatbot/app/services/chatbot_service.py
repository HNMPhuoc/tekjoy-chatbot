import uuid
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_openai import ChatOpenAI

from app.schemas.chatbot_schema import ChatRequest  # ✅ import từ schemas


# ---- DB HELPERS ----
async def get_or_create_chat_settings(db: AsyncSession, session_id: str) -> Dict[str, Any]:
    q = text("SELECT * FROM chat_settings WHERE session_id = :sid")
    result = await db.execute(q, {"sid": session_id})
    settings = result.mappings().first()

    if settings:
        return settings

    default = {
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
    cols = ",".join(default.keys())
    vals = ",".join([f":{k}" for k in default.keys()])
    await db.execute(text(f"INSERT INTO chat_settings ({cols}) VALUES ({vals})"), default)
    await db.commit()
    return default


async def get_file_extracts(db: AsyncSession, file_ids: List[str]) -> List[str]:
    if not file_ids:
        return []
    q = text("SELECT extracted_text FROM files WHERE id = ANY(:ids)")
    result = await db.execute(q, {"ids": file_ids})
    rows = result.fetchall()
    return [row[0] for row in rows if row[0]]


async def get_chat_history(db: AsyncSession, session_id: str, limit: int) -> List[str]:
    q = text("""
        SELECT sender_type, message_text
        FROM chat_messages
        WHERE session_id = :sid
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    result = await db.execute(q, {"sid": session_id, "limit": limit})
    rows = result.fetchall()
    return [f"{r[0]}: {r[1]}" for r in reversed(rows)]


async def get_or_create_session(db: AsyncSession, session_id: str, user_id: str) -> str:
    q = text("SELECT id FROM chat_sessions WHERE id = :sid")
    result = await db.execute(q, {"sid": session_id})
    row = result.fetchone()
    if row:
        return row[0]

    await db.execute(text("""
        INSERT INTO chat_sessions (id, user_id, title)
        VALUES (:sid, :uid, :title)
    """), {"sid": session_id, "uid": user_id, "title": "New Session"})
    await db.commit()
    return session_id


# ---- MAIN CHAT SERVICE ----
async def handle_chat(payload: ChatRequest, db: AsyncSession) -> Dict[str, Any]:
    # get settings + session
    session_id = await get_or_create_session(db, payload.session_id, payload.user_id)
    settings = await get_or_create_chat_settings(db, payload.session_id)

    # handle docs
    context_text = ""
    if settings["using_document"]:
        file_ids = [f.file_id for f in payload.files]
        extracts = await get_file_extracts(db, file_ids)
        context_text = "\n\n".join(extracts)

    # handle history
    history_text = ""
    if settings["is_history"]:
        limit = settings["max_context_messages"] or 15
        history = await get_chat_history(db, payload.session_id, limit)
        history_text = "\n".join(history)

    # build final prompt
    final_prompt = f"""{settings['system_prompt']}

this is document:
{context_text}

and messenger history:
{history_text}

current user: {payload.message}
"""

    llm = ChatOpenAI(model=settings["model"], temperature=0)

    # log user message
    user_msg_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO chat_messages (id, session_id, sender_type, sender_id, message_text)
        VALUES (:id, :sid, 'user', :uid, :msg)
    """), {
        "id": user_msg_id,
        "sid": payload.session_id,
        "uid": payload.user_id,
        "msg": payload.message
    })
    await db.commit()

    # call LLM
    response = await llm.ainvoke(final_prompt)

    # log assistant message
    bot_msg_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO chat_messages (id, session_id, sender_type, message_text)
        VALUES (:id, :sid, 'assistant', :msg)
    """), {
        "id": bot_msg_id,
        "sid": payload.session_id,
        "msg": response.content
    })
    await db.commit()

    return {
        "message": response.content,
        "used_files": payload.files if settings["show_sources"] else []
    }
