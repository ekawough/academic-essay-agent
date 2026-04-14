from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import os

from api.routes import essay, check
from api.routes import stream

app = FastAPI(title="Writer", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(essay.router, prefix="/essay", tags=["Essay"])
app.include_router(check.router, prefix="/check", tags=["Check"])
app.include_router(stream.router, prefix="/stream", tags=["Stream"])

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve():
    path = os.path.join(os.path.dirname(__file__), "..", "frontend", "index.html")
    if os.path.exists(path):
        with open(path) as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Writer API</h1><a href='/docs'>Docs</a>")

@app.get("/health")
def health():
    return {"status": "ok", "version": "2.0"}
