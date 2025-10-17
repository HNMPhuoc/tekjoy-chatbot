# app/schemas/group_schema.py
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID

class GroupBase(BaseModel):
    name: str
    description: Optional[str] = None

class GroupCreate(GroupBase):
    pass

class GroupUpdate(GroupBase):
    name: Optional[str] = None

class GroupPublic(GroupBase):
    id: UUID
    
    class Config:
        from_attributes = True

class GroupAddUserRequest(BaseModel):
    user_ids: List[UUID]