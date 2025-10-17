# app/services/group_service.py
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
from uuid import UUID # <-- Thêm import UUID
from app.db.models import Group, User, UserGroup, GroupAccessLevel, AccessLevel 
from app.schemas.group_schema import GroupCreate, GroupPublic, GroupUpdate
from sqlalchemy.orm import joinedload
from app.schemas.user_schema import UserPublic
import logging
from sqlalchemy import delete

logger = logging.getLogger(__name__)

class GroupService:
    async def create_group(self, db: AsyncSession, group_data: GroupCreate) -> Optional[GroupPublic]:
        try:
            new_group = Group(
                id=str(uuid.uuid4()),
                name=group_data.name,
                description=group_data.description
            )
            db.add(new_group)
            await db.commit()
            await db.refresh(new_group)
            return GroupPublic.model_validate(new_group)
        except IntegrityError:
            await db.rollback()
            return None

    async def get_all_groups(self, db: AsyncSession) -> List[GroupPublic]:
        result = await db.execute(select(Group))
        groups = result.scalars().all()
        return [GroupPublic.model_validate(group) for group in groups]

    async def get_group_by_id(self, db: AsyncSession, group_id: str) -> Optional[GroupPublic]:
        group = await db.get(Group, group_id)
        if group:
            return GroupPublic.model_validate(group)
        return None

    async def update_group(self, db: AsyncSession, group_id: str, group_data: GroupUpdate) -> Optional[GroupPublic]:
        group = await db.get(Group, group_id)
        if not group:
            return None

        update_data = group_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(group, key, value)
            
        await db.commit()
        await db.refresh(group)
        return GroupPublic.model_validate(group)

    async def delete_group(self, db: AsyncSession, group_id: str) -> bool:
        group = await db.get(Group, group_id)
        if not group:
            return False
        await db.delete(group)
        await db.commit()
        return True

    async def add_users_to_group(self, db: AsyncSession, group_id: UUID, user_ids: List[UUID]) -> bool:
        try:
            # 1. Kiểm tra tồn tại của Group (Giữ nguyên)
            group = await db.get(Group, group_id)
            if not group:
                return False

            # 2. Lấy TẤT CẢ các User hợp lệ trong danh sách user_ids (Giảm thiểu truy vấn)
            # Điều này giúp khóa (lock) các hàng User cần thiết một cách hiệu quả hơn.
            stmt_valid_users = select(User.id).where(User.id.in_(user_ids))
            valid_user_ids = (await db.execute(stmt_valid_users)).scalars().all()

            if not valid_user_ids:
                return True # Không có người dùng hợp lệ nào để thêm

            # 3. Lấy TẤT CẢ các mối quan hệ UserGroup ĐÃ TỒN TẠI
            # Sử dụng các ID hợp lệ để truy vấn.
            stmt_existing = select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id.in_(valid_user_ids)
            )
            existing_user_groups = (await db.execute(stmt_existing)).scalars().all()

            # Chuyển các cặp user_id đã tồn tại thành một set để tra cứu nhanh O(1)
            existing_user_id_set = {ug.user_id for ug in existing_user_groups}

            # 4. Tạo danh sách các mối quan hệ mới cần thêm
            new_user_groups = []
            for user_id in valid_user_ids:
                if user_id not in existing_user_id_set:
                    # Chuyển UUID về chuỗi nếu model UserGroup yêu cầu (Giả định là UUID)
                    new_user_groups.append(UserGroup(user_id=user_id, group_id=group_id))

            if not new_user_groups:
                return True

            # 5. Thêm tất cả các mối quan hệ mới và commit (Tối ưu hóa)
            db.add_all(new_user_groups)
            await db.commit()
            return True
            
        except IntegrityError:
            # Vẫn giữ rollback/return False để xử lý các vấn đề toàn vẹn khác
            await db.rollback()
            return False
        # Bạn có thể cân nhắc bỏ try/except ở đây nếu bạn muốn retry_on_deadlock
        # bắt được các Deadlock (Deadlock là một loại IntegrityError).
        # Tuy nhiên, cách làm hiện tại vẫn an toàn.
        except Exception:
            await db.rollback()
            raise # Để các Exception khác (không phải Deadlock/IntegrityError) được đẩy ra ngoài

    async def get_group_access_levels(self, db: AsyncSession, group_id: UUID) -> Optional[List[dict]]:
        group = await db.execute(
            select(Group)
            .options(joinedload(Group.group_access_levels).joinedload(GroupAccessLevel.access_level))
            .filter(Group.id == group_id)
        )
        group = group.scalars().first()
        
        if not group:
            return None
        
        access_levels = []
        for ga_level in group.group_access_levels:
            access_levels.append({
                "id": ga_level.access_level.id,
                "name": ga_level.access_level.name,
                "description": ga_level.access_level.description
            })
        
        return access_levels

    async def get_users_in_group(self, db: AsyncSession, group_id: UUID) -> Optional[List[UserPublic]]:
        group = await db.get(
            Group,
            group_id,
            options=[joinedload(Group.users_associated).joinedload(UserGroup.user)]
        )
        if not group:
            return None   # khác [] để route phân biệt group không tồn tại

        users = [ug.user for ug in group.users_associated]
        return [UserPublic.model_validate(user) for user in users]


    async def remove_user_from_group(self, db: AsyncSession, group_id: UUID, user_id: UUID) -> bool:
        # Tìm bản ghi liên kết giữa user và group
        user_group = await db.execute(
            select(UserGroup).where(
                UserGroup.group_id == group_id,
                UserGroup.user_id == user_id
            )
        )
        user_group_to_delete = user_group.scalars().first()
        
        if not user_group_to_delete:
            return False
            
        await db.delete(user_group_to_delete)
        await db.commit()
        return True

    async def update_group_users(self, db: AsyncSession, group_id: UUID, new_user_ids: List[UUID]) -> bool:
        try:
            group = await db.get(Group, group_id)
            if not group:
                return False

            new_user_ids_set = set(new_user_ids)
            
            # 1. Lấy TẤT CẢ các mối quan hệ HIỆN CÓ
            stmt_existing = select(UserGroup).where(UserGroup.group_id == group_id)
            existing_associations = (await db.execute(stmt_existing)).scalars().all()
            existing_user_ids_set = {assoc.user_id for assoc in existing_associations}

            # --- A. XỬ LÝ XÓA HÀNG LOẠT ---
            
            # ID người dùng cần xóa (có trong cũ, không có trong mới)
            user_ids_to_remove = existing_user_ids_set - new_user_ids_set

            # Trường hợp gửi user_ids: [], user_ids_to_remove sẽ bằng existing_user_ids_set
            # => TẤT CẢ sẽ bị xóa. Đây là hành vi đúng.
            
            if user_ids_to_remove:
                stmt_delete = delete(UserGroup).where(
                    UserGroup.group_id == group_id,
                    UserGroup.user_id.in_(user_ids_to_remove)
                )
                await db.execute(stmt_delete)
            
            # --- B. XỬ LÝ THÊM HÀNG LOẠT ---
            
            # ID người dùng cần thêm (có trong mới, không có trong cũ)
            user_ids_to_add = new_user_ids_set - existing_user_ids_set

            if user_ids_to_add:
                # 1. Kiểm tra TẤT CẢ người dùng có tồn tại không (1 lệnh SELECT IN)
                stmt_valid_users = select(User.id).where(User.id.in_(user_ids_to_add))
                valid_user_ids = (await db.execute(stmt_valid_users)).scalars().all()
                
                # 2. Tạo danh sách các đối tượng UserGroup mới
                new_associations = []
                for user_id in valid_user_ids:
                    new_associations.append(UserGroup(user_id=user_id, group_id=group_id))

                if new_associations:
                    db.add_all(new_associations)
            
            # 3. COMMIT TẤT CẢ CÁC THAY ĐỔI
            
            # Chỉ cần commit nếu có thay đổi (xóa hoặc thêm)
            # Nếu không có gì để xóa VÀ không có gì để thêm, có thể skip commit,
            # nhưng commit an toàn hơn nếu đã có thao tác execute delete()
            await db.commit()
            return True

        except Exception:
            # Giữ nguyên rollback và raise/return False
            await db.rollback()
            # logger.error/print (giữ logic của bạn)
            return False