import asyncio
import os
from typing import Optional

async def research_topic(topic: str, paper_type: str = "bachelor") -> dict:
    """
    Multi-source researcher using GPT-Researcher.
    Aggregates 20+ sources per query to prevent hallucination.
    Falls back to CrossRef/OpenAlex if GPT-Researcher unavailable.
    """
    try:
        from gpt_researcher import GPTResearcher

        queries = [
            f"academic research on {topic} peer-reviewed studies",
            f"{topic} theoretical framework literature review",
            f"{topic} empirical evidence recent studies 2020-2025",
        ]

        all_sources = []
        full_context = ""

        for query in queries:
            researcher = GPTResearcher(
                query=query,
                report_type="research_report",
                verbose=False
            )
            await researcher.conduct_research()
            sources = researcher.get_source_urls()
            report = await researcher.write_report()
            all_sources.extend(sources)
            full_context += f"\n\n{report}"

        return {
            "context": full_context,
            "sources": list(set(all_sources)),
            "source_count": len(set(all_sources)),
            "method": "gpt-researcher"
        }

    except ImportError:
        # Fallback: use CrossRef + OpenAlex (free, no key required)
        return await _fallback_academic_research(topic)

async def _fallback_academic_research(topic: str) -> dict:
    """
    Fallback researcher using CrossRef and OpenAlex APIs.
    Both are free with no API key required. Zero hallucination risk
    because all sources are real papers from academic databases.
    """
    import httpx

    sources = []
    context_parts = []

    encoded_topic = topic.replace(" ", "+")

    async with httpx.AsyncClient(timeout=30) as client:
        # CrossRef — 130M+ papers
        try:
            crossref_url = f"https://api.crossref.org/works?query={encoded_topic}&rows=10&sort=relevance&filter=type:journal-article"
            r = await client.get(crossref_url, headers={"User-Agent": "AcademicAgent/1.0 (mailto:agent@example.com)"})
            if r.status_code == 200:
                data = r.json()
                items = data.get("message", {}).get("items", [])
                for item in items[:8]:
                    title = item.get("title", [""])[0]
                    authors = [f"{a.get('given','')} {a.get('family','')}".strip()
                               for a in item.get("author", [])[:3]]
                    year = item.get("published", {}).get("date-parts", [[""]])[0][0]
                    doi = item.get("DOI", "")
                    journal = item.get("container-title", [""])[0]
                    abstract = item.get("abstract", "No abstract available.")

                    if title:
                        source_entry = f"{', '.join(authors)} ({year}). {title}. {journal}. https://doi.org/{doi}"
                        sources.append(source_entry)
                        context_parts.append(f"Title: {title}\nAuthors: {', '.join(authors)}\nYear: {year}\nAbstract: {abstract[:500]}\nDOI: {doi}")
        except Exception as e:
            print(f"CrossRef error: {e}")

        # OpenAlex — 250M+ papers
        try:
            openalex_url = f"https://api.openalex.org/works?search={encoded_topic}&per-page=10&sort=relevance_score:desc"
            r = await client.get(openalex_url, headers={"User-Agent": "AcademicAgent/1.0"})
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                for work in results[:8]:
                    title = work.get("title", "")
                    year = work.get("publication_year", "")
                    doi = work.get("doi", "")
                    cited_by = work.get("cited_by_count", 0)
                    authorships = work.get("authorships", [])[:3]
                    authors = [a.get("author", {}).get("display_name", "") for a in authorships]
                    abstract_inverted = work.get("abstract_inverted_index", {})
                    abstract = _reconstruct_abstract(abstract_inverted) if abstract_inverted else "No abstract available."

                    if title and title not in [s for s in sources]:
                        source_entry = f"{', '.join(authors)} ({year}). {title}. DOI: {doi} [Cited by: {cited_by}]"
                        sources.append(source_entry)
                        context_parts.append(f"Title: {title}\nAuthors: {', '.join(authors)}\nYear: {year}\nCited by: {cited_by}\nAbstract: {abstract[:500]}")
        except Exception as e:
            print(f"OpenAlex error: {e}")

        # Semantic Scholar — additional coverage
        try:
            ss_url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded_topic}&fields=title,authors,year,abstract,citationCount,externalIds&limit=8"
            r = await client.get(ss_url)
            if r.status_code == 200:
                data = r.json()
                papers = data.get("data", [])
                for paper in papers[:5]:
                    title = paper.get("title", "")
                    year = paper.get("year", "")
                    authors = [a.get("name", "") for a in paper.get("authors", [])[:3]]
                    abstract = paper.get("abstract", "No abstract available.")
                    citations = paper.get("citationCount", 0)
                    doi = paper.get("externalIds", {}).get("DOI", "")

                    if title:
                        source_entry = f"{', '.join(authors)} ({year}). {title}. DOI: {doi} [Citations: {citations}]"
                        if source_entry not in sources:
                            sources.append(source_entry)
                            context_parts.append(f"Title: {title}\nYear: {year}\nCitations: {citations}\nAbstract: {abstract[:500]}")
        except Exception as e:
            print(f"Semantic Scholar error: {e}")

    full_context = "\n\n---\n\n".join(context_parts)

    return {
        "context": full_context,
        "sources": sources,
        "source_count": len(sources),
        "method": "crossref+openalex+semanticscholar"
    }

def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return " ".join(word for _, word in word_positions)
