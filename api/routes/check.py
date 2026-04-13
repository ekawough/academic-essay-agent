from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from api.agents.originality import OriginalityChecker
from api.routes.essay import essays_store, jobs_store

router = APIRouter()
checker = OriginalityChecker()

class CheckRequest(BaseModel):
    essay_id: str = None
    job_id: str = None
    text: str = None  # direct text check

@router.post("/originality")
async def check_originality(req: CheckRequest):
    text = None
    essay_id = req.essay_id

    if req.text:
        text = req.text
        essay_id = "direct_check"
    elif req.job_id:
        job = jobs_store.get(req.job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        essay_id = job.get("essay_id")
        if not essay_id:
            raise HTTPException(400, "No essay found for this job")
        essay = essays_store.get(essay_id)
        if not essay:
            raise HTTPException(404, "Essay not found")
        text = essay["content"]
    elif req.essay_id:
        essay = essays_store.get(req.essay_id)
        if not essay:
            raise HTTPException(404, "Essay not found")
        text = essay["content"]
    else:
        raise HTTPException(400, "Provide essay_id, job_id, or text")

    results = await checker.check(text, essay_id)
    return results

@router.post("/webhook/{scan_id}")
async def copyleaks_webhook(scan_id: str, payload: dict):
    """Receives Copyleaks webhook callback with scan results."""
    # Store results (in production, update Supabase)
    print(f"Copyleaks webhook received for scan {scan_id}: {payload}")
    return {"received": True}
