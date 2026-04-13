# Academic Essay Agent

AI-powered academic essay writer for bachelor's and master's level papers.
Uses real academic sources (CrossRef, OpenAlex, Semantic Scholar) — no hallucinated citations.

## Stack

| Layer | Tech | Purpose |
|-------|------|---------|
| Backend | FastAPI on Railway | Orchestrator API |
| LLM | Claude (Anthropic) | Essay writing |
| Research | CrossRef + OpenAlex + Semantic Scholar | Real verified citations |
| Persistence | Supabase (Postgres) | Jobs + essays storage |
| Workspace | Notion API | Push finished essays |
| Originality | Copyleaks API + local heuristics | Plagiarism + AI detection |

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/academic-agent.git
cd academic-agent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY
```

### 3. Run locally

```bash
uvicorn api.main:app --reload --port 8000
```

Visit `http://localhost:8000` for the UI, or `http://localhost:8000/docs` for the API.

---

## Deploy to Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → GitHub repo
3. Add environment variables (copy from `.env`)
4. Railway auto-deploys from Dockerfile
5. Settings → Networking → Generate Domain

---

## Supabase Setup

1. Create project at [supabase.com](https://supabase.com)
2. SQL Editor → paste contents of `supabase_schema.sql` → Run
3. Copy `Project URL`, `anon key`, and `service_role key` to `.env`

---

## Notion Setup

1. Go to [notion.so/my-integrations](https://notion.so/my-integrations) → New Integration
2. Name it "Academic Essay Agent", copy the token
3. Create a Notion database with these properties:
   - Title (Title type)
   - Topic (Text)
   - Type (Select: research_paper, bachelor, master)
   - Status (Select: Complete, Failed)
   - Word Count (Number)
4. Share the database with your integration (Share → Invite)
5. Copy the database ID from the URL (it's the 32-char ID after the last slash)

---

## API Reference

### Generate Essay
```bash
POST /essay/generate
{
  "topic": "The impact of social media on mental health",
  "paper_type": "bachelor",   # research_paper | bachelor | master
  "language": "en",
  "additional_instructions": "Focus on college students aged 18-24",
  "push_to_notion": true
}
```

### Check Status
```bash
GET /essay/status/{job_id}
```

### Get Result
```bash
GET /essay/result/{job_id}
```

### Download DOCX
```bash
GET /essay/download/{job_id}?format=docx
```

### Check Originality
```bash
POST /check/originality
{
  "job_id": "your-job-id"
}
```

---

## Paper Types

| Type | Word Count | Use Case |
|------|-----------|----------|
| `research_paper` | 2,000–3,000 | Short academic papers, essays |
| `bachelor` | 3,000–5,000 | Undergraduate level papers |
| `master` | 5,000–8,000 | Graduate level papers |

---

## Cost Estimate

| Scenario | Cost |
|----------|------|
| research_paper (Gemini Flash) | ~$0.10 |
| bachelor (Claude Sonnet) | ~$0.35 |
| master (Claude Opus) | ~$1.20 |
| With Copyleaks scan | +$0.40/page |

---

## Anti-Hallucination Strategy

1. **Research phase**: Only uses CrossRef, OpenAlex, and Semantic Scholar — real papers with real DOIs
2. **Writing phase**: Injects verified research context into the prompt; model told not to invent citations
3. **Citation verification**: All cited DOIs can be spot-checked against academic databases

---

## License

MIT
