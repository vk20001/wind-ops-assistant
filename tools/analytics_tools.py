"""
Analytics Agent tools — farm health, turbine status, KPIs, workload analysis.
Read-only tools that query across multiple Firestore collections.
"""

from datetime import datetime, timezone

from db.firestore_client import get_client


def turbine_health_summary(
    turbine_id: str,
) -> dict:
    """Get a health snapshot for a single turbine — open tasks, alerts, field notes, maintenance windows.

    Args:
        turbine_id: Turbine identifier (e.g. T-007)

    Returns:
        Dict with open tasks, active alerts, recent notes, and maintenance windows for this turbine
    """
    valid_turbines = [f"T-{str(i).zfill(3)}" for i in range(1, 16)]
    if turbine_id not in valid_turbines:
        return {"success": False, "error": f"Invalid turbine_id '{turbine_id}'. Must be T-001 to T-015."}

    db = get_client()

    # Open tasks for this turbine
    tasks = [
        d.to_dict() for d in
        db.collection("tasks")
        .where("turbine_id", "==", turbine_id)
        .where("status", "in", ["open", "in_progress"])
        .stream()
    ]

    # Active alerts for this turbine
    alerts = [
        d.to_dict() for d in
        db.collection("alerts")
        .where("turbine_id", "==", turbine_id)
        .where("status", "in", ["open", "acknowledged"])
        .stream()
    ]

    # Maintenance windows for this turbine
    windows = [
        d.to_dict() for d in
        db.collection("maintenance_windows")
        .where("turbine_id", "==", turbine_id)
        .stream()
    ]

    # Field notes mentioning this turbine
    notes = [
        d.to_dict() for d in
        db.collection("documents")
        .where("related_turbine_id", "==", turbine_id)
        .stream()
    ]

    has_critical = any(
        a.get("severity") == "critical" for a in alerts
    ) or any(
        t.get("priority") == "P1" for t in tasks
    )

    status = "CRITICAL" if has_critical else "NEEDS ATTENTION" if (tasks or alerts) else "HEALTHY"

    return {
        "success": True,
        "turbine_id": turbine_id,
        "status": status,
        "open_tasks": [{"task_id": t["task_id"], "title": t["title"], "priority": t["priority"], "assigned_to": t.get("assigned_to", "")} for t in tasks],
        "active_alerts": [{"alert_id": a["alert_id"], "alert_type": a["alert_type"], "severity": a["severity"], "description": a["description"]} for a in alerts],
        "maintenance_windows": [{"window_id": w["window_id"], "start_date": w["start_date"], "end_date": w["end_date"], "reason": w["reason"]} for w in windows],
        "related_documents": [{"doc_id": n["doc_id"], "title": n["title"], "category": n["category"]} for n in notes],
        "message": f"{turbine_id}: {status}. {len(tasks)} open task(s), {len(alerts)} active alert(s).",
    }


def farm_overview() -> dict:
    """Get a high-level health overview of all 15 turbines in the farm.

    Returns:
        Dict with per-turbine status summary and farm-wide counts
    """
    db = get_client()

    all_tasks = [d.to_dict() for d in db.collection("tasks").where("status", "in", ["open", "in_progress"]).stream()]
    all_alerts = [d.to_dict() for d in db.collection("alerts").where("status", "in", ["open", "acknowledged"]).stream()]

    turbine_ids = [f"T-{str(i).zfill(3)}" for i in range(1, 16)]
    summary = []
    critical_count = 0
    attention_count = 0
    healthy_count = 0

    for tid in turbine_ids:
        t_tasks = [t for t in all_tasks if t["turbine_id"] == tid]
        t_alerts = [a for a in all_alerts if a["turbine_id"] == tid]

        has_critical = any(a.get("severity") == "critical" for a in t_alerts) or any(t.get("priority") == "P1" for t in t_tasks)

        if has_critical:
            status = "CRITICAL"
            critical_count += 1
        elif t_tasks or t_alerts:
            status = "NEEDS ATTENTION"
            attention_count += 1
        else:
            status = "HEALTHY"
            healthy_count += 1

        if status != "HEALTHY":
            summary.append({
                "turbine_id": tid,
                "status": status,
                "open_tasks": len(t_tasks),
                "active_alerts": len(t_alerts),
            })

    return {
        "success": True,
        "total_turbines": 15,
        "critical": critical_count,
        "needs_attention": attention_count,
        "healthy": healthy_count,
        "turbines_with_issues": summary,
        "message": f"Farm: {critical_count} critical, {attention_count} need attention, {healthy_count} healthy.",
    }


