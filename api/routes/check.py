from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from api.agents.originality import OriginalityChecker
from api.routes.essay import get_job, get_essay

router = APIRouter()
checker = OriginalityChecker()

class CheckRequest(BaseModel):
    essay_id: Optional[str] = None
    job_id: Optional[str] = None
    text: Optional[str] = None

@router.post("/originality")
async def check_originality(req: CheckRequest):
    text = None
    essay_id = req.essay_id

    if req.text:
        text = req.text
        essay_id = "direct_check"
    elif req.job_id:
        job = get_job(req.job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        essay_id = job.get("essay_id")
        if not essay_id:
            raise HTTPException(400, "No essay for this job yet")
        essay = get_essay(essay_id)
        if not essay:
            raise HTTPException(404, "Essay not found")
        text = essay.get("content", "")
    elif req.essay_id:
        essay = get_essay(req.essay_id)
        if not essay:
            raise HTTPException(404, "Essay not found")
        text = essay.get("content", "")
    else:
        raise HTTPException(400, "Provide essay_id, job_id, or text")

    results = await checker.check(text, essay_id)
    return results

@router.post("/webhook/{scan_id}")
async def copyleaks_webhook(scan_id: str, payload: dict = {}):
    print(f"Copyleaks webhook: {scan_id}")
    return {"received": True}
