from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID

from app.db.database import get_db
from app.services.autocomplet_service import AutocompleteService
from app.schemas.folder_file_schema import FilePublic
from app.schemas.user_schema import UserPublic
from app.api.deps import get_current_active_user
from app.schemas.autocomplete_schema import FileSummary, FolderKeywordResponse, AutocompleteItem

router = APIRouter(tags=["Autocomplete"])
autocomplete_service = AutocompleteService()


@router.get("/autocomplete/keywords", response_model=List[FolderKeywordResponse])
async def get_all_keywords(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Lấy toàn bộ keywords kèm folder_id và folder_name để client hiển thị autocomplete ban đầu."""
    return await autocomplete_service.get_all_keywords(db)


@router.get("/autocomplete/keywords/suggest", response_model=List[str])
async def suggest_keywords(
    prefix: str = Query(..., description="Chuỗi gợi ý keyword, ví dụ: 'to' → 'tóm tắt'"),
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Gợi ý keywords theo prefix user đang nhập."""
    results = await autocomplete_service.suggest_keywords(db, prefix)
    if not results:
        raise HTTPException(status_code=404, detail="Không tìm thấy keyword nào phù hợp.")
    return results


@router.get("/autocomplete/filesV2", response_model=List[FileSummary])
async def get_files_by_keyword(
    keyword: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    files = await autocomplete_service.get_files_by_keyword(db, current_user.id, keyword)
    if not files:
        raise HTTPException(status_code=404, detail="Không tìm thấy file nào cho keyword này.")
    return files


@router.get("/autocomplete/browse", response_model=List[AutocompleteItem])
async def browse_folder_contents(
    folder_id: Optional[str] = Query(None, description="ID của thư mục cần xem nội dung"),
    keyword: Optional[str] = Query(None, description="Keyword để tìm thư mục gốc (nếu folder_id không được cung cấp)"),
    prefix: str = Query("", description="Lọc kết quả theo prefix"),
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Duyệt nội dung thư mục (bao gồm cả file và thư mục con) mà người dùng có quyền truy cập.
    Có thể sử dụng keyword để tìm thư mục gốc hoặc folder_id để xem nội dung cụ thể.
    """
    folder_uuid = None
    if folder_id:
        try:
            folder_uuid = UUID(folder_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Định dạng folder_id không hợp lệ")
    
    items = await autocomplete_service.get_folder_contents(
        db=db,
        user_id=current_user.id,
        folder_id=folder_uuid,
        keyword=keyword,
        prefix=prefix
    )
    
    if not items:
        raise HTTPException(status_code=404, detail="Không tìm thấy nội dung nào trong thư mục này.")
    
    return items