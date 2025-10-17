# app/api/folder_file_router.py
from fastapi import APIRouter, Depends, HTTPException, Form, status, Query, File as FastAPIFile, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Union, Tuple, Any, Dict # <-- Thêm Tuple, Any, Dict
from uuid import UUID
from app.db.database import get_db
from app.services.folder_file_service import DocumentService
from app.services.ocr_service import ocr_service, UploadCancelledError
from app.services.postgres_service import postgres_service
from app.db.models import Folder, File, User, UserGroup, GroupAccessLevel, FileAccessLevel, AccessLevel
from datetime import datetime

from app.schemas.folder_file_schema import (
    FolderCreate,
    FolderUpdate,
    FolderPublic,
    FileCreate,
    FileUpdate,
    FilePublic,
    FolderContentResponse,
    PaginatedFiles
)
from app.schemas.user_schema import UserPublic # Giả sử UserPublic có id và role
from app.api.deps import get_current_active_user, get_current_active_admin
from app.core.db_retry import retry_on_deadlock # <-- THÊM IMPORT NÀY


router = APIRouter(tags=["Folders & Files"])
document_service = DocumentService()
document_service = DocumentService()

# Hàm helper để tạo thông báo tích cực (dùng chung cho các router)
def create_positive_message(base_message: str, attempts: int) -> str:
    """Tạo thông báo thân thiện cho người dùng nếu thao tác thành công sau khi thử lại Deadlock."""
    if attempts > 1:
        return f"{base_message} sau {attempts} lần thử (Đã tự động xử lý tắc nghẽn hệ thống)."
    return base_message


