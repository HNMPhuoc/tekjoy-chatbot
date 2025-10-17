from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID

# =========================
# Folder Schemas
# =========================
class FolderBase(BaseModel):
    name: str = Field(..., description="Tên thư mục.")
    parent_id: Optional[UUID] = Field(None, description="ID của thư mục cha.")

class FolderCreate(FolderBase):
    pass

class FolderUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Tên mới của thư mục.")
    parent_id: Optional[UUID] = Field(None, description="ID của thư mục cha mới.")
    keyword: Optional[str]  = Field(None, description="Keyword mới của thư mục.")  


class FolderPublic(FolderBase):
    id: UUID
    created_at: datetime
    created_by_user_id: Optional[UUID]
    
    class Config:
        from_attributes = True


# =========================
# File Schemas
# =========================
class FileBase(BaseModel):
    original_file_name: str = Field(..., description="Tên gốc của tệp tin.")
    folder_id: Optional[UUID] = Field(None, description="ID của thư mục chứa tệp tin.")

class FileCreate(FileBase):
    file_extension: Optional[str] = None
    mime_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    storage_path: str
    thumbnail_path: Optional[str] = None
    document_type: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    document_date: Optional[date] = None
    vendor_name: Optional[str] = None
    contract_number: Optional[str] = None
    total_value: Optional[float] = None
    currency: Optional[str] = None
    warranty_period_months: Optional[int] = None
    is_template: Optional[bool] = False
    keywords: Optional[List[str]] = []
    folder_path: Optional[str] = None
    extracted_text: Optional[str] = None
    ai_summary: Optional[Dict[str, Any]] = None
    ai_extracted_data: Optional[Dict[str, Any]] = None
    download_link: Optional[str] = None
    char_count: Optional[int] = None
    word_count: Optional[int] = None

class FileUpdate(BaseModel):
    original_file_name: Optional[str] = None
    folder_id: Optional[UUID] = None
    file_extension: Optional[str] = None
    mime_type: Optional[str] = None
    document_type: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    vendor_name: Optional[str] = None
    contract_number: Optional[str] = None
    total_value: Optional[float] = None
    currency: Optional[str] = None
    warranty_period_months: Optional[int] = None
    is_template: Optional[bool] = None
    keywords: Optional[List[str]] = None

class FilePublic(FileBase):
    id: UUID
    file_extension: Optional[str]
    mime_type: Optional[str]
    file_size_bytes: Optional[int]
    storage_path: str
    thumbnail_path: Optional[str]
    document_type: Optional[str]
    upload_timestamp: datetime
    last_modified_timestamp: datetime
    uploaded_by_user_id: Optional[UUID]
    processing_status: str
    error_message: Optional[str]
    project_code: Optional[str]
    project_name: Optional[str]
    document_date: Optional[date]
    vendor_name: Optional[str]
    contract_number: Optional[str]
    total_value: Optional[float]
    currency: Optional[str]
    warranty_period_months: Optional[int]
    is_template: Optional[bool]
    keywords: Optional[List[str]]
    folder_path: Optional[str]
    extracted_text: Optional[str]
    ai_summary: Optional[Dict[str, Any]]
    ai_extracted_data: Optional[Dict[str, Any]]
    download_link: Optional[str]
    char_count: Optional[int]
    word_count: Optional[int]
    
    class Config:
        from_attributes = True


# =========================
# Folder Content Response
# =========================
class FolderContentResponse(BaseModel):
    folders: List[FolderPublic]
    files: List[FilePublic]

class PaginatedFiles(BaseModel):
    page: int
    page_size: int
    total: int
    items: List[FilePublic]