# app/access_level_router.py
from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from uuid import UUID
from app.db.database import get_db
from app.schemas.access_level_schema import AccessLevelCreate, AccessLevelPublic, AccessLevelUpdate
from app.services.access_level_service import AccessLevelService
from app.api.deps import get_current_active_admin
from app.schemas.user_schema import UserPublic
from app.schemas.folder_file_schema import FilePublic, FileUpdate
from app.services.folder_file_service import DocumentService
from app.api.deps import get_current_active_user, get_current_active_admin
from app.db.models import File # Added this import to resolve the NameError


router = APIRouter()
access_level_service = AccessLevelService()
document_service = DocumentService()

@router.post("", response_model=AccessLevelPublic, status_code=status.HTTP_201_CREATED)
async def create_access_level(
    level_data: AccessLevelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """Tạo một cấp độ truy cập mới (chỉ admin)."""
    level = await access_level_service.create_access_level(db, level_data, current_user.id)
    if not level:
        raise HTTPException(status_code=400, detail="Access level name already exists.")
    return level

@router.get("", response_model=List[AccessLevelPublic])
async def list_access_levels(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Lấy danh sách tất cả các cấp độ truy cập (chỉ admin)."""
    return await access_level_service.get_all_access_levels(db)

@router.put("/{level_id}", response_model=AccessLevelPublic)
async def update_access_level(
    level_id: UUID,
    level_data: AccessLevelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """Cập nhật một cấp độ truy cập (chỉ admin)."""
    level = await access_level_service.update_access_level(db, level_id, level_data)
    if not level:
        raise HTTPException(status_code=404, detail="Access level not found.")
    return level

@router.delete("/{level_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_access_level(
    level_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """Xóa một cấp độ truy cập (chỉ admin)."""
    success = await access_level_service.delete_access_level(db, level_id)
    if not success:
        raise HTTPException(status_code=404, detail="Access level not found.")
    return

@router.get("/hello", response_model=List[dict])
async def list_access_levels_with_details(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Lấy danh sách tất cả các cấp độ truy cập, bao gồm các nhóm và người dùng trong đó (chỉ admin).
    """
    levels = await access_level_service.get_all_access_levels(db)
    detailed_levels = []
    for level in levels:
        details = await access_level_service.get_access_level_with_groups_and_users(db, level.id)
        if details:
            detailed_levels.append(details)
    return detailed_levels

@router.get("/{level_id}/details", response_model=dict)
async def get_access_level_details(
    level_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Lấy thông tin chi tiết của một cấp độ truy cập, bao gồm các nhóm và người dùng (chỉ admin).
    """
    details = await access_level_service.get_access_level_with_groups_and_users(db, level_id)
    if not details:
        raise HTTPException(status_code=404, detail="Access level not found.")
    return details

# ----- ENDPOINTS MỚI CHO FILES -----
@router.post("/files/{file_id}/access-levels", status_code=status.HTTP_200_OK)
async def assign_access_levels_to_file(
    file_id: UUID,
    access_level_ids: List[UUID] = Body(..., embed=True, alias="access_level_ids"),
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Gán các cấp độ truy cập cho một tệp tin (admin hoặc người tải lên).
    """
    file = await document_service.get_file_by_id(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found.")

    is_admin = current_user.role == "admin"
    is_owner = file.uploaded_by_user_id == current_user.id

    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="Bạn không có quyền gán quyền truy cập cho tệp tin này.")
    
    success = await access_level_service.assign_access_levels_to_file(db, file_id, access_level_ids)
    if not success:
        raise HTTPException(status_code=404, detail="File or some access levels not found.")
    return {"message": "Access levels assigned to file successfully."}

@router.get("/files/{file_id}/access-levels", response_model=List[AccessLevelPublic])
async def get_file_access_levels(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Lấy danh sách các cấp độ truy cập của một tệp tin (admin hoặc người tải lên).
    """
    file = await document_service.get_file_by_id(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found.")

    is_admin = current_user.role == "admin"
    is_owner = file.uploaded_by_user_id == current_user.id

    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem quyền truy cập của tệp tin này.")

    levels = await access_level_service.get_file_access_levels(db, file_id)
    if levels is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return levels

@router.delete("/files/{file_id}/access-levels", status_code=status.HTTP_204_NO_CONTENT)
async def remove_access_levels_from_file(
    file_id: UUID,
    access_level_ids: List[UUID] = Body(..., embed=True, alias="access_level_ids"),
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Xóa các cấp độ truy cập khỏi một tệp tin (admin hoặc người tải lên).
    """
    file = await document_service.get_file_by_id(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found.")

    is_admin = current_user.role == "admin"
    is_owner = file.uploaded_by_user_id == current_user.id

    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xóa quyền truy cập của tệp tin này.")

    success = await access_level_service.remove_access_levels_from_file(db, file_id, access_level_ids)
    if not success:
        raise HTTPException(status_code=404, detail="File or some access levels not found.")
    return

@router.get("/{level_id}", response_model=AccessLevelPublic)
async def get_access_level_by_id(
    level_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)  # chỉ admin được xem
):
    """
    Lấy thông tin chi tiết của một cấp độ truy cập theo ID (chỉ admin).
    """
    level = await access_level_service.get_access_level_by_id(db, level_id)
    if not level:
        raise HTTPException(status_code=404, detail="Access level not found.")
    return level
