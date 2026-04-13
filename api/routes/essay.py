from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
import uuid
import json

from api.agents.researcher import research_topic
from api.agents.ghostwriter import write_essay, export_essay_docx
from api.integrations.notion_client import push_to_notion

router = APIRouter()

# In-memory job store (replace with Supabase in production)
jobs_store = {}
essays_store = {}

class EssayRequest(BaseModel):
    topic: str
    paper_type: str = "bachelor"
    language: str = "en"
    additional_instructions: Optional[str] = None
    context_input: Optional[str] = None
    push_to_notion: bool = False

class EssayResponse(BaseModel):
    job_id: str
    status: str
    message: str

async def process_essay(job_id: str, req: EssayRequest):
    try:
        # Status: researching
        jobs_store[job_id]["status"] = "researching"
        jobs_store[job_id]["progress"] = 20

        # Step 1: Research
        research = await research_topic(req.topic, req.paper_type)
        jobs_store[job_id]["sources"] = research["sources"]
        jobs_store[job_id]["source_count"] = research["source_count"]
        jobs_store[job_id]["research_method"] = research["method"]

        # Status: writing
        jobs_store[job_id]["status"] = "writing"
        jobs_store[job_id]["progress"] = 50

        # Step 2: Write
        essay = await write_essay(
            topic=req.topic,
            paper_type=req.paper_type,
            language=req.language,
            context=research["context"] + ("

User context: " + req.context_input if req.context_input else ""),
            additional_instructions=req.additional_instructions
        )
        essay["topic"] = req.topic

        # Store essay
        essay_id = str(uuid.uuid4())
        essays_store[essay_id] = essay
        jobs_store[job_id]["essay_id"] = essay_id
        jobs_store[job_id]["progress"] = 80

        # Step 3: Push to Notion if requested
        if req.push_to_notion:
            jobs_store[job_id]["status"] = "pushing_to_notion"
            notion_url = await push_to_notion(essay, req.topic)
            jobs_store[job_id]["notion_url"] = notion_url

        # Done
        jobs_store[job_id]["status"] = "complete"
        jobs_store[job_id]["progress"] = 100
        jobs_store[job_id]["essay_title"] = essay["title"]
        jobs_store[job_id]["word_count"] = essay["word_count"]

        # Try Supabase if configured
        try:
            from api.integrations.supabase_client import supabase
            if supabase:
                await supabase.table("jobs").update({
                    "status": "complete",
                    "essay_id": essay_id,
                    "word_count": essay["word_count"]
                }).eq("id", job_id).execute()

                await supabase.table("essays").insert({
                    "id": essay_id,
                    "job_id": job_id,
                    "title": essay["title"],
                    "content": essay["content"],
                    "citations": json.dumps(essay["citations"]),
                    "word_count": essay["word_count"],
                    "paper_type": req.paper_type,
                }).execute()
        except Exception:
            pass  # Supabase optional

    except Exception as e:
        jobs_store[job_id]["status"] = "failed"
        jobs_store[job_id]["error"] = str(e)
        jobs_store[job_id]["progress"] = 0

@router.post("/generate", response_model=EssayResponse)
async def generate_essay(req: EssayRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())

    jobs_store[job_id] = {
        "id": job_id,
        "topic": req.topic,
        "paper_type": req.paper_type,
        "language": req.language,
        "status": "queued",
        "progress": 5,
        "sources": [],
        "source_count": 0,
    }

    # Try Supabase
    try:
        from api.integrations.supabase_client import supabase
        if supabase:
            supabase.table("jobs").insert({
                "id": job_id, "topic": req.topic,
                "paper_type": req.paper_type, "status": "queued"
            }).execute()
    except Exception:
        pass

    background_tasks.add_task(process_essay, job_id, req)

    return EssayResponse(
        job_id=job_id,
        status="queued",
        message=f"Essay generation started. Poll /essay/status/{job_id} for updates."
    )

@router.get("/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs_store:
        raise HTTPException(404, "Job not found")
    return jobs_store[job_id]

@router.get("/result/{job_id}")
async def get_result(job_id: str):
    job = jobs_store.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "complete":
        raise HTTPException(400, f"Job is not complete. Status: {job['status']}")

    essay_id = job.get("essay_id")
    if not essay_id or essay_id not in essays_store:
        raise HTTPException(404, "Essay not found")

    return essays_store[essay_id]

@router.get("/download/{job_id}")
async def download_essay(job_id: str, format: str = "docx"):
    job = jobs_store.get(job_id)
    if not job or job["status"] != "complete":
        raise HTTPException(400, "Essay not ready")

    essay_id = job.get("essay_id")
    essay = essays_store.get(essay_id)
    if not essay:
        raise HTTPException(404, "Essay not found")

    if format == "docx":
        doc_bytes = export_essay_docx(essay["title"], essay["content"], essay["citations"])
        return Response(
            content=doc_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="essay_{job_id[:8]}.docx"'}
        )
    elif format == "txt":
        return Response(
            content=essay["content"],
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="essay_{job_id[:8]}.txt"'}
        )
    else:
        raise HTTPException(400, "Format must be 'docx' or 'txt'")

@router.get("/list")
async def list_essays():
    completed = [
        {
            "job_id": jid,
            "topic": j["topic"],
            "paper_type": j["paper_type"],
            "status": j["status"],
            "word_count": j.get("word_count"),
            "title": j.get("essay_title"),
        }
        for jid, j in jobs_store.items()
    ]
    return {"jobs": completed, "total": len(completed)}
