"""
Task Agent tools — maintenance work order management.
All writes are logged to audit_log collection.
"""

from datetime import datetime, timezone
from typing import Optional, List

from db.firestore_client import get_client, generate_id, add_audit_log


def create_task(
    turbine_id: str,
    title: str,
    priority: str,
    description: str = "",
    assigned_to: str = "",
    fault_type: str = "",
) -> dict:
    """Create a new maintenance task for a wind turbine.

    Args:
        turbine_id: Turbine identifier (T-001 to T-015)
        title: Short task description
        priority: P1 (safety-critical), P2 (performance), P3 (routine)
        description: Detailed task description
        assigned_to: Technician name
        fault_type: One of: gearbox, bearing, pitch_system, electrical, blade, yaw

    Returns:
        Dict with task_id, status, and confirmation message
    """
    valid_turbines = [f"T-{str(i).zfill(3)}" for i in range(1, 16)]
    if turbine_id not in valid_turbines:
        return {"success": False, "error": f"Invalid turbine_id '{turbine_id}'. Must be T-001 to T-015."}

    if priority not in ("P1", "P2", "P3"):
        return {"success": False, "error": f"Invalid priority '{priority}'. Must be P1, P2, or P3."}

    valid_fault_types = ("gearbox", "bearing", "pitch_system", "electrical", "blade", "yaw", "")
    if fault_type not in valid_fault_types:
        return {"success": False, "error": f"Invalid fault_type '{fault_type}'."}

    db = get_client()
    task_id = generate_id("TASK")
    now = datetime.now(timezone.utc).isoformat()

    task = {
        "task_id": task_id,
        "turbine_id": turbine_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "assigned_to": assigned_to,
        "fault_type": fault_type,
        "created_at": now,
        "updated_at": now,
    }

    db.collection("tasks").document(task_id).set(task)
    add_audit_log(
        action="task_created",
        entity_type="task",
        entity_id=task_id,
        details=f"{priority} task created for {turbine_id}: {title}",
        performed_by=assigned_to or "system",
    )

    return {
        "success": True,
        "task_id": task_id,
        "message": f"Task {task_id} created for {turbine_id} with priority {priority}.",
        "task": task,
    }


def list_tasks(
    turbine_id: str = "",
    status: str = "open",
    priority: str = "",
    assigned_to: str = "",
) -> dict:
    """List maintenance tasks with optional filters.

    Args:
        turbine_id: Filter by turbine (empty = all turbines)
        status: Filter by status: open, in_progress, completed, blocked (empty = all statuses)
        priority: Filter by priority: P1, P2, P3 (empty = all priorities)
        assigned_to: Filter by technician name (empty = all technicians)

    Returns:
        Dict with list of matching tasks and count
    """
    db = get_client()
    query = db.collection("tasks")

    if turbine_id:
        query = query.where("turbine_id", "==", turbine_id)
    if status:
        query = query.where("status", "==", status)
    if priority:
        query = query.where("priority", "==", priority)
    if assigned_to:
        query = query.where("assigned_to", "==", assigned_to)

    docs = query.stream()
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    tasks = sorted(
        [d.to_dict() for d in docs],
        key=lambda t: priority_order.get(t.get("priority", "P3"), 3),
    )

    return {
        "success": True,
        "count": len(tasks),
        "tasks": tasks,
    }


def update_task(
    task_id: str,
    status: str = "",
    assigned_to: str = "",
    priority: str = "",
    description: str = "",
) -> dict:
    """Update an existing task's status, assignment, or details.

    Args:
        task_id: The task identifier to update
        status: New status: open, in_progress, completed, blocked
        assigned_to: New assignee name
        priority: New priority level: P1, P2, P3
        description: Updated description

    Returns:
        Dict with updated task and confirmation
    """
    db = get_client()
    ref = db.collection("tasks").document(task_id)
    doc = ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Task '{task_id}' not found."}

    updates = {"updated_at": datetime.now(timezone.utc).isoformat()}
    changes = []

    if status:
        valid_statuses = ("open", "in_progress", "completed", "blocked")
        if status not in valid_statuses:
            return {"success": False, "error": f"Invalid status '{status}'."}
        updates["status"] = status
        changes.append(f"status → {status}")

    if assigned_to:
        updates["assigned_to"] = assigned_to
        changes.append(f"assigned_to → {assigned_to}")

    if priority:
        if priority not in ("P1", "P2", "P3"):
            return {"success": False, "error": f"Invalid priority '{priority}'."}
        updates["priority"] = priority
        changes.append(f"priority → {priority}")

    if description:
        updates["description"] = description
        changes.append("description updated")

    if not changes:
        return {"success": False, "error": "No valid fields provided to update."}

    ref.update(updates)
    add_audit_log(
        action="task_updated",
        entity_type="task",
        entity_id=task_id,
        details=", ".join(changes),
    )

    updated = ref.get().to_dict()
    return {
        "success": True,
        "task_id": task_id,
        "message": f"Task {task_id} updated: {', '.join(changes)}.",
        "task": updated,
    }
