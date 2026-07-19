from typing import Optional, List
from pydantic import BaseModel
from app.database import repository as repo


class SaveNoteInput(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class SearchNotesInput(BaseModel):
    query: str
    category: Optional[str] = None


NOTE_TOOL_DEFS = [
    {
        "name": "save_note",
        "description": (
            "Save a new note to the database. "
            "Use this to store meeting notes, ideas, research, or reference information. "
            "REQUIRES human approval before execution."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short descriptive title for the note"},
                "content": {"type": "string", "description": "Full content of the note"},
                "category": {
                    "type": "string",
                    "description": "Category such as 'meeting', 'research', 'ideas', 'reference'",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Tags for easy retrieval",
                },
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "search_notes",
        "description": (
            "Search notes by keyword in title or content. "
            "Use this to find previously saved notes or reference information. "
            "Does NOT require approval."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search keyword or phrase"},
                "category": {
                    "type": "string",
                    "description": "Optionally filter by category",
                },
            },
            "required": ["query"],
        },
    },
]


def execute_note_tool(name: str, tool_input: dict) -> dict:
    if name == "save_note":
        inp = SaveNoteInput(**tool_input)
        note = repo.save_note(
            title=inp.title,
            content=inp.content,
            category=inp.category,
            tags=inp.tags,
        )
        return {"success": True, "note": note, "message": f"Note #{note['id']} saved: {note['title']}"}

    if name == "search_notes":
        inp = SearchNotesInput(**tool_input)
        notes = repo.search_notes(query=inp.query, category=inp.category)
        return {"success": True, "notes": notes, "count": len(notes)}

    return {"success": False, "error": f"Unknown note tool: {name}"}
