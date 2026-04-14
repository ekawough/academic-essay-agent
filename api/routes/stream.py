from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import asyncio, threading, json, os

router = APIRouter()

class QuickGenRequest(BaseModel):
    prompt: str
    system: Optional[str] = None

class RewriteRequest(BaseModel):
    text: str
    action: str  # improve, shorten, expand, academic, simplify, professional, casual

class OutlineRequest(BaseModel):
    topic: str
    content_type: str = "essay"
    notes: Optional[str] = None

REWRITE_PROMPTS = {
    "improve":       "Improve this text. Make it clearer, more engaging, and better written. Keep the same meaning and length.",
    "shorten":       "Shorten this text by 40-50%. Keep the most important points. Do not add anything new.",
    "expand":        "Expand this text with more detail, examples, and depth. Keep the same tone.",
    "academic":      "Rewrite this in formal academic style. Use precise language, third-person perspective, and scholarly tone.",
    "simplify":      "Simplify this text. Use shorter sentences, simpler words. Make it easy for anyone to understand.",
    "professional":  "Rewrite this in a polished, professional tone suitable for a business or workplace context.",
    "casual":        "Rewrite this in a friendly, conversational tone. Natural and easy to read.",
    "creative":      "Rewrite this with more vivid language, stronger imagery, and creative expression.",
    "persuasive":    "Rewrite this to be more persuasive. Use compelling arguments and a confident tone.",
}

async def _stream_gemini(prompt: str, system: Optional[str] = None):
    """Async generator that yields text tokens from Gemini streaming API."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    loop = asyncio.get_running_loop()
    q: asyncio.Queue = asyncio.Queue()

    config = types.GenerateContentConfig(max_output_tokens=4096, temperature=0.7)
    contents = prompt
    if system:
        config = types.GenerateContentConfig(
            max_output_tokens=4096,
            temperature=0.7,
            system_instruction=system
        )

    def producer():
        try:
            for chunk in client.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=contents,
                config=config
            ):
                if chunk.text:
                    loop.call_soon_threadsafe(q.put_nowait, ("text", chunk.text))
        except Exception as e:
            loop.call_soon_threadsafe(q.put_nowait, ("error", str(e)))
        finally:
            loop.call_soon_threadsafe(q.put_nowait, ("done", None))

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    while True:
        kind, value = await q.get()
        if kind == "done":
            yield "data: [DONE]\n\n"
            break
        elif kind == "error":
            yield f"data: {json.dumps({'error': value})}\n\n"
            break
        else:
            yield f"data: {json.dumps({'text': value})}\n\n"

@router.post("/quick")
async def stream_quick(req: QuickGenRequest):
    """Stream a quick generation (social posts, emails, short content)."""
    return StreamingResponse(
        _stream_gemini(req.prompt, req.system),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@router.post("/rewrite")
async def stream_rewrite(req: RewriteRequest):
    """Stream a rewrite of selected text."""
    action_prompt = REWRITE_PROMPTS.get(req.action, REWRITE_PROMPTS["improve"])
    prompt = f"{action_prompt}\n\nText to rewrite:\n\n{req.text}\n\nRewritten version:"
    return StreamingResponse(
        _stream_gemini(prompt),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

@router.post("/outline")
async def generate_outline(req: OutlineRequest):
    """Generate a structured outline for a topic."""
    from google import genai
    from google.genai import types

    type_instructions = {
        "essay": "academic essay with thesis, body paragraphs, and conclusion",
        "blog": "blog post with introduction, main sections, and call to action",
        "research": "research paper with abstract, literature review, methodology, results, discussion",
        "creative": "short story or creative piece with beginning, middle, and end",
        "email": "professional email with subject, opening, body, and closing",
        "social": "social media content series",
    }
    format_desc = type_instructions.get(req.content_type, "structured document")

    prompt = f"""Generate a detailed outline for a {format_desc} on: "{req.topic}"
{f'Additional notes: {req.notes}' if req.notes else ''}

Return ONLY a JSON object in this exact format:
{{
  "title": "Suggested title for the piece",
  "sections": [
    {{"heading": "Section heading", "points": ["Key point 1", "Key point 2", "Key point 3"]}},
    {{"heading": "Section heading", "points": ["Key point 1", "Key point 2"]}}
  ]
}}"""

    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = await asyncio.to_thread(
        lambda: client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(max_output_tokens=1024, temperature=0.5)
        )
    )

    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        return {"title": req.topic, "sections": [{"heading": "Introduction", "points": ["Add your key points here"]}]}
