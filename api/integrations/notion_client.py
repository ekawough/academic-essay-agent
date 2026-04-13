import os
from notion_client import AsyncClient

notion = None
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

def init_notion():
    global notion
    token = os.getenv("NOTION_TOKEN")
    if token:
        notion = AsyncClient(auth=token)
        print("Notion connected.")
    else:
        print("Notion not configured. Set NOTION_TOKEN in .env to enable.")

async def push_to_notion(essay: dict, topic: str = "") -> str:
    """
    Pushes a completed essay to Notion as a full page.
    Returns the created page URL or error string.
    """
    if not notion:
        return "Notion not configured"

    db_id = DATABASE_ID
    if not db_id:
        return "NOTION_DATABASE_ID not set"

    try:
        page = await notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "Title": {"title": [{"text": {"content": essay.get("title", "Untitled Essay")[:2000]}}]},
                "Topic": {"rich_text": [{"text": {"content": topic[:2000]}}]},
                "Type": {"select": {"name": essay.get("paper_type", "bachelor")}},
                "Status": {"select": {"name": "Complete"}},
                "Word Count": {"number": essay.get("word_count", 0)},
            }
        )

        page_id = page["id"]
        content = essay.get("content", "")

        # Split content into 1900-char chunks (Notion block limit is 2000)
        chunks = [content[i:i+1900] for i in range(0, len(content), 1900)]

        blocks = []
        for chunk in chunks:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": chunk}}]
                }
            })

        # Add references as toggle block
        citations = essay.get("citations", [])
        if citations:
            citations_text = "\n".join([f"[{i+1}] {cite}" for i, cite in enumerate(citations[:50])])
            blocks.append({
                "object": "block",
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"text": {"content": "References"}}],
                    "children": [{
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": citations_text[:1900]}}]
                        }
                    }]
                }
            })

        # Append blocks in batches of 100 (Notion API limit)
        for i in range(0, len(blocks), 100):
            await notion.blocks.children.append(
                block_id=page_id,
                children=blocks[i:i+100]
            )

        return page.get("url", "Created in Notion")

    except Exception as e:
        return f"Notion error: {str(e)}"
