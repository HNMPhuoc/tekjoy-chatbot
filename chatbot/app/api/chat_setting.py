from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.chat_setting_service import (
    list_chat_settings,
    get_settings,
    edit_chat_setting,
    reset_chat_setting,
)

from app.services.chat_setting_serviceV2 import (
    list_chat_settings,
    get_settings,
    edit_chat_setting,
    reset_chat_setting,
)

router = APIRouter(tags=["Chat Settings"])


@router.post("/list")
async def list_settings_api(db: AsyncSession = Depends(get_db)):
    rows = await list_chat_settings(db)
    if not rows:
        raise HTTPException(status_code=404, detail="No chat settings found")
    return rows


@router.post("/get")
async def get_settings_api(session_id: str = Body(..., embed=True), db: AsyncSession = Depends(get_db)):
    row = await get_settings(db, session_id)
    if not row:
        raise HTTPException(status_code=404, detail="Settings not found")
    return row


@router.post("/edit")
async def edit_settings_api(
    session_id: str = Body(..., embed=True),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db)
):
    updated, error = await edit_chat_setting(db, session_id, payload)
    if error:
        raise HTTPException(status_code=400 if "valid" in error else 404, detail=error)
    return {"message": "Chat settings updated", "updated": updated}


@router.post("/reset")
async def reset_settings_api(session_id: str = Body(..., embed=True), db: AsyncSession = Depends(get_db)):
    defaults = await reset_chat_setting(db, session_id)
    if not defaults:
        raise HTTPException(status_code=404, detail="Chat setting not found")
    return {"message": "Chat settings reset", "settings": defaults}


@router.post("/getV2")
async def get_settings_api(user_id: str = Body(..., embed=True), db: AsyncSession = Depends(get_db)):
    row = await get_settings(db, user_id)
    if not row:
        raise HTTPException(status_code=404, detail="Settings not found")
    return row


@router.post("/editV2")
async def edit_settings_api(
    user_id: str = Body(..., embed=True),
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db)
):
    updated, error = await edit_chat_setting(db, user_id, payload)
    if error:
        raise HTTPException(status_code=400 if "valid" in error else 404, detail=error)
    return {"message": "Chat settings updated", "updated": updated}


@router.post("/resetV2")
async def reset_settings_api(user_id: str = Body(..., embed=True), db: AsyncSession = Depends(get_db)):
    defaults = await reset_chat_setting(db, user_id)
    if not defaults:
        raise HTTPException(status_code=404, detail="Chat setting not found")
    return {"message": "Chat settings reset", "settings": defaults}