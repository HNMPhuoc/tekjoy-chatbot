# app/schemas/access_level_schema.py
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime

class AccessLevelBase(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: Optional[bool] = False

class AccessLevelCreate(AccessLevelBase):
    pass

class AccessLevelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_default: Optional[bool] = None

class AccessLevelPublic(AccessLevelBase):
    id: UUID
    created_by_user_id: Optional[UUID] = None
    created_at: datetime

    class Config:
        from_attributes = True

class GroupAccessLevelRequest(BaseModel):
    access_level_ids: List[UUID]