# --- FOLDERS ENDPOINTS ---
@router.post("/folders", response_model=FolderPublic, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder_data: FolderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Tạo một thư mục mới. (Được bọc Deadlock Retry)"""
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        result: Tuple[Union[FolderPublic, None], int] = await retry_on_deadlock(
            document_service.create_folder, db=db, folder_data=folder_data, user_id=current_user.id
        )
        folder, attempts = result
        
        if not folder:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên thư mục đã tồn tại hoặc lỗi khác."
            )
            
        if attempts > 1:
            print(create_positive_message(f"Tạo thư mục '{folder.name}' thành công.", attempts))

        return folder
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi tạo thư mục: {str(e)}")


@router.get("/folders", response_model=List[FolderPublic])
async def get_all_folders(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Lấy tất cả các thư mục."""
    return await document_service.get_all_folders(db)

@router.put("/folders/{folder_id}", response_model=FolderPublic)
async def update_folder(
    folder_id: UUID,
    folder_data: FolderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Cập nhật một thư mục (chỉ người tạo hoặc admin). (Được bọc Deadlock Retry)"""
    # Lấy thông tin thư mục để kiểm tra quyền (Phải thực hiện ngoài khối retry)
    existing_folder = await document_service.get_folder_by_id(db, folder_id)
    if not existing_folder:
        raise HTTPException(status_code=404, detail="Thư mục không tồn tại.")

    is_admin = current_user.role == "admin"
    
    # Kiểm tra quyền
    from uuid import UUID
    try:
        user_uuid = UUID(str(current_user.id))
        folder_created_by_uuid = UUID(str(existing_folder.created_by_user_id))
        
        if not is_admin and folder_created_by_uuid != user_uuid:
            raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật thư mục này.")
            
    except Exception:
        if not is_admin and existing_folder.created_by_user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật thư mục này.")

    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        result: Tuple[Union[FolderPublic, None], int] = await retry_on_deadlock(
            document_service.update_folder, db=db, folder_id=folder_id, folder_data=folder_data, user_id=current_user.id, is_admin=is_admin
        )
        updated_folder, attempts = result
        
        if not updated_folder:
            raise HTTPException(status_code=400, detail="Cập nhật thất bại.")
        
        if attempts > 1:
            print(create_positive_message(f"Cập nhật thư mục '{updated_folder.name}' thành công.", attempts))

        return updated_folder
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi cập nhật thư mục: {str(e)}")

@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Xóa một thư mục (chỉ người tạo hoặc admin). (Được bọc Deadlock Retry)"""
    # Lấy thông tin thư mục để kiểm tra quyền (Phải thực hiện ngoài khối retry)
    existing_folder = await document_service.get_folder_by_id(db, folder_id)
    if not existing_folder:
        raise HTTPException(status_code=404, detail="Thư mục không tồn tại.")
        
    is_admin = current_user.role == "admin"
    
    # Kiểm tra quyền
    from uuid import UUID
    try:
        user_uuid = UUID(str(current_user.id))
        folder_created_by_uuid = UUID(str(existing_folder.created_by_user_id))
        
        if not is_admin and folder_created_by_uuid != user_uuid:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xóa thư mục này.")
            
    except Exception:
        if not is_admin and existing_folder.created_by_user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xóa thư mục này.")
        
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        result: Tuple[bool, int] = await retry_on_deadlock(
            document_service.delete_folder, db=db, folder_id=folder_id, user_id=current_user.id, is_admin=is_admin
        )
        success, attempts = result

        if not success:
            raise HTTPException(status_code=400, detail="Xóa thư mục thất bại.")
        
        if attempts > 1:
            print(create_positive_message(f"Xóa thư mục '{folder_id}' thành công.", attempts))
            
        return
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi xóa thư mục: {str(e)}")

@router.get("/folders/content", response_model=FolderContentResponse)
async def list_folder_content(
    folder_id: Optional[UUID] = Query(None, description="ID thư mục. Trống = root"),
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user) 
):
    """
    Liệt kê folder + file theo quyền:
    - Admin: xem tất cả (dùng get_current_active_admin)
    - User thường: chỉ xem được phần họ có quyền
    """
    is_admin = current_user.role == "admin"
    return await document_service.list_folder_content(
        db, folder_id, str(current_user.id), is_admin
    )



# --- FILES ENDPOINTS ---
@router.post("/files", response_model=FilePublic, status_code=status.HTTP_201_CREATED)
async def create_file(
    file: UploadFile = FastAPIFile(...) ,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user),
    folder_id: Optional[UUID] = Form(None),
    is_template: bool = Form(False),
    project_code: Optional[str] = Form(None),
    project_name: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    upload_id: Optional[str] = Form(None)
):
    """
    Tải lên một tệp tin vật lý và lưu thông tin của nó vào cơ sở dữ liệu.
    (Được bọc Deadlock Retry cho các thao tác ghi DB)
    """
    uploaded_file_info = None
    try:
        # Đăng ký upload nếu có upload_id
        if upload_id:
            document_service.register_upload(upload_id, {"status": "uploading"})

        # Bước 1: Lưu tệp tin vật lý và tạo record file trong DB
        # BỌC LỜI GỌI SERVICE 1 BẰNG RETRY_ON_DEADLOCK
        result1: Tuple[dict, int] = await retry_on_deadlock(
            document_service.save_upload_file,
            file=file,
            user_id=str(current_user.id),
            folder_id=str(folder_id) if folder_id else None,
            is_template=is_template,
            project_code=project_code,
            project_name=project_name,
            document_type=document_type
        )
        uploaded_file_info, attempts1 = result1
        
        # Cập nhật thông tin upload
        if upload_id:
            document_service.register_upload(upload_id, {
                "status": "processing",
                "storage_path": uploaded_file_info.get("storage_path"),
                "file_id": uploaded_file_info.get("id")
            })
        
        if uploaded_file_info.get("error"):
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lỗi khi lưu tệp tin: {uploaded_file_info['error']}"
            )
        
        if attempts1 > 1:
            print(create_positive_message(f"Tạo record file '{uploaded_file_info['original_file_name']}' thành công.", attempts1))


        # Bước 2: Thực hiện OCR trên file đã upload
        file_path = uploaded_file_info['storage_path']

        # --- START MODIFICATION: CHECK FOR CANCELLATION BEFORE OCR ---
        # Nếu có upload_id, kiểm tra xem nó có bị hủy trước khi bắt đầu OCR không
        if upload_id and not document_service.get_upload_info(upload_id):
            print(f"Upload {upload_id} was canceled before OCR processing. Aborting.")
            # File tạm đã được dọn dẹp bởi hàm cancel_upload, không cần làm gì thêm.
            # Trả về lỗi cho client biết rằng quá trình đã bị hủy
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload {upload_id} was canceled by the user."
            )
        # --- END MODIFICATION ---

        try:
            ocr_result = await run_in_threadpool(
                ocr_service.process_file,
                file_path=file_path,
                upload_id=upload_id,
                document_service=document_service
            )
        except UploadCancelledError:
            # Ghi log và ném lại lỗi HTTP để client biết
            print(f"Upload {upload_id} was canceled during OCR processing. Aborting.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Upload {upload_id} was canceled by the user."
            )

        # Lấy kết quả text đã trích xuất
        extracted_text = None
        char_count = None
        word_count = None
        if ocr_result and ocr_result.get('success', False):
            extracted_text = ocr_result.get('text', '')
            if extracted_text:
                char_count = len(extracted_text)
                word_count = len(extracted_text.split())

        # Cập nhật thông tin OCR cho file vừa lưu
        if extracted_text:
            update_data = {
                "extracted_text": extracted_text,
                "char_count": char_count,
                "word_count": word_count
            }
            # BỌC LỜI GỌI SERVICE 2 BẰNG RETRY_ON_DEADLOCK (Update record file)
            result2: Tuple[dict, int] = await retry_on_deadlock(
                 postgres_service.update_file_data, file_id=uploaded_file_info['id'], update_data=update_data
            )
            result, attempts2 = result2
            
            if not result["success"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"Lỗi khi cập nhật thông tin OCR: {result['error']}"
                )
            
            if attempts2 > 1:
                print(create_positive_message(f"Cập nhật OCR cho file '{uploaded_file_info['original_file_name']}' thành công.", attempts2))
            
            # Xóa file tạm sau khi đã trích xuất OCR thành công
            await document_service.cleanup_upload_file(file_path)
            
            # Xóa khỏi danh sách active uploads nếu có
            if upload_id:
                document_service.active_uploads.pop(upload_id, None)
                
            return FilePublic.model_validate(result["file"])
            
        # Return original file info if no OCR results
        # Xóa file tạm ngay cả khi không có kết quả OCR
        await document_service.cleanup_upload_file(file_path)
        return FilePublic.model_validate(uploaded_file_info)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi khi xử lý tải lên tệp: {str(e)}"
        ) 
    
