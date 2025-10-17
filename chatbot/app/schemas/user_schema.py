# app/schemas/user_schema.py
from pydantic import BaseModel, Field, SecretStr
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    password: str
    role: str = "user"
    is_active: bool = True

class UserInDB(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None
    password_hash: str

    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    email: str
    password: str

class UserPublic(BaseModel):
    id: UUID
    username: str
    email: str
    full_name: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True
        
class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = None