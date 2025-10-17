# app/core/db_retry.py (Đã sửa đổi để trả về số lần thử)

import asyncio
from typing import Callable, Any, Awaitable, Tuple, Union
from fastapi import HTTPException, status
from sqlalchemy.exc import DBAPIError, OperationalError

# 1. Bắt lỗi driver cụ thể (asyncpg - driver cho PostgreSQL)
try:
    import asyncpg.exceptions
    DEADLOCK_ERRORS = (asyncpg.exceptions.DeadlockDetectedError,)
except ImportError:
    DEADLOCK_ERRORS = tuple()
    
# 2. Bắt lỗi SQLAlchemy tổng quát (fallback)
# from sqlalchemy.exc import DBAPIError, OperationalError # Đã import

# Cấu hình thử lại
MAX_RETRIES = 5
DELAY_SECONDS = 0.1 # Thời gian chờ ban đầu

# Lưu ý: Hàm này hiện trả về Tuple[Any, int]
async def retry_on_deadlock(func: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Union[Any, Tuple[Any, int]]:
    """
    Thực hiện gọi hàm (thường là hàm service) và tự động thử lại nếu phát hiện Deadlock.
    
    Tối ưu cho SQLAlchemy/asyncpg: Bắt lỗi DeadlockDetectedError (asyncpg) và mã SQLSTATE '40P01'.
    
    Trả về: (Kết quả của hàm service, Số lần thử thành công)
    """
    is_deadlock = False
    error_type = ""
    for attempt in range(MAX_RETRIES):
        try:
            # 1. Gọi hàm service gốc
            result = await func(*args, **kwargs)
            # THÀNH CÔNG: Trả về kết quả và số lần thử
            return result, attempt + 1
        
        # Bắt lỗi Deadlock từ driver asyncpg (nếu có)
        except DEADLOCK_ERRORS:
            is_deadlock = True
            error_type = "asyncpg.DeadlockDetectedError"
        
        # Bắt lỗi DBAPIError/OperationalError từ SQLAlchemy và kiểm tra mã SQLSTATE
        except (DBAPIError, OperationalError) as e:
            sqlstate = getattr(e.orig, 'sqlstate', None)
            is_deadlock = sqlstate == '40P01' # Mã SQLSTATE cho Deadlock Detected
            error_type = f"DBAPIError (SQLSTATE: {sqlstate})"
            if not is_deadlock:
                raise # Ném lỗi không phải deadlock lên
        
        except HTTPException:
            # Bắt lỗi FastAPI/HTTP được ném từ bên trong hàm service
            raise 
        
        except Exception as e:
            # Bất kỳ lỗi không phải DB/HTTP nào khác
            print(f"An unexpected error occurred: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Lỗi không xác định: {str(e)}"
            )

        # Xử lý khi lỗi được xác định là Deadlock
        if is_deadlock:
            if attempt < MAX_RETRIES - 1:
                # 3. Deadlock xảy ra, thử lại
                wait_time = DELAY_SECONDS * (2 ** attempt) # Exponential Backoff
                print(f"Deadlock detected ({error_type}) on {func.__name__}. Retrying in {wait_time:.2f}s... (Attempt {attempt + 1}/{MAX_RETRIES})")
                await asyncio.sleep(wait_time) 
                continue
            else:
                # 4. Hết lượt thử lại
                print(f"Deadlock detected on {func.__name__}. Failed after max retries.")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Hệ thống quá tải do giao dịch bị tắc nghẽn. Vui lòng thử lại sau giây lát."
                )