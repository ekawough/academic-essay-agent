from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import uuid, json

from api.agents.researcher import research_topic
from api.agents.ghostwriter import write_essay, export_essay_docx
from api.integrations.notion_client import push_to_notion

router = APIRouter()

# ---------- Storage helpers (Supabase + memory fallback) ----------

_mem_jobs = {}
_mem_essays = {}

def _db():
    try:
        from api.integrations.supabase_client import get_db
        return get_db()
    except Exception:
        return None

def save_job(job: dict):
    _mem_jobs[job["id"]] = job
    db = _db()
    if db:
        try:
            db.table("jobs").upsert(job).execute()
        except Exception as e:
            print(f"Supabase job save error: {e}")

def get_job(job_id: str) -> dict:
    db = _db()
    if db:
        try:
            r = db.table("jobs").select("*").eq("id", job_id).single().execute()
            if r.data:
                _mem_jobs[job_id] = r.data
                return r.data
        except Exception:
            pass
    return _mem_jobs.get(job_id)

def update_job(job_id: str, updates: dict):
    job = get_job(job_id) or {}
    job.update(updates)
    _mem_jobs[job_id] = job
    db = _db()
    if db:
        try:
            db.table("jobs").update(updates).eq("id", job_id).execute()
        except Exception as e:
            print(f"Supabase job update error: {e}")

def save_essay(essay_doc: dict):
    _mem_essays[essay_doc["id"]] = essay_doc
    db = _db()
    if db:
        try:
            row = {
                "id": essay_doc["id"],
                "job_id": essay_doc["job_id"],
                "title": essay_doc.get("title", ""),
                "content": essay_doc.get("content", ""),
                "citations": json.dumps(essay_doc.get("citations", [])),
                "word_count": essay_doc.get("word_count", 0),
                "paper_type": essay_doc.get("paper_type", ""),
                "model_used": essay_doc.get("model_used", ""),
            }
            db.table("essays").upsert(row).execute()
        except Exception as e:
            print(f"Supabase essay save error: {e}")

def get_essay(essay_id: str) -> dict:
    if essay_id in _mem_essays:
        return _mem_essays[essay_id]
    db = _db()
    if db:
        try:
            r = db.table("essays").select("*").eq("id", essay_id).single().execute()
            if r.data:
                row = r.data
                if isinstance(row.get("citations"), str):
                    try:
                        row["citations"] = json.loads(row["citations"])
                    except Exception:
                        row["citations"] = []
                _mem_essays[essay_id] = row
                return row
        except Exception:
            pass
    return None

def list_jobs() -> list:
    db = _db()
    if db:
        try:
            r = db.table("jobs").select("*").order("created_at", desc=True).limit(100).execute()
            if r.data:
                return r.data
        except Exception:
            pass
    return list(reversed(list(_mem_jobs.values())))

# ---------- Request model ----------

class EssayRequest(BaseModel):
    topic: str
    paper_type: str = "bachelor"
    language: str = "en"
    additional_instructions: Optional[str] = None
    context_input: Optional[str] = None
    push_to_notion: bool = False

# ---------- Pipeline ----------

async def run_pipeline(job_id: str, req: EssayRequest):
    try:
        update_job(job_id, {"status": "researching", "progress": 20})

        research = await research_topic(req.topic, req.paper_type)
        update_job(job_id, {
            "sources": json.dumps(research["sources"]),
            "source_count": research["source_count"],
            "research_method": research["method"],
            "progress": 50,
            "status": "writing"
        })

        full_context = research["context"]
        if req.context_input:
            full_context += "\n\nUser context: " + req.context_input

        result = await write_essay(
            topic=req.topic,
            paper_type=req.paper_type,
            language=req.language,
            context=full_context,
            additional_instructions=req.additional_instructions
        )
        result["topic"] = req.topic

        essay_id = str(uuid.uuid4())
        essay_doc = {
            "id": essay_id,
            "job_id": job_id,
            "title": result["title"],
            "content": result["content"],
            "citations": result["citations"],
            "word_count": result["word_count"],
            "paper_type": req.paper_type,
            "model_used": result.get("model_used", "gemini-2.5-flash"),
        }
        save_essay(essay_doc)

        notion_url = None
        if req.push_to_notion:
            update_job(job_id, {"status": "pushing_to_notion", "progress": 85})
            notion_url = await push_to_notion(result, req.topic)

        update_job(job_id, {
            "status": "complete",
            "progress": 100,
            "essay_id": essay_id,
            "essay_title": result["title"],
            "word_count": result["word_count"],
            "notion_url": notion_url,
        })

    except Exception as e:
        print(f"Pipeline error: {e}")
        update_job(job_id, {"status": "failed", "progress": 0, "error": str(e)})

# ---------- Routes ----------

@router.post("/generate")
async def generate(req: EssayRequest, bg: BackgroundTasks):
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "topic": req.topic,
        "paper_type": req.paper_type,
        "language": req.language,
        "status": "queued",
        "progress": 5,
        "sources": "[]",
        "source_count": 0,
        "essay_id": None,
        "essay_title": None,
        "word_count": None,
        "notion_url": None,
        "error": None,
        "created_at": None,
    }
    save_job(job)
    bg.add_task(run_pipeline, job_id, req)
    return {"job_id": job_id, "status": "queued", "message": f"Started. Poll /essay/status/{job_id}"}

@router.get("/status/{job_id}")
async def status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    # Parse sources back to list for frontend
    if isinstance(job.get("sources"), str):
        try:
            job["sources"] = json.loads(job["sources"])
        except Exception:
            job["sources"] = []
    return job

@router.get("/result/{job_id}")
async def result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") != "complete":
        raise HTTPException(400, f"Not complete. Status: {job.get('status')}")
    essay = get_essay(job["essay_id"])
    if not essay:
        raise HTTPException(404, "Essay not found")
    return essay

@router.get("/download/{job_id}")
async def download(job_id: str, format: str = "docx"):
    job = get_job(job_id)
    if not job or job.get("status") != "complete":
        raise HTTPException(400, "Essay not ready")
    essay = get_essay(job["essay_id"])
    if not essay:
        raise HTTPException(404, "Essay not found")
    if format == "docx":
        data = export_essay_docx(essay["title"], essay["content"], essay.get("citations", []))
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="essay_{job_id[:8]}.docx"'}
        )
    return Response(
        content=essay["content"],
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="essay_{job_id[:8]}.txt"'}
    )

@router.get("/list")
async def list_essays():
    jobs = list_jobs()
    out = []
    for j in jobs:
        if isinstance(j.get("sources"), str):
            try: j["sources"] = json.loads(j["sources"])
            except: j["sources"] = []
        out.append({
            "job_id": j["id"],
            "topic": j.get("topic", ""),
            "paper_type": j.get("paper_type", ""),
            "status": j.get("status", ""),
            "word_count": j.get("word_count"),
            "title": j.get("essay_title") or j.get("title") or j.get("topic", ""),
        })
    return {"jobs": out, "total": len(out)}
