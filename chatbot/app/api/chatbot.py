from fastapi import APIRouter, Depends, HTTPException, status # <-- THÊM status
from pydantic import BaseModel
from typing import List, Tuple, Any, Union # <-- THÊM Tuple, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.services.chatbot_service import handle_chat
from app.schemas.chatbot_schema import ChatRequest  
from app.services.chatbot_service_v2 import handle_chat_v2,get_chat_history_list
from app.services.chat_service_new import list_user_sessions, get_session_history, edit_session_title # Import new services
from uuid import UUID

from app.core.db_retry import retry_on_deadlock # <-- THÊM IMPORT QUAN TRỌNG NÀY

router = APIRouter()

# Hàm helper để tạo thông báo tích cực (nên đặt ở đầu file)
def create_positive_message(base_message: str, attempts: int) -> str:
    """Tạo thông báo thân thiện cho người dùng nếu thao tác thành công sau khi thử lại Deadlock."""
    if attempts > 1:
        return f"{base_message} sau {attempts} lần thử (Đã tự động xử lý tắc nghẽn hệ thống)."
    return base_message

# ---- tạo class để nhận request
class EditSessionTitleRequest(BaseModel):
    new_title: str

@router.post("/chat")
async def chat_completion(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    return await handle_chat(payload, db)

@router.post("/chatV2")
async def chat_completion_v2(payload: ChatRequest, db: AsyncSession = Depends(get_db)):
    return await handle_chat_v2(payload, db)

@router.get("/sessions/{user_id}", response_model=List[dict])
async def list_user_sessions_api(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    List all chat sessions for a specific user, sorted by last activity.
    Returns an empty list if no sessions are found.
    """
    sessions = await list_user_sessions(db, str(user_id))
    if not sessions:
        raise HTTPException(status_code=404, detail="No sessions found for this user.")
    return sessions

# phiên bản dùng yêu cầu parameter trên body - ĐÃ CẬP NHẬT TÍCH HỢP RETRY
@router.put("/sessions/{session_id}/edit-title")
async def edit_session_title_api(
    session_id: UUID,
    request: EditSessionTitleRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Edit the title of a specific chat session. (Bao gồm cơ chế tự động thử lại Deadlock)
    """
    try:
        # BỌC LỜI GỌI SERVICE BẰNG RETRY_ON_DEADLOCK
        # retry_on_deadlock sẽ gọi edit_session_title, truyền các tham số db, session_id, new_title dưới dạng kwargs
        result: Tuple[Union[dict, None], int] = await retry_on_deadlock(
            edit_session_title, db=db, session_id=str(session_id), new_title=request.new_title
        )
        updated_session, attempts = result
        
        if not updated_session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
            
        # Tạo thông báo bao gồm số lần thử nếu có
        message = create_positive_message("Session title updated successfully", attempts)
            
        return {"message": message, "session": updated_session}
        
    except HTTPException:
        # Lỗi HTTP (404/503) được ném từ bên trong retry_on_deadlock hoặc từ logic 404
        raise
    except Exception as e:
        # Xử lý lỗi hệ thống chung
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi hệ thống khi cập nhật tiêu đề session: {str(e)}")


@router.get("/history/{session_id}")
async def get_session_history_api(session_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Get the full chat message history for a specific session.
    """
    messages = await get_session_history(db, str(session_id))
    return {"session_id": session_id, "messages": messages}