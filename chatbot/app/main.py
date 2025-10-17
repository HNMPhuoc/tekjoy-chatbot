from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI
from app.api import chatbot, chat_setting, user_router, group_router, access_level_router, folder_file_router, autocomplete_router
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import sys
import logging

# On Windows, the default encoding for stdout can be a problem.
# We'll reconfigure it to use UTF-8 to prevent UnicodeEncodeError in logs.
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except TypeError:
        # This can happen in environments where stdout is not a standard stream
        # (e.g., in some IDEs or notebooks). We'll proceed without it.
        pass

# Set up a basic logging configuration that will be used across the application.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout  # Log to standard output
)


app = FastAPI(
    title="RAG Chatbot API",
    version="1.0.0"
)

# Bật full CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả origin
    allow_credentials=True,
    allow_methods=["*"],  # Cho phép tất cả method (GET, POST, PUT, DELETE, ...)
    allow_headers=["*"],  # Cho phép tất cả header
)
# --- Mount thư mục UI ---

# Serve toàn bộ thư mục UI như static files
app.mount("/ui", StaticFiles(directory="app/ui"), name="ui")



app.include_router(chatbot.router, prefix="/api/chatbot", tags=["chatbot"])
app.include_router(chat_setting.router, prefix="/api/chat-settings", tags=["chat-settings"])
app.include_router(user_router.router, prefix="/api/users", tags=["users"])
app.include_router(group_router.router, prefix="/api/groups", tags=["groups"])
app.include_router(access_level_router.router, prefix="/api/access_levels", tags=["access_levels"])
app.include_router(folder_file_router.router, prefix="/api/file", tags=["folder_file"])
app.include_router(autocomplete_router.router, prefix="/api/autoc", tags=["folder_file"])


# @app.get("/")
# async def root():
#         return FileResponse("ui/indexV3.html")

        
if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",   # <== đường dẫn module tới biến app
        host="0.0.0.0",
        port=8001,
        reload=False
    )
