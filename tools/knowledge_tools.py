"""
Knowledge Agent tools — SOPs, manuals, field notes, safety bulletins.
Search is keyword-based across title, tags, content, and fault_type.
"""

from datetime import datetime, timezone
from typing import Optional, List

from db.firestore_client import get_client, generate_id, add_audit_log


def search_docs(
    query: str,
    category: str = "",
    fault_type: str = "",
) -> dict:
    """Search operational documents, SOPs, manuals, and field notes.

    Args:
        query: Search terms — matched against title, tags, and content
        category: Filter by category: sop, manual, field_note, safety_bulletin (empty = all)
        fault_type: Filter by related fault type: gearbox, bearing, pitch_system, electrical, blade, yaw

    Returns:
        Dict with matching documents including title, snippet, doc_id, and category
    """
    db = get_client()
    docs_query = db.collection("documents")

    if category:
        docs_query = docs_query.where("category", "==", category)
    if fault_type:
        docs_query = docs_query.where("related_fault_type", "==", fault_type)

    all_docs = [d.to_dict() for d in docs_query.stream()]

    # Keyword match: split query into terms, score by hits
    terms = [t.lower() for t in query.split() if len(t) > 2]

    def score(doc):
        text = (
            doc.get("title", "").lower()
            + " "
            + " ".join(doc.get("tags", [])).lower()
            + " "
            + doc.get("content", "").lower()
            + " "
            + doc.get("related_fault_type", "").lower()
        )
        return sum(1 for term in terms if term in text)

    scored = [(score(d), d) for d in all_docs]
    # Include docs with at least one term hit, or all docs if no terms
    if terms:
        scored = [(s, d) for s, d in scored if s > 0]
    scored.sort(key=lambda x: -x[0])

    results = []
    for _, doc in scored:
        content = doc.get("content", "")
        snippet = content[:200] + "..." if len(content) > 200 else content
        results.append({
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "category": doc["category"],
            "related_fault_type": doc.get("related_fault_type", ""),
            "snippet": snippet,
            "tags": doc.get("tags", []),
        })

    return {
        "success": True,
        "count": len(results),
        "documents": results,
    }


def add_note(
    title: str,
    content: str,
    related_turbine_id: str = "",
    related_fault_type: str = "",
    tags: Optional[List[str]] = None,
    created_by: str = "",
) -> dict:
    """Add a field note or observation to the knowledge base.

    Args:
        title: Short descriptive title for the note
        content: Full note content — observations, measurements, findings
        related_turbine_id: Turbine this note relates to (e.g. T-012), empty if general
        related_fault_type: Related fault type if applicable: gearbox, bearing, pitch_system, electrical, blade, yaw
        tags: List of keyword tags for searchability
        created_by: Name of the person adding the note

    Returns:
        Dict with doc_id and confirmation
    """
    tags = tags or []

    db = get_client()
    doc_id = generate_id("DOC")
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "doc_id": doc_id,
        "title": title,
        "category": "field_note",
        "content": content,
        "tags": tags,
        "related_fault_type": related_fault_type,
        "related_turbine_id": related_turbine_id,
        "created_by": created_by,
        "created_at": now,
    }

    db.collection("documents").document(doc_id).set(doc)
    add_audit_log(
        action="note_added",
        entity_type="document",
        entity_id=doc_id,
        details=f"Field note added: '{title}'" + (f" for {related_turbine_id}" if related_turbine_id else ""),
        performed_by=created_by or "system",
    )

    return {
        "success": True,
        "doc_id": doc_id,
        "message": f"Field note '{title}' saved as {doc_id}.",
        "document": doc,
    }


def get_doc(doc_id: str) -> dict:
    """Retrieve the full content of a specific document by ID.

    Args:
        doc_id: Document identifier (e.g. DOC-001)

    Returns:
        Dict with full document content and all metadata
    """
    db = get_client()
    ref = db.collection("documents").document(doc_id)
    doc = ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Document '{doc_id}' not found."}

    return {
        "success": True,
        "document": doc.to_dict(),
    }
