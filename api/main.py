from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

from api.routes import essay, check

app = FastAPI(title="Academic Essay Agent", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(essay.router, prefix="/essay", tags=["Essay"])
app.include_router(check.router, prefix="/check", tags=["Originality"])

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(frontend_path):
        with open(frontend_path, "r") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Academic Essay Agent</h1><p><a href='/docs'>API Docs</a></p>")

@app.get("/health")
def health():
    return {"status": "running", "version": "1.0"}