def maintenance_kpis() -> dict:
    """Calculate maintenance performance metrics from task history.

    Returns:
        Dict with KPIs: total tasks, completion rate, open P1 count, tasks by status and priority
    """
    db = get_client()
    all_tasks = [d.to_dict() for d in db.collection("tasks").stream()]

    total = len(all_tasks)
    if total == 0:
        return {"success": True, "message": "No tasks found.", "total_tasks": 0}

    completed = sum(1 for t in all_tasks if t.get("status") == "completed")
    open_count = sum(1 for t in all_tasks if t.get("status") == "open")
    in_progress = sum(1 for t in all_tasks if t.get("status") == "in_progress")
    blocked = sum(1 for t in all_tasks if t.get("status") == "blocked")

    p1_open = [t for t in all_tasks if t.get("priority") == "P1" and t.get("status") in ("open", "in_progress")]

    completion_rate = round((completed / total) * 100, 1) if total > 0 else 0

    # Average age of open tasks in days
    now = datetime.now(timezone.utc)
    open_tasks = [t for t in all_tasks if t.get("status") in ("open", "in_progress")]
    ages = []
    for t in open_tasks:
        created = t.get("created_at", "")
        if created:
            try:
                created_dt = datetime.fromisoformat(created)
                age_days = (now - created_dt).total_seconds() / 86400
                ages.append(round(age_days, 1))
            except (ValueError, TypeError):
                pass

    avg_age = round(sum(ages) / len(ages), 1) if ages else 0

    return {
        "success": True,
        "total_tasks": total,
        "completion_rate_percent": completion_rate,
        "by_status": {"open": open_count, "in_progress": in_progress, "completed": completed, "blocked": blocked},
        "open_p1_count": len(p1_open),
        "open_p1_tasks": [{"task_id": t["task_id"], "turbine_id": t["turbine_id"], "title": t["title"]} for t in p1_open],
        "avg_open_task_age_days": avg_age,
        "message": f"{total} total tasks. {completion_rate}% completion rate. {len(p1_open)} open P1. Avg open task age: {avg_age} days.",
    }


def technician_workload(
    technician_name: str = "",
) -> dict:
    """Get workload breakdown per technician — open tasks, upcoming shifts, and overload flag.

    Args:
        technician_name: Specific technician (empty = all technicians)

    Returns:
        Dict with task count, shift count, and overload status per technician
    """
    db = get_client()

    technicians = [d.to_dict() for d in db.collection("technicians").stream()]
    if technician_name:
        technicians = [t for t in technicians if t["name"] == technician_name]
        if not technicians:
            return {"success": False, "error": f"Technician '{technician_name}' not found."}

    all_tasks = [d.to_dict() for d in db.collection("tasks").where("status", "in", ["open", "in_progress"]).stream()]
    all_shifts = [d.to_dict() for d in db.collection("shifts").stream()]

    workloads = []
    for tech in technicians:
        name = tech["name"]
        tech_tasks = [t for t in all_tasks if t.get("assigned_to") == name]
        tech_shifts = [s for s in all_shifts if s.get("technician_name") == name]

        p1_count = sum(1 for t in tech_tasks if t.get("priority") == "P1")
        overloaded = len(tech_tasks) >= 4 or p1_count >= 2

        workloads.append({
            "technician": name,
            "role": tech.get("role", ""),
            "open_tasks": len(tech_tasks),
            "p1_tasks": p1_count,
            "upcoming_shifts": len(tech_shifts),
            "task_list": [{"task_id": t["task_id"], "turbine_id": t["turbine_id"], "title": t["title"], "priority": t["priority"]} for t in tech_tasks],
            "overloaded": overloaded,
        })

    workloads.sort(key=lambda w: w["open_tasks"])

    return {
        "success": True,
        "technician_count": len(workloads),
        "workloads": workloads,
        "message": f"Workload for {len(workloads)} technician(s). Least loaded: {workloads[0]['technician']} ({workloads[0]['open_tasks']} tasks)." if workloads else "No technicians found.",
    }