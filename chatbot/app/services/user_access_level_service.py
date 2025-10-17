from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
# from app.db.models import Folder, File, User, UserGroup, GroupAccessLevel, FileAccessLevel, AccessLevel, Group
from app.db.models import UserAccessFile  # Import model UserAccessFile

# file: user_access_level_service.py
class UserAccessLevelService:
    async def refresh_user_access_files(self, db: AsyncSession, user_id: str, is_admin: bool, files: list):
        """
        Xóa quyền cũ của user và insert lại toàn bộ file mà user có quyền truy cập
        """
        # 1. Lấy danh sách file user có quyền
        # Dòng này cần được xóa đi vì danh sách files đã được truyền vào
        # files = await self.get_accessible_filesV2(db, user_id, is_admin)

        # 2. Xóa quyền cũ
        await db.execute(
            delete(UserAccessFile).where(UserAccessFile.user_id == user_id)
        )

        # 3. Insert quyền mới
        new_records = [
            UserAccessFile(user_id=user_id, file_id=file.id)
            for file in files
        ]
        db.add_all(new_records)

        # 4. Commit
        await db.commit()

        return len(new_records)
