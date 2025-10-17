from pathlib import Path
import shutil
import os
from typing import List, Optional, Union, Dict, Any, BinaryIO
from uuid import UUID, uuid4
from datetime import datetime, timezone, date, timedelta
import logging
import asyncio
from fastapi import UploadFile, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, DBAPIError
from sqlalchemy.orm import joinedload, aliased
from app.services.user_access_level_service import UserAccessLevelService
from datetime import timedelta, datetime, timezone
from sqlalchemy import select, distinct, or_, union, func, and_, exists
from functools import wraps

def db_transaction(timeout: int = 30):
    """Decorator để quản lý transaction với timeout"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            db = kwargs.get('db')
            if not db or not isinstance(db, AsyncSession):
                raise ValueError("Thiếu tham số db hoặc không phải AsyncSession")
                
            try:
                # Bắt đầu transaction với timeout
                await db.execute(f"SET statement_timeout TO {timeout * 1000}")
                result = await func(*args, **kwargs)
                await db.commit()
                return result
            except Exception as e:
                await db.rollback()
                raise
        return wrapper
    return decorator

from app.db.models import (
    Folder, File, User, UserGroup, GroupAccessLevel, 
    FileAccessLevel, AccessLevel, Group
)
from app.schemas.folder_file_schema import (
    FolderPublic, FolderCreate, FolderUpdate,
    FilePublic, FileCreate, FileUpdate, FolderContentResponse
)
from app.services.postgres_service import postgres_service
from app.services.user_access_level_service import UserAccessLevelService

logger = logging.getLogger(__name__)

class DocumentService:
    def __init__(self):
        """Khởi tạo service và tạo các thư mục cần thiết."""
        self.base_dir = Path.cwd()
        self.upload_dir = self.base_dir / "uploads"
        self.temp_dir = self.base_dir / "temp"
        self.max_file_size = 100 * 1024 * 1024  # 100MB
        self.allowed_file_types = {
            'image': ['image/jpeg', 'image/png', 'image/gif'],
            'document': ['application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
            'pdf': ['application/pdf'],
            'spreadsheet': ['application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
            'text': ['text/plain']
        }
        
        # Dictionary để theo dõi các upload đang diễn ra
        self.active_uploads = {}
        
        # Tạo các thư mục nếu chưa tồn tại
        self._setup_directories()
    
    def _setup_directories(self) -> None:
        """Tạo các thư mục cần thiết nếu chưa tồn tại."""
        try:
            self.upload_dir.mkdir(parents=True, exist_ok=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Đã khởi tạo thư mục: {self.upload_dir}")
            logger.info(f"Đã khởi tạo thư mục tạm: {self.temp_dir}")
        except OSError as e:
            logger.error(f"Lỗi khi tạo thư mục: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể tạo thư mục: {e}"
            )
    
    @staticmethod
    async def _safe_delete_file(file_path: Union[str, Path]) -> bool:
        """Xóa file một cách an toàn.
        
        Args:
            file_path: Đường dẫn đến file cần xóa (str hoặc Path)
            
        Returns:
            bool: True nếu xóa thành công hoặc file không tồn tại, False nếu có lỗi
        """
        try:
            path = Path(file_path) if isinstance(file_path, str) else file_path
            if await run_in_threadpool(path.exists):
                await run_in_threadpool(lambda p: p.unlink(missing_ok=True), path)
                logger.debug(f"Đã xóa file: {path}")
            return True
        except Exception as e:
            logger.error(f"Lỗi khi xóa file {file_path}: {e}")
            return False
            
    async def cleanup_upload_file(self, file_path: Union[str, Path]) -> bool:
        """Xóa file tạm sau khi đã trích xuất OCR.
        
        Args:
            file_path: Đường dẫn đến file cần xóa (str hoặc Path)
            
        Returns:
            bool: True nếu xóa thành công, False nếu có lỗi
        """
        try:
            # Kiểm tra xem file_path có thuộc thư mục uploads không
            path = Path(file_path) if isinstance(file_path, str) else file_path
            if self.upload_dir in path.parents or str(self.upload_dir) in str(path):
                result = await self._safe_delete_file(path)
                if result:
                    logger.info(f"Đã xóa file tạm sau khi OCR: {path}")
                return result
            else:
                logger.warning(f"Không xóa file không thuộc thư mục uploads: {path}")
                return False
        except Exception as e:
            logger.error(f"Lỗi khi xóa file tạm {file_path}: {e}")
            return False
            
    def register_upload(self, upload_id: str, file_info: dict) -> None:
        """Đăng ký một upload đang diễn ra.
        
        Args:
            upload_id: ID của upload
            file_info: Thông tin về file đang upload
        """
        self.active_uploads[upload_id] = file_info
        
    def get_upload_info(self, upload_id: str) -> dict:
        """Lấy thông tin về một upload đang diễn ra.
        
        Args:
            upload_id: ID của upload
            
        Returns:
            dict: Thông tin về upload hoặc None nếu không tồn tại
        """
        return self.active_uploads.get(upload_id)
        
    async def cancel_upload(self, upload_id: str, db: AsyncSession) -> dict:
        """Hủy một upload đang diễn ra.
        
        Args:
            upload_id: ID của upload cần hủy
            db: Database session
            
        Returns:
            dict: Kết quả hủy upload
        """
        upload_info = self.active_uploads.get(upload_id)
        if not upload_info:
            return {"success": False, "message": "Upload không tồn tại hoặc đã hoàn thành"}
            
        # Xóa file tạm nếu đã được lưu
        if "storage_path" in upload_info:
            await self.cleanup_upload_file(upload_info["storage_path"])
            
        # Xóa thông tin file khỏi database nếu đã được tạo
        if "file_id" in upload_info:
            try:
                file_id = upload_info["file_id"]
                file = await db.get(File, file_id)
                if file:
                    await db.delete(file)
                    await db.commit()
                    logger.info(f"Đã xóa file {file_id} từ database")
            except Exception as e:
                logger.error(f"Lỗi khi xóa file từ database: {e}")
                await db.rollback()
                
        # Xóa khỏi danh sách active uploads
        self.active_uploads.pop(upload_id, None)
        
        return {"success": True, "message": "Đã hủy upload thành công"}
            
    async def create_folder(self, db: AsyncSession, folder_data: FolderCreate, user_id: UUID) -> Optional[FolderPublic]:
        """Tạo một thư mục mới."""
        try:
            new_folder = Folder(
                id=str(uuid4()),
                name=folder_data.name,
                parent_id=str(folder_data.parent_id) if folder_data.parent_id else None,
                created_by_user_id=str(user_id)
            )
            db.add(new_folder)
            await db.commit()
            await db.refresh(new_folder)
            return FolderPublic.model_validate(new_folder)
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Lỗi khi tạo thư mục: {e}")
            return None
            
    async def get_all_folders(self, db: AsyncSession) -> List[FolderPublic]:
        """Lấy tất cả các thư mục."""
        result = await db.execute(select(Folder))
        folders = result.scalars().all()
        return [FolderPublic.model_validate(folder) for folder in folders]

    @db_transaction(timeout=30)
    async def get_accessible_filesV2(
        self,
        db: AsyncSession,
        user_id: str,
        is_admin: bool = False,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        file_type: Optional[str] = None,
        sort_by: str = "upload_timestamp",
        sort_order: str = "desc"
    ) -> Dict[str, Any]:
        """Lấy danh sách file có thể truy cập với phân trang và lọc.
        
        Args:
            db: Database session
            user_id: ID người dùng
            is_admin: Có phải là admin hay không
            page: Số trang hiện tại (bắt đầu từ 1)
            page_size: Số lượng bản ghi mỗi trang
            search: Từ khóa tìm kiếm trong tên file
            file_type: Lọc theo loại file (image, document, pdf, ...)
            sort_by: Trường sắp xếp (upload_timestamp, file_name, file_size)
            sort_order: Thứ tự sắp xếp (asc, desc)
            
        Returns:
            Dict[str, Any]: Kết quả phân trang với danh sách file và thông tin phân trang
            
        Raises:
            HTTPException: Nếu có lỗi xảy ra
        """
        try:
            # Validate và chuẩn hóa tham số
            page = max(1, page)
            page_size = min(max(1, page_size), 100)  # Giới hạn tối đa 100 bản ghi/trang
            offset = (page - 1) * page_size
            
            # Xác định thứ tự sắp xếp
            sort_column = {
                "upload_timestamp": File.upload_timestamp,
                "file_name": File.file_name,
                "file_size": File.file_size,
                "file_type": File.file_type
            }.get(sort_by, File.upload_timestamp)
            
            sort_expression = sort_column.desc() if sort_order.lower() == "desc" else sort_column.asc()
            
            if is_admin:
                # Admin có quyền xem tất cả file
                base_query = select(File)
                count_query = select(func.count(File.id))
            else:
                # Người dùng thường chỉ xem được file của họ hoặc file được chia sẻ
                # Lấy file từ group
                group_stmt = (
                    select(File.id)
                    .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
                    .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
                    .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
                    .join(Group, Group.id == GroupAccessLevel.group_id)
                    .join(UserGroup, UserGroup.group_id == Group.id)
                    .where(UserGroup.user_id == user_id)
                )
                
                # Lấy file do chính user tạo
                owner_stmt = select(File.id).where(File.uploaded_by_user_id == user_id)
                
                # Kết hợp cả 2 nguồn
                file_ids_union = union(group_stmt, owner_stmt).subquery()
                base_query = select(File).where(File.id.in_(select(file_ids_union.c.id)))
                count_query = select(func.count()).select_from(file_ids_union)
            
            # Áp dụng bộ lọc tìm kiếm
            if search:
                search = f"%{search.lower()}%"
                base_query = base_query.where(func.lower(File.file_name).like(search))
                
            # Áp dụng bộ lọc loại file
            if file_type and file_type in self.allowed_file_types:
                base_query = base_query.where(File.file_type.in_(self.allowed_file_types[file_type]))
            
            # Thực hiện đếm tổng số bản ghi
            total = await db.scalar(count_query) or 0
            
            # Lấy dữ liệu phân trang
            stmt = (
                base_query
                .order_by(sort_expression)
                .limit(page_size)
                .offset(offset)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            
            # Tính toán số trang
            total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
            
            return {
                "items": [FilePublic.model_validate(f) for f in rows],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_previous": page > 1
            }
            
        except (SQLAlchemyError, DBAPIError) as e:
            logger.error(f"Lỗi database khi lấy danh sách file V2: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Lỗi hệ thống, vui lòng thử lại sau"
            )
            
        except Exception as e:
            logger.error(f"Lỗi không xác định khi lấy danh sách file V2: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Đã xảy ra lỗi không xác định"
            )

    @db_transaction(timeout=300)
    async def refresh_access_files_batch(
        self, 
        db: AsyncSession, 
        user_id: str, 
        is_admin: bool = False,
        batch_size: int = 100
    ) -> Dict[str, Any]:
        """
        Cập nhật quyền truy cập file cho user theo từng batch để tránh quá tải.
        
        Args:
            db: Database session
            user_id: ID của người dùng cần cập nhật quyền
            is_admin: Có phải là admin hay không
            batch_size: Số lượng file xử lý trong mỗi batch
            
        Returns:
            Dict[str, Any]: Thông tin về quá trình cập nhật
            
        Raises:
            HTTPException: Nếu có lỗi xảy ra
        """
        try:
            logger.info(f"Bắt đầu làm mới quyền truy cập file cho user {user_id}")
            start_time = datetime.utcnow()
            
            # Lấy tổng số file cần xử lý
            if is_admin:
                total_files = await db.scalar(select(func.count(File.id)))
            else:
                # Đếm số lượng file từ group
                group_count = select(func.count(distinct(File.id)))\
                    .join(FileAccessLevel, FileAccessLevel.file_id == File.id)\
                    .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)\
                    .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)\
                    .join(Group, Group.id == GroupAccessLevel.group_id)\
                    .join(UserGroup, UserGroup.group_id == Group.id)\
                    .where(UserGroup.user_id == user_id)
                
                # Đếm số lượng file do chính user tạo
                owner_count = select(func.count(File.id))\
                    .where(File.uploaded_by_user_id == user_id)
                
                # Tính tổng (tránh đếm trùng lặp)
                group_count = await db.scalar(group_count) or 0
                owner_count = await db.scalar(owner_count) or 0
                
                # Đây chỉ là ước tính, có thể có sự trùng lặp giữa 2 tập hợp
                total_files = group_count + owner_count
            
            if total_files == 0:
                logger.info(f"Không có file nào cần cập nhật quyền cho user {user_id}")
                return {
                    "status": "success",
                    "message": "Không có file nào cần cập nhật",
                    "total_files": 0,
                    "processed_files": 0,
                    "duration_seconds": 0
                }
            
            logger.info(f"Tìm thấy {total_files} file cần cập nhật quyền cho user {user_id}")
            
            # Khởi tạo service
            user_access_service = UserAccessLevelService()
            processed_files = 0
            
            # Xử lý từng batch
            for offset in range(0, total_files, batch_size):
                # Lấy danh sách file cho batch hiện tại
                if is_admin:
                    stmt = select(File).offset(offset).limit(batch_size)
                else:
                    # Lấy file từ group
                    group_files = (
                        select(File)
                        .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
                        .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
                        .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
                        .join(Group, Group.id == GroupAccessLevel.group_id)
                        .join(UserGroup, UserGroup.group_id == Group.id)
                        .where(UserGroup.user_id == user_id)
                    )
                    
                    # Lấy file do chính user tạo
                    owner_files = select(File).where(File.uploaded_by_user_id == user_id)
                    
                    # Kết hợp và phân trang
                    stmt = union(group_files, owner_files).offset(offset).limit(batch_size)
                
                result = await db.execute(stmt)
                files = result.scalars().all()
                
                if not files:
                    break
                    
                # Cập nhật quyền cho batch hiện tại
                await user_access_service.refresh_user_access_files(
                    db, 
                    user_id=user_id, 
                    is_admin=is_admin, 
                    files=files
                )
                
                processed_files += len(files)
                logger.info(f"Đã xử lý {processed_files}/{total_files} file")
                
                # Giải phóng bộ nhớ
                del files
                
            duration = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Hoàn thành cập nhật quyền cho {processed_files} file trong {duration:.2f} giây")
            
            return {
                "status": "success",
                "message": f"Đã cập nhật quyền cho {processed_files} file",
                "total_files": total_files,
                "processed_files": processed_files,
                "duration_seconds": duration
            }
            
        except (SQLAlchemyError, DBAPIError) as e:
            logger.error(f"Lỗi database khi làm mới quyền truy cập file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Lỗi hệ thống khi cập nhật quyền truy cập"
            )
            
        except Exception as e:
            logger.error(f"Lỗi không xác định khi làm mới quyền truy cập file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Đã xảy ra lỗi không xác định khi cập nhật quyền"
            )

    async def get_folder_by_id(self, db: AsyncSession, folder_id: UUID) -> Optional[FolderPublic]:
        """Lấy một thư mục bằng ID."""
        folder = await db.get(Folder, str(folder_id))
        if folder:
            return FolderPublic.model_validate(folder)
        return None

    async def update_folder(self, db: AsyncSession, folder_id: UUID, folder_data: FolderUpdate, 
                          user_id: UUID, is_admin: bool) -> Optional[FolderPublic]:
        """Cập nhật một thư mục (chỉ admin hoặc người tạo)."""
        folder = await db.get(Folder, str(folder_id))
        if not folder:
            return None
        
        # Kiểm tra quyền
        if not is_admin and str(folder.created_by_user_id) != str(user_id):
            return None

        # Cập nhật dữ liệu
        update_data = folder_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == 'parent_id' and value is not None:
                setattr(folder, key, str(value))
            else:
                setattr(folder, key, value)
        
        try:
            await db.commit()
            await db.refresh(folder)
            return FolderPublic.model_validate(folder)
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Lỗi khi cập nhật thư mục {folder_id}: {e}")
            return None

    async def delete_folder(self, db: AsyncSession, folder_id: UUID, 
                          user_id: UUID, is_admin: bool) -> bool:
        """Xóa một thư mục (chỉ admin hoặc người tạo)."""
        folder = await db.get(Folder, str(folder_id))
        if not folder:
            return False
        
        # Kiểm tra quyền
        if not is_admin and str(folder.created_by_user_id) != str(user_id):
            return False
            
        try:
            await db.delete(folder)
            await db.commit()
            return True
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Lỗi khi xóa thư mục {folder_id}: {e}")
            return False

    async def _save_file_chunks(self, file: UploadFile, filepath: Path, chunk_size: int = 1024 * 1024) -> int:
        """Lưu file theo từng chunk để tiết kiệm bộ nhớ.
        
        Args:
            file: File upload từ client
            filepath: Đường dẫn đích để lưu file
            chunk_size: Kích thước mỗi chunk (mặc định 1MB)
            
        Returns:
            int: Tổng kích thước file đã lưu (bytes)
        """
        total_size = 0
        try:
            # Mở file đích để ghi nhị phân
            with open(filepath, 'wb') as f:
                # Đọc và ghi từng chunk
                while True:
                    # Đọc chunk từ file upload (đồng bộ)
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    # Ghi chunk vào file đích (đồng bộ, chạy trong thread pool)
                    await run_in_threadpool(f.write, chunk)
                    total_size += len(chunk)
                    
                    # Kiểm tra kích thước tối đa (50MB)
                    if total_size > 50 * 1024 * 1024:  # 50MB
                        # Xóa file nếu vượt quá giới hạn
                        await self._safe_delete_file(filepath)
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Kích thước file vượt quá giới hạn 50MB"
                        )
            
            return total_size
            
        except IOError as e:
            await self._safe_delete_file(filepath)
            logger.error(f"Lỗi khi lưu file {file.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Không thể lưu file: {e}"
            )

    async def save_upload_file(self, file: UploadFile, user_id: str = None, **kwargs) -> dict:
        """Xử lý lưu file upload và lưu thông tin vào PostgreSQL."""
        # Tạo tên file duy nhất
        utc_time = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        filename = f"{utc_time}_{file.filename}"
        filepath = self.upload_dir / filename
        
        try:
            # Lưu file từng chunk
            file_size = await self._save_file_chunks(file, filepath)
            logger.info(f"Đã lưu file {file.filename} thành công, kích thước: {file_size} bytes")

            # Chuẩn bị dữ liệu để lưu vào database
            file_info = {
                "original_file_name": file.filename,
                "file_extension": filepath.suffix[1:],  # Bỏ dấu . ở đầu
                "mime_type": file.content_type,
                "file_size_bytes": file_size,
                "storage_path": str(filepath.absolute()),
                "download_link": f"/uploads/{filename}",
                "uploaded_by_user_id": user_id,
                "processing_status": "uploaded"
            }
            
            # Thêm các thông tin bổ sung nếu có
            file_info.update(kwargs)
            
            # Lưu thông tin vào database
            try:
                result = await postgres_service.insert_file_data(**file_info)
                
                if not result["success"]:
                    await self._safe_delete_file(filepath)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Lỗi khi lưu thông tin file: {result.get('error', 'Unknown error')}"
                    )

                return result["file_info"]
                
            except Exception as db_error:
                await self._safe_delete_file(filepath)
                logger.error(f"Lỗi database khi lưu file: {db_error}", exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Lỗi khi lưu thông tin file vào database: {str(db_error)}"
                )
            
        except HTTPException as http_err:
            # Đã xử lý ở các tầng dưới, chỉ cần ném lên
            raise http_err
            
        except Exception as e:
            logger.error(f"Lỗi không xác định khi xử lý upload file: {e}", exc_info=True)
            if 'filepath' in locals():
                await self._safe_delete_file(filepath)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Đã xảy ra lỗi không xác định: {str(e)}"
            )

    async def create_file(self, db: AsyncSession, file_data: FileCreate, user_id: UUID) -> Optional[FilePublic]:
        """Tạo một tệp tin mới."""
        try:
            new_file_dict = file_data.model_dump(exclude_unset=True)
            if 'folder_id' in new_file_dict and new_file_dict['folder_id'] is not None:
                new_file_dict['folder_id'] = str(new_file_dict['folder_id'])
            
            new_file = File(
                id=str(uuid4()),
                **new_file_dict,
                uploaded_by_user_id=str(user_id)
            )
            db.add(new_file)
            await db.commit()
            await db.refresh(new_file)
            return FilePublic.model_validate(new_file)
        except IntegrityError as e:
            await db.rollback()
            logger.error(f"Lỗi khi tạo file: {e}")
            return None

    async def get_all_files(self, db: AsyncSession) -> List[FilePublic]:
        """Lấy tất cả các tệp tin."""
        result = await db.execute(select(File))
        files = result.scalars().all()
        return [FilePublic.model_validate(file) for file in files]

    async def get_file_by_id(self, db: AsyncSession, file_id: UUID) -> Optional[FilePublic]:
        """Lấy một tệp tin bằng ID."""
        file = await db.get(File, str(file_id))
        if file:
            return FilePublic.model_validate(file)
        return None

    async def update_file(self, db: AsyncSession, file_id: UUID, file_data: FileUpdate, 
                         user_id: UUID, is_admin: bool) -> Optional[FilePublic]:
        """Cập nhật một tệp tin (chỉ admin hoặc người tải lên)."""
        file = await db.get(File, str(file_id))
        if not file:
            return None
            
        # Kiểm tra quyền
        if not is_admin and str(file.uploaded_by_user_id) != str(user_id):
            return None
            
        # Cập nhật dữ liệu
        update_data = file_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(file, key, value)
            
        try:
            await db.commit()
            await db.refresh(file)
            return FilePublic.model_validate(file)
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Lỗi khi cập nhật file {file_id}: {e}")
            return None

    async def delete_file(self, db: AsyncSession, file_id: UUID, 
                         user_id: UUID, is_admin: bool) -> bool:
        """Xóa một tệp tin (chỉ admin hoặc người tải lên)."""
        file = await db.get(File, str(file_id))
        if not file:
            return False
            
        # Kiểm tra quyền
        if not is_admin and str(file.uploaded_by_user_id) != str(user_id):
            return False
            
        try:
            # Xóa file vật lý nếu tồn tại
            if file.storage_path and Path(file.storage_path).exists():
                self._safe_delete_file(Path(file.storage_path))
                
            # Xóa bản ghi trong database
            await db.delete(file)
            await db.commit()
            return True
            
        except SQLAlchemyError as e:
            await db.rollback()
            logger.error(f"Lỗi khi xóa file {file_id}: {e}")
            return False

    def _get_accessible_file_query_base(self, user_id: str):
        """Tạo Base Query/CTE/Subquery cho TẤT CẢ File mà user có quyền truy cập."""
        # Logic Files có quyền thông qua group (GroupAccessLevel)
        group_stmt = (
            select(File.id, File.folder_id)  # CHỈ LẤY ID VÀ FOLDER_ID
            .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
            .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
            .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
            .join(Group, Group.id == GroupAccessLevel.group_id)
            .join(UserGroup, UserGroup.group_id == Group.id)
            .where(UserGroup.user_id == user_id)
            .distinct(File.id)
        )
        
        # Logic Files do chính user tạo (Owner)
        owner_stmt = select(File.id, File.folder_id).where(File.uploaded_by_user_id == user_id)
        
        # Kết hợp 2 nguồn thành một Subquery (rất nhanh)
        return union(group_stmt, owner_stmt).subquery('accessible_files_base')

    async def list_folder_content(
        self,
        db: AsyncSession,
        folder_id: Optional[UUID],
        user_id: str,
        is_admin: bool
    ) -> FolderContentResponse:
        """Liệt kê nội dung thư mục (Đã tối ưu hóa cấp độ 2)."""
        from sqlalchemy import or_, and_
        
        folder_id_str = str(folder_id) if folder_id else None
        
        # 1. Định nghĩa điều kiện cho thư mục cha và file trong thư mục hiện tại
        folder_parent_condition = Folder.parent_id == folder_id_str if folder_id else Folder.parent_id.is_(None)
        file_folder_condition = File.folder_id == folder_id_str if folder_id else File.folder_id.is_(None)

        if is_admin:
            # ADMIN PATH: Query tất cả trong folder hiện tại
            folders_query = select(Folder).where(folder_parent_condition)
            files_query = select(File).where(file_folder_condition)
        else:
            # USER PATH: Tối ưu hóa bằng cách chuyển logic quyền truy cập vào SQL
            
            # --- BƯỚC 1: Xây dựng Subquery cho TẤT CẢ file có quyền truy cập ---
            # Chỉ lấy File.id và File.folder_id, KHÔNG tải full File object vào Python
            accessible_files_subquery = self._get_accessible_file_query_base(user_id)
            AccessibleFile = accessible_files_subquery.c

            # --- BƯỚC 2: Tối ưu hóa Truy vấn File (files_query) ---
            # Lấy các file trong folder hiện tại CÓ ID nằm trong accessible_files_subquery
            files_query = (
                select(File)
                .where(
                    and_(
                        file_folder_condition,
                        File.id.in_(select(AccessibleFile.id)) # Dùng IN với Subquery
                    )
                )
            )

            # --- BƯỚC 3: Tối ưu hóa Truy vấn Folder (folders_query) ---
            # Lấy các folder con (D) thỏa mãn 1 trong 3 điều kiện sau:
            folders_query = (
                select(Folder)
                .where(
                    and_(
                        folder_parent_condition,
                        or_(
                            # Điều kiện 1: Folder do user tạo
                            Folder.created_by_user_id == user_id,
                            
                            # Điều kiện 2: Folder chứa bất kỳ file nào user có quyền truy cập
                            # Sử dụng EXISTS/IN để check sự tồn tại của accessible file trong folder
                            exists().where(and_(
                                AccessibleFile.folder_id == Folder.id,
                                AccessibleFile.folder_id.is_not(None)
                            )),
                            
                            # Điều kiện 3: Folder là thư mục cha của file có quyền
                            # Sử dụng LIKE để kiểm tra folder_path
                            exists().where(and_(
                                File.folder_path.is_not(None),
                                File.folder_path.like(f'%/{Folder.id}/%'),
                                File.id.in_(select(AccessibleFile.id))
                            ))
                        )
                    )
                )
            )
        
        # 4. Thực thi truy vấn
        # Chỉ 2 truy vấn chính, không tải toàn bộ file có quyền vào bộ nhớ
        folders_result = await db.execute(folders_query)
        files_result = await db.execute(files_query)
        
        folders = folders_result.scalars().all()
        files = files_result.scalars().all()

        return FolderContentResponse(
            folders=[FolderPublic.model_validate(f) for f in folders],
            files=[FilePublic.model_validate(f) for f in files],
        )

    async def get_accessible_files(self, db: AsyncSession, user_id: UUID, is_admin: bool) -> List[FilePublic]:
        """Lấy tất cả các tệp tin mà người dùng có quyền truy cập."""
        if is_admin:
            files_q = select(File)
        else:
            files_q = select(File).where(File.uploaded_by_user_id == str(user_id))
            
        files_result = await db.execute(files_q)
        files = files_result.scalars().all()
        
        return [FilePublic.model_validate(f) for f in files]

    async def get_accessible_filesV3(self, db: AsyncSession, user_id: str, is_admin: bool):
        """Lấy danh sách file có thể truy cập thông qua group hoặc sở hữu."""
        if is_admin:
            result = await db.execute(select(File))
            return result.scalars().all()

        # --- Query group accessible IDs ---
        group_stmt = (
            select(File.id)
            .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
            .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
            .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
            .join(Group, Group.id == GroupAccessLevel.group_id)
            .join(UserGroup, UserGroup.group_id == Group.id)
            .where(UserGroup.user_id == user_id)
        )

        # --- Query owner IDs ---
        owner_stmt = select(File.id).where(File.uploaded_by_user_id == user_id)

        # --- UNION để gộp ID ---
        union_ids = union(group_stmt, owner_stmt).subquery()

        # --- Join lại với bảng File để ORM mapping ---
        stmt = select(File).join(union_ids, union_ids.c.id == File.id).distinct()

        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_accessible_filesV2(
        self,
        db: AsyncSession,
        user_id: str,
        is_admin: bool,
        page: int = 1,
        page_size: int = 4,
    ):
        """Lấy danh sách file có thể truy cập với phân trang."""
        if is_admin:
            base_query = select(File)
            count_query = select(func.count()).select_from(File)
        else:
            group_stmt = (
                select(File.id)
                .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
                .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
                .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
                .join(Group, Group.id == GroupAccessLevel.group_id)
                .join(UserGroup, UserGroup.group_id == Group.id)
                .where(UserGroup.user_id == user_id)
            )
            owner_stmt = select(File.id).where(File.uploaded_by_user_id == user_id)
            file_ids_union = union(group_stmt, owner_stmt).subquery()

            base_query = select(File).where(File.id.in_(select(file_ids_union.c.id)))
            count_query = select(func.count()).select_from(file_ids_union)

        # Tổng số record
        total = await db.scalar(count_query)

        # Query phân trang
        stmt = (
            base_query
            .order_by(File.upload_timestamp.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        result = await db.execute(stmt)
        rows = result.scalars().all()

        return {
            "page": page,
            "page_size": page_size,
            "total": total or 0,
            "items": rows,
        }

    async def refresh_access_files(self, db: AsyncSession, user_id: str, is_admin: bool):
        """
        Cập nhật quyền truy cập file cho user.
        Không trả về gì, chỉ thực hiện update thông tin quyền.
        """
        if is_admin:
            result = await db.execute(select(File))
            files = result.scalars().all()
        else:
            stmt = (
                select(File).distinct(File.id)
                .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
                .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
                .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
                .join(Group, Group.id == GroupAccessLevel.group_id)
                .join(UserGroup, UserGroup.group_id == Group.id)
                .where(UserGroup.user_id == user_id)
            )
            result = await db.execute(stmt)
            files = result.scalars().all()

        # Gọi UserAccessLevelService để cập nhật quyền
        user_access_service = UserAccessLevelService()
        await user_access_service.refresh_user_access_files(db, user_id=user_id, is_admin=is_admin, files=files)

    async def search_files(
        self,
        db: AsyncSession,
        user_id: str,
        is_admin: bool,
        name_query: Optional[str] = None,
        file_extension: Optional[str] = None,
        upload_from: Optional[datetime] = None,
        upload_to: Optional[datetime] = None,
        modified_from: Optional[datetime] = None,
        modified_to: Optional[datetime] = None,
        uploader_only: bool = False,
        accessible_only: bool = True,
        content_query: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ):
        # --- Xử lý upload_to để lấy hết ngày nếu chỉ chọn ngày ---
        def normalize_datetime(dt: Optional[datetime], end_of_day=False) -> Optional[datetime]:
            if not dt:
                return None
            if end_of_day and dt.hour == dt.minute == dt.second == dt.microsecond == 0:
                dt = dt + timedelta(days=1) - timedelta(microseconds=1)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            return dt
        
        upload_from_utc = normalize_datetime(upload_from, end_of_day=False)
        upload_to_utc   = normalize_datetime(upload_to,   end_of_day=True)
        modified_from_utc = normalize_datetime(modified_from, end_of_day=False)
        modified_to_utc   = normalize_datetime(modified_to,   end_of_day=True)
        
        # Build base query với filters
        filters = []
        
        # Text search filters
        if name_query:
            filters.append(File.original_file_name.ilike(f"%{name_query}%"))
        if file_extension:
            filters.append(File.file_extension == file_extension)
        if content_query:
            filters.append(File.extracted_text.ilike(f"%{content_query}%"))
        # Timestamp filters
        if upload_from_utc:
            filters.append(File.upload_timestamp >= upload_from_utc)
        if upload_to_utc:
            filters.append(File.upload_timestamp <= upload_to_utc)
        
        if modified_from_utc:
            filters.append(File.last_modified_timestamp >= modified_from_utc)
        if modified_to_utc:
            filters.append(File.last_modified_timestamp <= modified_to_utc)
        
        # Permission filters - TỐI ƯU: sử dụng subquery thay vì load data
        if uploader_only:
            # Chỉ file do user upload
            filters.append(File.uploaded_by_user_id == user_id)
        if not is_admin:
            if accessible_only:
                # Files accessible qua group permissions
                group_files_subquery = (
                    select(File.id)
                    .join(FileAccessLevel, FileAccessLevel.file_id == File.id)
                    .join(AccessLevel, AccessLevel.id == FileAccessLevel.access_level_id)
                    .join(GroupAccessLevel, GroupAccessLevel.access_level_id == AccessLevel.id)
                    .join(Group, Group.id == GroupAccessLevel.group_id)
                    .join(UserGroup, UserGroup.group_id == Group.id)
                    .where(UserGroup.user_id == user_id)
                )
                
                # Files uploaded by user
                owner_files_subquery = select(File.id).where(File.uploaded_by_user_id == user_id)
                
                # Union cả hai
                accessible_files_subquery = union(group_files_subquery, owner_files_subquery)
                
                filters.append(File.id.in_(accessible_files_subquery))
        # Build final query
        base_query = select(File)
        if filters:
            base_query = base_query.where(and_(*filters))
        
        # Count query
        count_query = select(func.count()).select_from(base_query.subquery())
        
        # Data query với pagination
        data_query = (
            base_query
            .order_by(File.upload_timestamp.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        
        # Execute cả 2 queries song song (tối ưu performance)
        total_task = db.scalar(count_query)
        files_task = db.execute(data_query)
        
        total, result = await asyncio.gather(total_task, files_task)
        files = result.scalars().all()
        
        return {
            "page": page,
            "page_size": page_size,
            "total": total or 0,
            "items": files
        }
