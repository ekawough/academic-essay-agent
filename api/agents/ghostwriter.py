import os
import re
from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

PAPER_CONFIGS = {
    "research_paper": {
        "word_count": "2000-3000",
        "sections": ["Abstract", "Introduction", "Literature Review", "Methodology", "Results & Discussion", "Conclusion", "References"],
        "description": "A focused academic research paper with clear thesis, evidence, and argumentation.",
        "tone": "formal academic, objective, evidence-based"
    },
    "bachelor": {
        "word_count": "3000-5000",
        "sections": ["Abstract", "Introduction", "Literature Review", "Theoretical Framework", "Methodology", "Analysis & Discussion", "Conclusion", "References"],
        "description": "A bachelor's level academic essay demonstrating understanding of the field, critical analysis, and academic writing conventions.",
        "tone": "formal academic, analytical, well-structured, demonstrates critical thinking"
    },
    "master": {
        "word_count": "5000-8000",
        "sections": ["Abstract", "Introduction", "Literature Review", "Theoretical Framework", "Methodology", "Findings & Analysis", "Discussion", "Conclusion", "References"],
        "description": "A master's level paper with sophisticated analysis, original argumentation, and deep engagement with scholarly literature.",
        "tone": "highly academic, nuanced, demonstrates advanced critical analysis and original thinking"
    }
}

async def write_essay(
    topic: str,
    paper_type: str = "bachelor",
    language: str = "en",
    context: str = None,
    additional_instructions: str = None
) -> dict:
    config = PAPER_CONFIGS.get(paper_type, PAPER_CONFIGS["bachelor"])

    context_section = ""
    if context:
        context_section = f"\n\n## Verified Research Context (cite ONLY these sources):\n\n{context[:8000]}\n\n---"

    instructions_section = f"\nAdditional requirements: {additional_instructions}\n" if additional_instructions else ""

    prompt = f"""You are an expert academic ghostwriter specializing in {paper_type}-level essays.

Standards:
- Tone: {config['tone']}
- Target length: {config['word_count']} words
- Structure: {', '.join(config['sections'])}
- Use in-text citations (Author, Year) format for ALL claims
- Only cite sources from the research context provided — do NOT invent citations
- Formal academic language appropriate for university submission
- Strong thesis statement in the introduction
- Smooth transitions between sections
- Critical thinking throughout, not just description

CRITICAL: Never invent DOIs, authors, or journals. If no source supports a claim, write "further research is needed" or omit it.

Output: Full essay with ## section headers. End with ## References in APA 7th edition.

Topic: {topic}
Paper type: {paper_type}
Language: {language}
{instructions_section}
{context_section}

Write the complete essay now, starting with the Abstract:"""

    response = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=8192,
            temperature=0.7,
        )
    )

    full_text = response.text
    return {
        "title": _extract_title(full_text, topic),
        "content": full_text,
        "sections": _parse_sections(full_text),
        "citations": _extract_citations(full_text),
        "word_count": len(full_text.split()),
        "paper_type": paper_type,
        "model_used": "gemini-2.5-flash-lite"
    }

def _parse_sections(text):
    return re.findall(r'^##\s+(.+)$', text, re.MULTILINE)

def _extract_citations(text):
    ref_match = re.search(r'##\s+References?\s*\n([\s\S]+?)(?:##|$)', text, re.IGNORECASE)
    if ref_match:
        return [l.strip() for l in ref_match.group(1).strip().split('\n') if l.strip() and not l.strip().startswith('#')]
    return []

def _extract_title(text, fallback):
    for line in text.split('\n')[:10]:
        line = line.strip()
        if line and not line.startswith('#') and 20 < len(line) < 150:
            if not any(kw in line.lower() for kw in ['abstract', 'introduction', 'write']):
                return line
    m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    return m.group(1) if m else f"Academic Essay: {fallback.title()}"

def export_essay_docx(title, content, citations):
    try:
        from docx import Document
        from docx.shared import Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import io
        doc = Document()
        for s in doc.sections:
            s.top_margin = s.bottom_margin = Inches(1)
            s.left_margin = s.right_margin = Inches(1.25)
        p = doc.add_heading(title, 0)
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        doc.add_paragraph()
        for line in content.split('\n'):
            line = line.strip()
            if not line: continue
            if line.startswith('## '): doc.add_heading(line[3:], level=2)
            elif line.startswith('# '): doc.add_heading(line[2:], level=1)
            else: doc.add_paragraph(line)
        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()
    except ImportError:
        return content.encode('utf-8')
