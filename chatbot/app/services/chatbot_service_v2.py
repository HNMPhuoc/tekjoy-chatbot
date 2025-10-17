import uuid
from datetime import datetime
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from langchain_openai import ChatOpenAI
import os

from app.schemas.chatbot_schema import ChatRequest


# ---- DB HELPERS ----
async def get_or_create_user_settings(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """Lấy hoặc tạo chat_setting mặc định theo user_id"""
    q = text("SELECT * FROM chat_settings WHERE user_id = :uid LIMIT 1")
    result = await db.execute(q, {"uid": user_id})
    settings = result.mappings().first()

    if settings:
        return settings

    default = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,     # ✅ scope theo user_id
        "model": "gpt-3.5-turbo",
        "system_prompt": """""
        Bạn là **Chuyên gia Phân tích Dữ liệu & Hợp đồng Cấp cao (Senior Data & Contract Analyst)** của công ty Tekjoy. Vai trò của bạn là trả lời các yêu cầu phân tích một cách chuyên nghiệp, khách quan, và dựa trên sự thật (fact-based).

### I. ƯU TIÊN TUYỆT ĐỐI: BỐI CẢNH DỮ LIỆU & LƯỢC ĐỒ HOẠT ĐỘNG
1.  **CƠ SỞ DỮ LIỆU (LUẬT CỨNG):** **BẮT BUỘC** kiểm tra khu vực **{context_text} TRƯỚC HẾT**. Mọi câu trả lời và phân tích **CHỈ ĐƯỢC DỰA TRÊN** dữ liệu HIỆN CÓ trong khu vực này.
2.  **QUY TẮC BỎ QUA LỊCH SỬ:** Nếu **{context_text} có dữ liệu**, bạn **PHẢI HOÀN TOÀN BỎ QUA** bất kỳ lịch sử trò chuyện nào (trong {history\_text}) liên quan đến việc yêu cầu người dùng cung cấp tài liệu, và tiến hành phân tích ngay.

---

### II. Nhiệm vụ & Xử lý Yêu cầu (CORE TASKS)
1.  **Độ dài:** Trả lời trực tiếp, chính xác, và **đầy đủ** (độ dài câu trả lời vừa đủ để truyền tải thông tin cần thiết, không quá ngắn cũng không lan man, **tương đương với mức độ chi tiết** của yêu cầu).
2.  **Phân tích Mặc định (Khi Yêu cầu Chung chung):** * **Nếu yêu cầu quá chung chung** (ví dụ: "phân tích", "xem xét tài liệu", "cho tôi biết về file"), bạn **BẮT BUỘC** phải thực hiện **Phân tích Tổng quan** theo các bước sau:
    * **Bước 1:** Tóm tắt ngắn gọn mục đích của tài liệu (nếu có thể xác định).
    * **Bước 2:** Trích xuất các **Chỉ số Quan trọng (Key Metrics)** hoặc **Kết quả Chính** từ dữ liệu có cấu trúc.
    * **Bước 3:** Sử dụng **bảng Markdown** để trình bày các chỉ số này.
3.  **Thiếu Dữ liệu:**
    * **Tham số Suy luận:** Ưu tiên dùng **dữ liệu thực tế** > suy luận chuyên môn.
    * Nếu dữ liệu không đủ: Nêu rõ **“Nhận định (suy luận):”** trước mỗi kết luận suy luận.
    * Luôn ghi rõ **Giả định** nếu phải giả định dữ liệu thiếu để tiếp tục phân tích.

---

### III. Quản lý Bối cảnh & Xử lý Xung đột Dữ liệu
1.  **Dữ liệu Duy nhất:** Dữ liệu trong **{context\_text}** được coi là phiên bản **mới nhất và duy nhất**. **Ngay lập tức quên mọi dữ liệu** từ các lần tương tác trước không còn xuất hiện trong `{context\_text}` hiện tại.
2.  **Xử lý Xung đột Yêu cầu/Dữ liệu:**
    * **Nếu {payload.message} yêu cầu phân tích dữ liệu cũ** đã bị thay thế/xoá khỏi `{context\_text}`, bạn phải trả lời rõ ràng: **"Yêu cầu không thể hoàn thành vì dữ liệu/tệp '[TÊN DỮ LIỆU/TỆP CŨ NẾU CÓ THỂ XÁC ĐỊNH]' không còn nằm trong khu vực dữ liệu hiện tại."**
    * **Tuyệt đối không** cố gắng suy luận hay tìm kiếm thông tin về tài liệu không có trong `{context\_text}` hiện tại.

---

### IV. Luật Ứng xử & Định dạng Bắt buộc
1.  **Ngôn ngữ & Phong cách:** Trả lời **Tiếng Việt**. Phong cách: **chuyên nghiệp, khách quan, súc tích**.
2.  **Giao tiếp:** **Không chào, không kết thúc, không dùng từ ngữ xã giao**.
3.  **Định dạng Số liệu (Chuẩn VN):**
    * Mọi giá trị tiền tệ, doanh số, chi phí phải được trả lời với đơn vị **VNĐ**.
    * **Con số và giá trị** phải luôn sử dụng dấu **chấm (.)** cho hàng nghìn và dấu **phẩy (,)** cho phần thập phân (Ví dụ: **10.000.000,00 VNĐ** hoặc **123.456**).
4.  **Định dạng Trình bày:**
    * Khi so sánh/tổng hợp → **bắt buộc dùng bảng Markdown**.
    * Khi liệt kê → dùng **danh sách có cấu trúc**.
    * Làm nổi bật **thông tin quan trọng** bằng **in đậm**.

""""",
        "max_tokens": 50000,
        "context_files": [],
        "domain": None,
        "is_history": True,
        "max_context_messages": 0,
        "using_document": True,
        "free_chat": False,
        "show_sources": True,
        "enable_streaming": True,
        "response_style": "concise",
        "language": "Vietnamese",
        "api_key": None,   # 👈 thêm dòng này
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

    cols = ",".join(default.keys())
    vals = ",".join([f":{k}" for k in default.keys()])
    await db.execute(text(f"INSERT INTO chat_settings ({cols}) VALUES ({vals})"), default)
    await db.commit()
    return default


# async def get_file_extracts(db: AsyncSession, file_ids: List[str]) -> List[str]:
#     if not file_ids:
#         return []
#     q = text("SELECT extracted_text FROM files WHERE id = ANY(:ids)")
#     result = await db.execute(q, {"ids": file_ids})
#     rows = result.fetchall()
#     return [row[0] for row in rows if row[0]]
async def get_file_extracts(
    db: AsyncSession,
    file_ids: List[str]
) -> List[str]:
    """
    Trả về danh sách chuỗi đã ghép: "original_file_name\nextracted_text"
    """
    if not file_ids:
        return []

    q = text("""
        SELECT original_file_name, extracted_text
        FROM files
        WHERE id = ANY(:ids)
    """)
    result = await db.execute(q, {"ids": file_ids})
    rows = result.fetchall()

    # Nối tên file và nội dung, bỏ qua hàng không có extracted_text
    return [
        f"{row[0]}\n{row[1]}"
        for row in rows
        if row[1]  # chỉ lấy khi có extracted_text
    ]


async def get_chat_history(db: AsyncSession, session_id: str, limit: int) -> List[str]:
    q = text("""
        SELECT sender_type, message_text
        FROM chat_messages
        WHERE session_id = :sid
        ORDER BY created_at DESC
        LIMIT :limit
    """)
    result = await db.execute(q, {"sid": session_id, "limit": limit})
    rows = result.fetchall()
    return [f"{r[0]}: {r[1]}" for r in reversed(rows)]


async def get_or_create_session(db: AsyncSession, session_id: str, user_id: str) -> str:
    q = text("SELECT id FROM chat_sessions WHERE id = :sid")
    result = await db.execute(q, {"sid": session_id})
    row = result.fetchone()
    if row:
        return row[0]

    await db.execute(text("""
        INSERT INTO chat_sessions (id, user_id, title)
        VALUES (:sid, :uid, :title)
    """), {"sid": session_id, "uid": user_id, "title": "New Session"})
    await db.commit()
    return session_id


# ---- MAIN CHAT SERVICE V2 ----
async def handle_chat_v2(payload: ChatRequest, db: AsyncSession) -> Dict[str, Any]:
    # 1. Lấy hoặc tạo session (giữ nguyên để quản lý lịch sử)
    session_id = await get_or_create_session(db, payload.session_id, payload.user_id)

    # 2. Lấy hoặc tạo chatsetting theo user_id (không còn theo session_id)
    settings = await get_or_create_user_settings(db, payload.user_id)

    # 3. Xử lý docs
    context_text = ""
    if settings["using_document"]:
        file_ids = [f.file_id for f in payload.files]
        extracts = await get_file_extracts(db, file_ids)
        context_text = "\n\n".join(extracts)
        # context_text = "\n\n".join(text for text, _ in extracts)
        # # hoặc bạn cũng có thể dùng original_file_name tùy nhu cầu
        # file_names = [name for _, name in extracts]

    # 4. Xử lý lịch sử (theo session_id như cũ)
    history_text = ""
    if settings["is_history"]:
        limit = settings["max_context_messages"] or 15
        history = await get_chat_history(db, session_id, limit)
        history_text = "\n".join(history)

    # 5. Build final prompt
    final_prompt = f"""
{settings['system_prompt']}

{context_text}


### Lịch sử trò chuyện:
{history_text}

### Tin nhắn mới:
{payload.message} 
"""


    # 6. Call LLM (dùng model từ user chatsettings, không lấy env key cứng nữa)
    llm = ChatOpenAI(model=settings["model"], temperature=0, api_key=settings.get("api_key") or os.getenv("OPENAI_API_KEY"),streaming=True)
    print("prompt", final_prompt)
    print("api key", settings.get("api_key"))


    # 7. Log user message
    user_msg_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO chat_messages (id, session_id, sender_type, sender_id, message_text)
        VALUES (:id, :sid, 'user', :uid, :msg)
    """), {
        "id": user_msg_id,
        "sid": session_id,
        "uid": payload.user_id,
        "msg": payload.message
    })
    await db.commit()

    # 8. Gọi model
    response = await llm.ainvoke(final_prompt)

    # 9. Log assistant message
    bot_msg_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO chat_messages (id, session_id, sender_type, message_text)
        VALUES (:id, :sid, 'assistant', :msg)
    """), {
        "id": bot_msg_id,
        "sid": session_id,
        "msg": response.content
    })
    await db.commit()
    return {
        "message": response.content,
        "used_files": payload.files if settings["show_sources"] else []
    }

async def get_chat_history_list(db: AsyncSession, user_id: str):
    """
    Lấy danh sách các session trò chuyện của một người dùng, 
    mỗi session chỉ hiển thị tin nhắn đầu tiên.
    """
    # Truy vấn các session của user, sắp xếp theo thời gian hoạt động gần nhất
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(desc(ChatSession.last_activity_at))
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()

    response_list = []
    for session in sessions:
        # Tìm tin nhắn đầu tiên của mỗi session
        message_stmt = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at)
            .limit(1)
        )
        message_result = await db.execute(message_stmt)
        first_message = message_result.scalars().first()

        # Chỉ thêm session nếu có tin nhắn
        if first_message:
            response_list.append({
                "session_id": str(session.id),
                "title": session.title,
                "first_message": first_message.message_text,
                "last_activity_at": session.last_activity_at.isoformat() if session.last_activity_at else None,
                "created_at": session.created_at.isoformat()
            })
    
    return response_list