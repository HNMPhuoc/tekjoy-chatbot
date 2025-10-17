from pydantic import BaseModel
from typing import List

class FileItem(BaseModel):
    file_id: str
    file_name: str

class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    message: str
    files: List[FileItem] = []
