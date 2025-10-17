# app/api/group_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple, Any

from app.db.database import get_db
from app.schemas.group_schema import GroupCreate, GroupPublic, GroupUpdate, GroupAddUserRequest
from app.services.group_service import GroupService
from app.api.deps import get_current_active_admin, get_current_active_user
from app.schemas.user_schema import UserPublic 
from uuid import UUID

from app.services.access_level_service import AccessLevelService 
from app.schemas.access_level_schema import GroupAccessLevelRequest 
import logging
from app.core.db_retry import retry_on_deadlock # Import hàm helper

logger = logging.getLogger(__name__)

router = APIRouter()
group_service = GroupService()
access_level_service = AccessLevelService() 

# Hàm helper để tạo thông báo tích cực
def create_positive_message(base_message: str, attempts: int) -> str:
    if attempts > 1:
        # Phản hồi tích cực khi có retry
        return f"{base_message} sau {attempts} lần thử (Đã tự động xử lý tắc nghẽn hệ thống)."
    return base_message

# --- ENDPOINTS GHI DỮ LIỆU (ĐƯỢC BỌC RETRY) ---

@router.post("", response_model=GroupPublic, status_code=status.HTTP_201_CREATED)
async def create_group(
    group_data: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    try:
        # BỌC LỜI GỌI SERVICE
        group, attempts = await retry_on_deadlock(
            group_service.create_group, db=db, group_data=group_data
        )
        if not group:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên nhóm đã tồn tại." # Đã dịch lại thông báo lỗi
            )
        
        if attempts > 1:
            logger.warning(create_positive_message(f"Tạo nhóm {group.name} thành công.", attempts))
            
        return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating group: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi tạo nhóm.")


@router.put("/{group_id}", response_model=GroupPublic)
async def update_group(
    group_id: str,
    group_data: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    try:
        # BỌC LỜI GỌI SERVICE
        group, attempts = await retry_on_deadlock(
            group_service.update_group, db=db, group_id=group_id, group_data=group_data
        )
        if not group:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm.") # Đã dịch lại thông báo lỗi
        
        if attempts > 1:
            logger.warning(create_positive_message(f"Cập nhật nhóm {group.name} thành công.", attempts))
            
        return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating group: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi cập nhật nhóm.")


@router.post("/{group_id}/add_users", status_code=status.HTTP_200_OK)
async def add_users_to_group(
    group_id: UUID,
    payload: GroupAddUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Thêm một hoặc nhiều người dùng vào một nhóm cụ thể. (Chỉ dành cho admin).
    """
    try:
        user_ids_str = [str(uid) for uid in payload.user_ids]
        # BỌC LỜI GỌI SERVICE
        success, attempts = await retry_on_deadlock(
            group_service.add_users_to_group, db=db, group_id=str(group_id), user_ids=user_ids_str
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không tìm thấy nhóm hoặc không có người dùng hợp lệ nào được cung cấp." # Đã dịch lại thông báo lỗi
            )
        
        # PHẢN HỒI TÍCH CỰC
        message = create_positive_message("Người dùng đã được thêm vào nhóm thành công.", attempts)
        return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding users to group: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi thêm người dùng vào nhóm.")


@router.post("/{group_id}/assign_access_levels", status_code=status.HTTP_200_OK)
async def assign_access_levels_to_group(
    group_id: UUID,
    payload: GroupAccessLevelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Gán một hoặc nhiều cấp độ truy cập cho một nhóm (chỉ admin).
    Lưu ý: Thao tác này sẽ ghi đè các cấp độ truy cập đã có của nhóm.
    """
    try:
        # BỌC LỜI GỌI SERVICE
        success, attempts = await retry_on_deadlock(
            access_level_service.assign_access_levels_to_group, 
            db=db, 
            group_id=group_id, 
            access_level_ids=payload.access_level_ids
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm.") # Đã dịch lại thông báo lỗi
        
        # PHẢN HỒI TÍCH CỰC
        message = create_positive_message("Cấp độ truy cập đã được gán thành công.", attempts)
        return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning access levels to group: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi gán cấp độ truy cập.")


@router.delete("/{group_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_user_from_group(
    group_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin) # Chỉ admin mới có quyền xóa
):
    """
    Xóa một người dùng khỏi một nhóm cụ thể (chỉ admin).
    """
    try:
        # BỌC LỜI GỌI SERVICE
        success, attempts = await retry_on_deadlock(
            group_service.remove_user_from_group, db=db, group_id=group_id, user_id=user_id
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng hoặc nhóm, hoặc người dùng không phải thành viên của nhóm.") # Đã dịch lại thông báo lỗi
        
        if attempts > 1:
            logger.warning(create_positive_message("Xóa người dùng khỏi nhóm thành công.", attempts))
            
        return # HTTP 204 No Content
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing user from group: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi xóa người dùng khỏi nhóm.")


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Xóa một nhóm theo ID. 
    Chỉ admin mới có quyền xóa.
    """
    try:
        # BỌC LỜI GỌI SERVICE
        success, attempts = await retry_on_deadlock(
            group_service.delete_group, db=db, group_id=str(group_id)
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm.") # Đã dịch lại thông báo lỗi
            
        if attempts > 1:
            logger.warning(create_positive_message("Xóa nhóm thành công.", attempts))
            
        return None  # HTTP 204 không có body
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting group: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Lỗi hệ thống khi xóa nhóm.")


@router.put("/{group_id}/update_users", status_code=status.HTTP_200_OK)
async def update_group_users(
    group_id: UUID,
    payload: GroupAddUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Update all users in a group in a single operation.
    This replaces the existing user list with the new one.
    """
    try:
        # BỌC LỜI GỌI SERVICE
        success, attempts = await retry_on_deadlock(
            group_service.update_group_users, db=db, group_id=group_id, new_user_ids=payload.user_ids
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cập nhật người dùng vào nhóm thất bại." # Đã dịch lại thông báo lỗi
            )
        
        # PHẢN HỒI TÍCH CỰC
        message = create_positive_message("Cập nhật người dùng nhóm thành công.", attempts)
        return {"message": message}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating group users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Lỗi hệ thống khi cập nhật người dùng nhóm."
        )

# --- ENDPOINTS CHỈ ĐỌC (GIỮ NGUYÊN) ---

@router.get("", response_model=List[GroupPublic])
async def get_groups(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    return await group_service.get_all_groups(db)

@router.get("/{group_id}/access_levels", response_model=List[dict])
async def get_group_access_levels(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Lấy danh sách các cấp độ truy cập của một nhóm.
    """
    access_levels = await group_service.get_group_access_levels(db, group_id)
    return access_levels


@router.get("/{group_id}/users", response_model=List[UserPublic])
async def get_users_in_group(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin) 
):
    """
    Lấy danh sách tất cả người dùng trong một nhóm cụ thể (chỉ admin).
    """
    users = await group_service.get_users_in_group(db, group_id)
    if users is None: 
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm.") # Đã dịch lại thông báo lỗi
    return users


@router.get("/{group_id}", response_model=GroupPublic)
async def get_group_by_id(
    group_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin) 
):
    """
    Lấy thông tin chi tiết của một nhóm theo ID.
    """
    group = await group_service.get_group_by_id(db, str(group_id))
    if not group:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhóm.") # Đã dịch lại thông báo lỗi
    return group