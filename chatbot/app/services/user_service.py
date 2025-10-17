# app/services/user_service.py
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from passlib.hash import bcrypt

from typing import Optional, List 

from app.db.models import User, UserGroup, Group, GroupAccessLevel, AccessLevel, File, UserAccessFile # Thêm các models
from app.schemas.user_schema import UserCreate, UserInDB, UserUpdate

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import joinedload
from app.schemas.group_schema import GroupPublic # Thêm import này


class UserService:
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return bcrypt.hash(password)

    async def create_user(self, db: AsyncSession, user_data: UserCreate) -> Optional[UserInDB]:
        try:
            hashed_password = self.get_password_hash(user_data.password)
            new_user = User(
                id=str(uuid.uuid4()),
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                password_hash=hashed_password,
                role=user_data.role,
                is_active=user_data.is_active,
                created_at=datetime.utcnow()
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            return UserInDB.model_validate(new_user)
        except IntegrityError:
            await db.rollback()
            return None

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[UserInDB]:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalars().first()
        if user:
            return UserInDB.model_validate(user)
        return None

    async def get_all_users(self, db: AsyncSession) -> List[UserInDB]:
        result = await db.execute(select(User))
        users = result.scalars().all()
        return [UserInDB.model_validate(user) for user in users]

    async def get_user_by_id(self, db: AsyncSession, user_id: str) -> Optional[UserInDB]:
        user = await db.get(User, user_id)
        if user:
            return UserInDB.model_validate(user)
        return None

    async def update_user(self, db: AsyncSession, user_id: str, user_data: UserUpdate) -> Optional[UserInDB]:
        user = await db.get(User, user_id)
        if not user:
            return None

        update_data = user_data.model_dump(exclude_unset=True)
        
        # Xử lý password nếu có
        if "password" in update_data:
            update_data["password_hash"] = self.get_password_hash(update_data.pop("password"))

        # Kiểm tra email uniqueness nếu email được update
        if "email" in update_data and update_data["email"] != user.email:
            existing_user = await db.execute(select(User).where(User.email == update_data["email"]))
            if existing_user.scalars().first():
                return None  # Email đã tồn tại

        try:
            for key, value in update_data.items():
                setattr(user, key, value)

            await db.commit()
            await db.refresh(user)
            return UserInDB.model_validate(user)
        except IntegrityError:
            await db.rollback()
            return None

    async def delete_user(self, db: AsyncSession, user_id: str) -> bool:
        user = await db.get(User, user_id)
        if not user:
            return False
        await db.delete(user)
        await db.commit()
        return True

    async def update_last_login(self, db: AsyncSession, user_id: str) -> None:
        user = await db.get(User, user_id)
        if user:
            user.last_login = datetime.utcnow()
            await db.commit()

    async def get_user_access_levels(self, db: AsyncSession, user_id: UUID) -> Optional[List[dict]]:
        user = await db.execute(
            select(User)
            .options(
                joinedload(User.groups)
                .joinedload(Group.group_access_levels)
                .joinedload(GroupAccessLevel.access_level)
            )
            .filter(User.id == user_id)
        )
        user = user.scalars().first()
        
        if not user:
            return None
        
        access_levels = set()
        for ug_level in user.groups:
            for ga_level in ug_level.group_access_levels:
                access_levels.add(
                    (ga_level.access_level.id, ga_level.access_level.name, ga_level.access_level.description)
                )
        
        return [
            {"id": item[0], "name": item[1], "description": item[2]}
            for item in access_levels
        ]

    async def get_user_groups(self, db: AsyncSession, user_id: UUID) -> List[GroupPublic]:
        user = await db.execute(
            select(User)
            .options(joinedload(User.groups))
            .filter(User.id == user_id)
        )
        user = user.scalars().first()
        if not user:
            return []
        
        return [GroupPublic.model_validate(group) for group in user.groups]

    async def get_all_users_with_groups(self, db: AsyncSession) -> List[dict]:
        users = await db.execute(
            select(User).options(joinedload(User.groups))
        )
        users = users.scalars().unique().all()
        
        results = []
        for user in users:
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
                "groups": [
                    {"id": group.id, "name": group.name} for group in user.groups
                ]
            }
            results.append(user_data)
        
        return results


    async def get_users_with_accessible_files(self, db: AsyncSession) -> List[dict]:
        """
        Lấy danh sách tất cả người dùng kèm các file mà họ có thể truy cập.
        Sử dụng joinedload để tối ưu hiệu suất, chỉ cần 1 query duy nhất.
        """
        from sqlalchemy.orm import joinedload
        
        # Sử dụng joinedload để tải sẵn dữ liệu accessible_files và file liên quan
        result = await db.execute(
            select(User)
            .options(
                joinedload(User.accessible_files)
                .joinedload(UserAccessFile.file)
            )
        )
        
        # Sử dụng unique() để tránh trùng lặp do join
        users = result.unique().scalars().all()
        
        return [
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "files": [
                    {
                        "id": uaf.file.id,
                        "original_file_name": uaf.file.original_file_name,
                        "file_extension": uaf.file.file_extension,
                        "storage_path": uaf.file.storage_path
                    }
                    for uaf in user.accessible_files
                ]
            }
            for user in users
        ]