@router.delete("/files/cancel-upload/{upload_id}")
async def cancel_upload(
    upload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Hủy quá trình upload file đang diễn ra
    """
    result = await document_service.cancel_upload(upload_id, db)
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )
    return {"success": result["success"], "message": result["message"]}

@router.get("/files", response_model=List[FilePublic])
async def get_all_files(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Lấy tất cả các tệp tin."""
    return await document_service.get_all_files(db)

@router.get("/files/{file_id}", response_model=FilePublic)
async def get_file_by_id(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Lấy một tệp tin bằng ID."""
    file = await document_service.get_file_by_id(db, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại.")
    return file

@router.put("/files/{file_id}", response_model=FilePublic)
async def update_file(
    file_id: UUID,
    file_data: FileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Cập nhật một tệp tin (chỉ người tải lên hoặc admin). (Được bọc Deadlock Retry)"""
    # Lấy thông tin tệp tin để kiểm tra quyền (Phải thực hiện ngoài khối retry)
    existing_file = await document_service.get_file_by_id(db, file_id)
    if not existing_file:
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại.")
    
    is_admin = current_user.role == "admin"
    
    # Kiểm tra quyền
    from uuid import UUID
    try:
        user_uuid = UUID(str(current_user.id))
        file_uploaded_by_uuid = UUID(str(existing_file.uploaded_by_user_id))
        
        if not is_admin and file_uploaded_by_uuid != user_uuid:
            raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật tệp tin này.")
            
    except Exception:
        if not is_admin and existing_file.uploaded_by_user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Bạn không có quyền cập nhật tệp tin này.")
        
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        result: Tuple[Union[FilePublic, None], int] = await retry_on_deadlock(
            document_service.update_file, db=db, file_id=file_id, file_data=file_data, user_id=current_user.id, is_admin=is_admin
        )
        updated_file, attempts = result
        
        if not updated_file:
            raise HTTPException(status_code=400, detail="Cập nhật tệp tin thất bại.")
        
        if attempts > 1:
            print(create_positive_message(f"Cập nhật tệp tin '{updated_file.original_file_name}' thành công.", attempts))
        
        return updated_file
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi cập nhật tệp tin: {str(e)}")

@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """Xóa một tệp tin (chỉ người tải lên hoặc admin). (Được bọc Deadlock Retry)"""
    # Lấy thông tin tệp tin để kiểm tra quyền (Phải thực hiện ngoài khối retry)
    existing_file = await document_service.get_file_by_id(db, file_id)
    if not existing_file:
        raise HTTPException(status_code=404, detail="Tệp tin không tồn tại.")

    is_admin = current_user.role == "admin"
    
    # Kiểm tra quyền
    from uuid import UUID
    try:
        user_uuid = UUID(str(current_user.id))
        file_uploaded_by_uuid = UUID(str(existing_file.uploaded_by_user_id))
        
        if not is_admin and file_uploaded_by_uuid != user_uuid:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xóa tệp tin này.")
            
    except Exception:
        if not is_admin and existing_file.uploaded_by_user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Bạn không có quyền xóa tệp tin này.")

    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        result: Tuple[bool, int] = await retry_on_deadlock(
            document_service.delete_file, db=db, file_id=file_id, user_id=current_user.id, is_admin=is_admin
        )
        success, attempts = result

        if not success:
            raise HTTPException(status_code=400, detail="Xóa tệp tin thất bại.")
        
        if attempts > 1:
            print(create_positive_message(f"Xóa tệp tin '{file_id}' thành công.", attempts))

        return
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi xóa tệp tin: {str(e)}")


@router.get("/files/accessible/", response_model=List[FilePublic], summary="Lấy danh sách các tệp tin người dùng có quyền truy cập.")
async def get_accessible_files_for_user(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    """
    Trả về danh sách các tệp tin mà người dùng hiện tại có quyền xem.
    Quyền truy cập được xác định dựa trên vai trò admin, quyền tải lên, và sự trùng khớp AccessLevel giữa group của người dùng và tệp tin.
    """
    is_admin = current_user.role == "admin"
    return await document_service.get_accessible_files(db, current_user.id, is_admin)


@router.get(
    "/files/accessibleV2/",
    response_model=PaginatedFiles,
    summary="Lấy danh sách file có quyền truy cập"
)
async def get_accessible_files_for_user_v2(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(4, ge=1, le=100),
):
    is_admin = current_user.role == "admin"
    return await document_service.get_accessible_filesV2(
        db, current_user.id, is_admin, page=page, page_size=page_size
    )


@router.post("/me/refresh-access", status_code=204)
async def refresh_my_access(
    db: AsyncSession = Depends(get_db),
    current_user: UserPublic = Depends(get_current_active_user)
):
    await document_service.refresh_access_files(db, str(current_user.id), is_admin=False)
    return


@router.get("/files/search/scr", response_model=PaginatedFiles, summary="Tìm kiếm file với filter")
async def search_files_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_active_user),
    name: Optional[str] = Query(None, description="Tên file tìm kiếm"),
    file_extension: Optional[str] = Query(None, description="Đuôi file"),
    upload_from: Optional[datetime] = Query(None, description="Upload từ ngày"),
    upload_to: Optional[datetime] = Query(None, description="Upload đến ngày"),
    modified_from: Optional[datetime] = Query(None, description="Modified từ ngày"),
    modified_to: Optional[datetime] = Query(None, description="Modified đến ngày"),
    uploader_only: bool = Query(False, description="Chỉ file do bạn upload"),
    content: Optional[str] = Query(None, description="Tìm trong nội dung extracted_text"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    is_admin = current_user.role == "admin"

    result = await document_service.search_files(
        db=db,
        user_id=current_user.id,
        is_admin=is_admin,
        name_query=name,
        file_extension=file_extension,
        upload_from=upload_from,
        upload_to=upload_to,
        modified_from=modified_from,
        modified_to=modified_to,
        uploader_only=uploader_only,
        content_query=content,
        page=page,
        page_size=page_size
    )

    # Convert File objects sang schema trả về
    items = [FilePublic.model_validate(f) for f in result["items"]]

    return {
        "page": result["page"],
        "page_size": result["page_size"],
        "total": result["total"],
        "items": items
    }