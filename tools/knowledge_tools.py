"""
Knowledge Agent tools — SOPs, manuals, field notes, safety bulletins.
Search is keyword-based across title, tags, content, and fault_type.
"""

from datetime import datetime, timezone
from typing import Optional, List

from db.firestore_client import get_client, generate_id, add_audit_log


def search_docs(
    query: str = "",
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
def list_recent_notes(
    limit: int = 10,
    related_turbine_id: str = "",
    created_by: str = "",
) -> dict:
    """List the most recent field notes, optionally filtered by turbine or author.

    Args:
        limit: Max number of notes to return (default 10)
        related_turbine_id: Filter to notes about a specific turbine (e.g. T-012)
        created_by: Filter to notes by a specific author

    Returns:
        Dict with list of recent field notes sorted by creation date (newest first)
    """
    db = get_client()
    query = db.collection("documents").where("category", "==", "field_note")

    docs = [d.to_dict() for d in query.stream()]

    if related_turbine_id:
        docs = [d for d in docs if d.get("related_turbine_id") == related_turbine_id]
    if created_by:
        docs = [d for d in docs if d.get("created_by") == created_by]

    docs.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    docs = docs[:limit]

    results = []
    for doc in docs:
        content = doc.get("content", "")
        snippet = content[:200] + "..." if len(content) > 200 else content
        results.append({
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "snippet": snippet,
            "related_turbine_id": doc.get("related_turbine_id", ""),
            "created_by": doc.get("created_by", ""),
            "created_at": doc.get("created_at", ""),
            "tags": doc.get("tags", []),
        })

    return {
        "success": True,
        "count": len(results),
        "notes": results,
        "message": f"{len(results)} recent field note(s) found.",
    }


def search_by_turbine(
    turbine_id: str,
) -> dict:
    """Get all knowledge base documents related to a specific turbine — SOPs, field notes, manuals, safety bulletins.

    Args:
        turbine_id: Turbine identifier (e.g. T-007)

    Returns:
        Dict with all documents mentioning this turbine, grouped by category
    """
    valid_turbines = [f"T-{str(i).zfill(3)}" for i in range(1, 16)]
    if turbine_id not in valid_turbines:
        return {"success": False, "error": f"Invalid turbine_id '{turbine_id}'. Must be T-001 to T-015."}

    db = get_client()
    all_docs = [d.to_dict() for d in db.collection("documents").stream()]

    turbine_lower = turbine_id.lower()

    def matches_turbine(doc):
        if doc.get("related_turbine_id", "") == turbine_id:
            return True
        text = (
            doc.get("title", "").lower()
            + " "
            + doc.get("content", "").lower()
            + " "
            + " ".join(doc.get("tags", [])).lower()
        )
        return turbine_lower in text

    matched = [d for d in all_docs if matches_turbine(d)]

    grouped = {}
    for doc in matched:
        cat = doc.get("category", "unknown")
        if cat not in grouped:
            grouped[cat] = []
        content = doc.get("content", "")
        snippet = content[:200] + "..." if len(content) > 200 else content
        grouped[cat].append({
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "snippet": snippet,
            "related_fault_type": doc.get("related_fault_type", ""),
            "tags": doc.get("tags", []),
        })

    return {
        "success": True,
        "turbine_id": turbine_id,
        "total_documents": len(matched),
        "by_category": grouped,
        "message": f"{len(matched)} document(s) found for {turbine_id}.",
    }