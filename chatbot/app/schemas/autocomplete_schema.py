from pydantic import BaseModel
from typing import Optional, List, Literal, Union
from uuid import UUID
from datetime import datetime


class FileSummary(BaseModel):
    id: UUID
    original_file_name: str

class FolderKeywordResponse(BaseModel):
    folder_id: str
    folder_name: str
    keyword: str

class FolderItem(BaseModel):
    id: UUID
    name: str
    type: Literal['folder'] = 'folder'
    parent_id: Optional[UUID] = None

class AutocompleteItem(BaseModel):
    type: Literal['file', 'folder']
    id: UUID
    name: str
    parent_id: Optional[UUID] = None