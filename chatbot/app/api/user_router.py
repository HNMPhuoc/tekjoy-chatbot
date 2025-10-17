# app/api/user_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Tuple, Any, Union # <-- Thêm Tuple, Any, Union
from datetime import datetime, timedelta
from uuid import UUID

from app.db.database import get_db
from app.schemas.user_schema import UserPublic, UserCreate, UserUpdate
from app.services.user_service import UserService
from app.core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from app.api.deps import get_current_active_user, get_current_active_admin
from jose import jwt

from app.schemas.group_schema import GroupPublic # Thêm import này
from app.core.db_retry import retry_on_deadlock # <-- THÊM IMPORT NÀY
import asyncio # <-- THÊM IMPORT NÀY

router = APIRouter()
user_service = UserService()

# Hàm helper để tạo thông báo tích cực
def create_positive_message(base_message: str, attempts: int) -> str:
    """Tạo thông báo thân thiện cho người dùng nếu thao tác thành công sau khi thử lại Deadlock."""
    if attempts > 1:
        return f"{base_message} sau {attempts} lần thử (Đã tự động xử lý tắc nghẽn hệ thống)."
    return base_message

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login")
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    user_in_db = await user_service.get_user_by_email(db, form_data.username)
    
    if not user_in_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # *** ĐÂY LÀ PHẦN QUAN TRỌNG NHẤT ***
    # Sử dụng asyncio.to_thread để chạy hàm blocking (đồng bộ) trong một thread riêng.
    # Điều này đảm bảo Event Loop không bị chặn trong quá trình tính toán hash/verify.
    is_verified = await asyncio.to_thread(
        user_service.verify_password,
        form_data.password,
        user_in_db.password_hash
    )
    
    if not is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_in_db.email}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        # Kết quả trả về là Tuple[UserPublic | None, int]
        result: Tuple[Union[UserPublic, None], int] = await retry_on_deadlock(
            user_service.create_user, db=db, user_data=user_data
        )
        user, attempts = result
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email đã được đăng ký."
            )
        
        if attempts > 1:
            # Ghi log nếu có retry
            print(create_positive_message(f"Đăng ký người dùng {user.email} thành công.", attempts))
            
        return user
    except HTTPException:
        raise
    except Exception as e:
        # Lỗi hệ thống không mong muốn
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi đăng ký người dùng: {str(e)}")


@router.get("/me", response_model=UserPublic)
async def read_current_user(current_user: UserPublic = Depends(get_current_active_user)):
    return current_user

@router.get("", response_model=List[UserPublic])
async def get_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    users = await user_service.get_all_users(db)
    return users

@router.put("/{user_id}", response_model=UserPublic)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        # Kết quả trả về là Tuple[UserPublic | None, int]
        result: Tuple[Union[UserPublic, None], int] = await retry_on_deadlock(
            user_service.update_user, db=db, user_id=user_id, user_data=user_data
        )
        user, attempts = result
        
        if not user:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        
        if attempts > 1:
            # Ghi log nếu có retry
            print(create_positive_message(f"Cập nhật người dùng {user.email} thành công.", attempts))

        return user
    except HTTPException:
        raise
    except Exception as e:
        # Lỗi hệ thống không mong muốn
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi cập nhật người dùng: {str(e)}")


@router.get("", response_model=List[UserPublic])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Lấy danh sách tất cả người dùng (chỉ dành cho admin).
    """
    return await user_service.get_all_users(db)


@router.get("/me/access_levels", response_model=List[dict])
async def get_my_access_levels(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Lấy danh sách các cấp độ truy cập của người dùng hiện tại.
    """
    access_levels = await user_service.get_user_access_levels(db, current_user.id)
    if not access_levels:
        raise HTTPException(status_code=404, detail="User not found or has no access levels.")
    return access_levels


@router.get("/me/groups", response_model=List[GroupPublic])
async def get_my_groups(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Lấy danh sách các nhóm mà người dùng hiện tại đang tham gia.
    """
    return await user_service.get_user_groups(db, current_user.id)


@router.get("/with_groups", response_model=List[dict])
async def get_all_users_with_groups(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Lấy danh sách tất cả người dùng và các nhóm mà họ đang tham gia (chỉ admin).
    """
    return await user_service.get_all_users_with_groups(db)


@router.get("/with_files", response_model=List[dict])
async def get_users_with_files(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)
):
    """
    Lấy danh sách tất cả người dùng kèm các file mà họ có quyền truy cập.
    Chỉ admin được phép gọi.
    """
    return await user_service.get_users_with_accessible_files(db)
    

@router.get("/{user_id}", response_model=UserPublic)
async def get_user_by_id(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)  # nếu muốn user tự xem chính mình thì đổi sang get_current_active_user
):
    """
    Lấy thông tin chi tiết của một người dùng theo ID.
    """
    user = await user_service.get_user_by_id(db, str(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_admin)  # Chỉ admin mới được xóa
):
    """
    Xóa một người dùng theo ID.
    """
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        # Kết quả trả về là Tuple[bool, int]
        result: Tuple[bool, int] = await retry_on_deadlock(
            user_service.delete_user, db=db, user_id=str(user_id)
        )
        success, attempts = result

        if not success:
            raise HTTPException(status_code=404, detail="Không tìm thấy người dùng.")
        
        if attempts > 1:
            # Ghi log nếu có retry
            print(create_positive_message(f"Xóa người dùng {user_id} thành công.", attempts))

        return None  # HTTP 204: không có body
    except HTTPException:
        raise
    except Exception as e:
        # Lỗi hệ thống không mong muốn
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi xóa người dùng: {str(e)}")