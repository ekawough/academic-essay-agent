-- ============================================================
-- Academic Essay Agent — Supabase Schema
-- Run this in the Supabase SQL Editor
-- ============================================================

-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  topic TEXT NOT NULL,
  paper_type TEXT DEFAULT 'bachelor',
  language TEXT DEFAULT 'en',
  status TEXT DEFAULT 'queued',
  progress INTEGER DEFAULT 0,
  sources JSONB DEFAULT '[]',
  source_count INTEGER DEFAULT 0,
  research_method TEXT,
  essay_id UUID,
  essay_title TEXT,
  word_count INTEGER,
  notion_url TEXT,
  error TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Essays table
CREATE TABLE IF NOT EXISTS essays (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  job_id UUID REFERENCES jobs(id),
  title TEXT,
  content TEXT,
  citations JSONB DEFAULT '[]',
  word_count INTEGER,
  paper_type TEXT,
  sections JSONB DEFAULT '[]',
  originality_score FLOAT,
  ai_score FLOAT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Originality checks table
CREATE TABLE IF NOT EXISTS originality_checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  essay_id UUID REFERENCES essays(id),
  copyleaks_scan_id TEXT,
  plagiarism_score FLOAT,
  ai_probability FLOAT,
  burstiness FLOAT,
  vocabulary_richness FLOAT,
  status TEXT DEFAULT 'pending',
  report JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE essays ENABLE ROW LEVEL SECURITY;
ALTER TABLE originality_checks ENABLE ROW LEVEL SECURITY;

-- Service role full access (API uses service key)
CREATE POLICY "Service role access" ON jobs FOR ALL USING (true);
CREATE POLICY "Service role access" ON essays FOR ALL USING (true);
CREATE POLICY "Service role access" ON originality_checks FOR ALL USING (true);

-- Auto-update timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER jobs_updated_at
  BEFORE UPDATE ON jobs
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
