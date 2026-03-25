import os
from google.cloud import firestore

_client = None


def get_client() -> firestore.Client:
    global _client
    if _client is None:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        _client = firestore.Client(project=project)
    return _client


def generate_id(prefix: str) -> str:
    """Generate a human-readable sequential-style ID using Firestore auto-id as suffix."""
    import uuid
    short = uuid.uuid4().hex[:6].upper()
    return f"{prefix}-{short}"


def add_audit_log(action: str, entity_type: str, entity_id: str, details: str, performed_by: str = "system"):
    from datetime import datetime, timezone
    db = get_client()
    log_ref = db.collection("audit_log").document()
    log_ref.set({
        "log_id": log_ref.id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "performed_by": performed_by,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "details": details,
    })
