from fastapi import FastAPI, Request
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from starlette.responses import RedirectResponse

app = FastAPI()

# Mount static files
app.mount("/chatbot", StaticFiles(directory="ui/ChatBot", html=True), name="chatbot")
app.mount("/tekjoy", StaticFiles(directory="ui/Tekjoy-UI", html=True), name="tekjoy")

# Middleware để set cache-control cho HTML
@app.middleware("http")
async def no_cache_html(request: Request, call_next):
    response: Response = await call_next(request)
    if request.url.path.endswith(".html") or response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Redirects
@app.get("/tekjoy/")
def tekjoy_slash():
    return RedirectResponse(url="/tekjoy")

@app.get("/chatbot/")
def chatbot_slash():
    return RedirectResponse(url="/chatbot")
