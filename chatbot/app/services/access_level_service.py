# app/services/access_level_service.py
import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from app.db.models import AccessLevel, Group, GroupAccessLevel, UserGroup, FileAccessLevel 
from app.schemas.access_level_schema import AccessLevelCreate, AccessLevelUpdate, AccessLevelPublic
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import joinedload
from app.db.models import File # Added this import to resolve the NameError
from sqlalchemy import delete # Cần import delete
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import hashlib  

class AccessLevelService:
    async def create_access_level(self, db: AsyncSession, level_data: AccessLevelCreate, created_by_id: str) -> Optional[AccessLevelPublic]:
        try:
            new_level = AccessLevel(
                id=str(uuid.uuid4()),
                name=level_data.name,
                description=level_data.description,
                is_default=level_data.is_default,
                created_by_user_id=created_by_id
            )
            db.add(new_level)
            await db.commit()
            await db.refresh(new_level)
            return AccessLevelPublic.model_validate(new_level)
        except IntegrityError:
            await db.rollback()
            return None

    async def get_all_access_levels(self, db: AsyncSession) -> List[AccessLevelPublic]:
        result = await db.execute(select(AccessLevel))
        levels = result.scalars().all()
        return [AccessLevelPublic.model_validate(level) for level in levels]

    async def update_access_level(self, db: AsyncSession, level_id: UUID, level_data: AccessLevelUpdate) -> Optional[AccessLevelPublic]:
        level = await db.get(AccessLevel, level_id)
        if not level:
            return None
        
        update_data = level_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(level, key, value)
        
        await db.commit()
        await db.refresh(level)
        return AccessLevelPublic.model_validate(level)

    async def delete_access_level(self, db: AsyncSession, level_id: UUID) -> bool:
        level = await db.get(AccessLevel, level_id)
        if not level:
            return False
        await db.delete(level)
        await db.commit()
        return True

    async def assign_access_levels_to_group(self, db: AsyncSession, group_id: UUID, access_level_ids: List[UUID]) -> bool:
        try:
            # 1. Kiểm tra tồn tại Group
            group = await db.get(Group, group_id)
            if not group:
                return False
                
            # 2. Xác minh tất cả AccessLevel hợp lệ (1 lệnh SELECT IN)
            # Lấy ID của các AccessLevel thực sự tồn tại trong DB
            valid_level_ids_stmt = select(AccessLevel.id).where(AccessLevel.id.in_(access_level_ids))
            valid_level_ids = set((await db.execute(valid_level_ids_stmt)).scalars().all())

            if not valid_level_ids and not access_level_ids:
                # Nếu danh sách gửi lên trống và không có level hợp lệ, tiếp tục xử lý xóa
                pass
            elif not valid_level_ids and access_level_ids:
                # Nếu có ID gửi lên nhưng không có cái nào hợp lệ, vẫn phải đảm bảo xóa các cái cũ
                pass
            
            # 3. Lấy tất cả mối quan hệ GroupAccessLevel hiện có
            stmt_existing = select(GroupAccessLevel).where(GroupAccessLevel.group_id == group_id)
            existing_associations = (await db.execute(stmt_existing)).scalars().all()
            
            # ID của các AccessLevel hiện đang được gán cho nhóm này
            existing_level_ids = {assoc.access_level_id for assoc in existing_associations}

            # --- TÍNH TOÁN KHÁC BIỆT ---

            # 4. Xác định những ID cần XÓA (có trong cũ, không có trong mới/hợp lệ)
            level_ids_to_remove = existing_level_ids - valid_level_ids

            # 5. Xác định những ID cần THÊM (có trong mới/hợp lệ, không có trong cũ)
            level_ids_to_add = valid_level_ids - existing_level_ids
            
            # --- THỰC THI THAY ĐỔI HÀNG LOẠT (BULK OPERATIONS) ---

            has_changes = False

            # 6. Xóa hàng loạt (1 lệnh DELETE duy nhất)
            if level_ids_to_remove:
                stmt_delete = delete(GroupAccessLevel).where(
                    GroupAccessLevel.group_id == group_id,
                    GroupAccessLevel.access_level_id.in_(level_ids_to_remove)
                )
                await db.execute(stmt_delete)
                has_changes = True

            # 7. Thêm hàng loạt (db.add_all)
            if level_ids_to_add:
                new_assignments = []
                for level_id in level_ids_to_add:
                    new_assignments.append(GroupAccessLevel(group_id=group_id, access_level_id=level_id))
                
                db.add_all(new_assignments)
                has_changes = True

            # 8. Commit
            if has_changes:
                await db.commit()
            else:
                # Nếu không có thay đổi nào, không cần commit
                pass 
                
            return True
            
        except IntegrityError:
            await db.rollback()
            return False
        except Exception:
            await db.rollback()
            raise # Đẩy lỗi ra ngoài để được bắt bởi retry_on_deadlock

    async def get_access_level_with_groups_and_users(self, db: AsyncSession, level_id: UUID) -> Optional[dict]:
            result = await db.execute(
                select(AccessLevel)
                .options(joinedload(AccessLevel.group_access_levels).joinedload(GroupAccessLevel.group).joinedload(Group.users))
                .filter(AccessLevel.id == level_id)
            )
            level = result.scalars().first()
            
            if not level:
                return None
            
            level_data = {
                "id": level.id,
                "name": level.name,
                "description": level.description,
                "groups": []
            }
            
            for ga_level in level.group_access_levels:
                group_data = {
                    "id": ga_level.group.id,
                    "name": ga_level.group.name,
                    "users": [
                        {"id": u.id, "username": u.username, "email": u.email}
                        for u in ga_level.group.users
                    ]
                }
                level_data["groups"].append(group_data)
                
            return level_data

 # ----- CÁC HÀM MỚI CHO FILES -----
    async def assign_access_levels_to_file(self, db: AsyncSession, file_id: UUID, access_level_ids: List[UUID]) -> bool:
        """Gán các cấp độ truy cập cho một tệp tin."""
        try:
            lock_id = int(hashlib.md5(str(file_id).encode()).hexdigest()[:15], 16)
            await db.execute(
                text("SELECT pg_advisory_xact_lock(:lock_id)"),
                    {"lock_id": lock_id}
                )
            file = await db.get(File, file_id)
            if not file:
                return False
            sql = text("""
                    WITH valid_levels AS (
                        SELECT id FROM access_levels 
                        WHERE id = ANY(:ids)
                    ),
                    deleted AS (
                        DELETE FROM file_access_levels
                        WHERE file_id = :file_id
                        AND access_level_id NOT IN (SELECT id FROM valid_levels)
                        RETURNING access_level_id
                    ),
                    inserted AS (
                        INSERT INTO file_access_levels (file_id, access_level_id)
                        SELECT :file_id, id FROM valid_levels
                        ON CONFLICT (file_id, access_level_id) DO NOTHING
                        RETURNING access_level_id
                    )
                    SELECT 
                        (SELECT COUNT(*) FROM deleted) as deleted_count,
                        (SELECT COUNT(*) FROM inserted) as inserted_count;
                """)
                
            await db.execute(
                    sql, 
                    {
                        "file_id": str(file_id), 
                        "ids": [str(id) for id in access_level_ids]
                    }
                )
            return True
        except IntegrityError:
            await db.rollback()
            return False

    async def get_file_access_levels(self, db: AsyncSession, file_id: UUID) -> Optional[List[dict]]:
        """Lấy tất cả cấp độ truy cập của một tệp tin."""
        file = await db.execute(
            select(File)
            .options(joinedload(File.access_levels).joinedload(FileAccessLevel.access_level))
            .filter(File.id == file_id)
        )
        file = file.scalars().first()

        if not file:
            return None

        access_levels = []
        for fa_level in file.access_levels:
            access_levels.append({
                "id": fa_level.access_level.id,
                "name": fa_level.access_level.name,
                "description": fa_level.access_level.description,
                "created_by_user_id": fa_level.access_level.created_by_user_id,
                "created_at": fa_level.access_level.created_at
            })
        
        return access_levels

    async def remove_access_levels_from_file(self, db: AsyncSession, file_id: UUID, access_level_ids: List[UUID]) -> bool:
        """Xóa các cấp độ truy cập khỏi một tệp tin."""
        # Check if file exists
        file = await db.get(File, str(file_id))
        if not file:
            return False
        
        # Delete associations for the specified access level IDs and file
        delete_q = FileAccessLevel.__table__.delete().where(
            FileAccessLevel.file_id == str(file_id),
            FileAccessLevel.access_level_id.in_([str(uid) for uid in access_level_ids])
        )
        await db.execute(delete_q)
        await db.commit()
        return True
            
    async def get_access_level_by_id(self, db: AsyncSession, level_id: UUID) -> Optional[AccessLevelPublic]:
        level = await db.get(AccessLevel, level_id)
        if level:
            return AccessLevelPublic.model_validate(level)
        return None
