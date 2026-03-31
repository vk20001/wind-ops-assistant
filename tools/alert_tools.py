"""
Alert Agent tools — create, list, acknowledge, and escalate operational alerts.
"""

from datetime import datetime, timezone

from db.firestore_client import get_client, generate_id, add_audit_log


def create_alert(
    turbine_id: str,
    alert_type: str,
    severity: str,
    description: str,
) -> dict:
    """Create a new operational alert for a turbine.

    Args:
        turbine_id: Turbine identifier (T-001 to T-015)
        alert_type: One of: sensor_anomaly, maintenance_overdue, safety_violation, performance_degradation
        severity: One of: critical, high, medium, low
        description: What triggered this alert

    Returns:
        Dict with alert_id and confirmation
    """
    valid_turbines = [f"T-{str(i).zfill(3)}" for i in range(1, 16)]
    if turbine_id not in valid_turbines:
        return {"success": False, "error": f"Invalid turbine_id '{turbine_id}'. Must be T-001 to T-015."}

    valid_types = ("sensor_anomaly", "maintenance_overdue", "safety_violation", "performance_degradation")
    if alert_type not in valid_types:
        return {"success": False, "error": f"Invalid alert_type '{alert_type}'."}

    valid_severities = ("critical", "high", "medium", "low")
    if severity not in valid_severities:
        return {"success": False, "error": f"Invalid severity '{severity}'."}

    db = get_client()
    alert_id = generate_id("ALERT")
    now = datetime.now(timezone.utc).isoformat()

    alert = {
        "alert_id": alert_id,
        "turbine_id": turbine_id,
        "alert_type": alert_type,
        "severity": severity,
        "description": description,
        "status": "open",
        "created_at": now,
        "acknowledged_by": "",
        "acknowledged_at": "",
        "escalated_to": "",
        "escalation_reason": "",
        "notes": "",
    }

    db.collection("alerts").document(alert_id).set(alert)
    add_audit_log(
        action="alert_created",
        entity_type="alert",
        entity_id=alert_id,
        details=f"{severity} {alert_type} alert for {turbine_id}: {description[:100]}",
    )

    return {
        "success": True,
        "alert_id": alert_id,
        "message": f"Alert {alert_id} created: {severity} {alert_type} on {turbine_id}.",
        "alert": alert,
    }


def list_alerts(
    status: str = "open",
    severity: str = "",
    turbine_id: str = "",
) -> dict:
    """List alerts with optional filters. Defaults to open alerts sorted by severity.

    Args:
        status: Filter by status: open, acknowledged, resolved (empty = all)
        severity: Filter by severity: critical, high, medium, low (empty = all)
        turbine_id: Filter by turbine (empty = all)

    Returns:
        Dict with list of matching alerts and count
    """
    db = get_client()
    query = db.collection("alerts")

    if status:
        query = query.where("status", "==", status)
    if severity:
        query = query.where("severity", "==", severity)
    if turbine_id:
        query = query.where("turbine_id", "==", turbine_id)

    alerts = [d.to_dict() for d in query.stream()]

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    alerts.sort(key=lambda a: severity_order.get(a.get("severity", "low"), 4))

    return {
        "success": True,
        "count": len(alerts),
        "alerts": alerts,
        "message": f"{len(alerts)} alert(s) found.",
    }


def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str,
    notes: str = "",
) -> dict:
    """Acknowledge an alert — confirms it has been seen and is being handled.

    Args:
        alert_id: The alert ID to acknowledge
        acknowledged_by: Name of the person acknowledging
        notes: Optional notes about the acknowledgement or planned action

    Returns:
        Dict with updated alert and confirmation
    """
    db = get_client()
    ref = db.collection("alerts").document(alert_id)
    doc = ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Alert '{alert_id}' not found."}

    alert = doc.to_dict()
    if alert.get("status") == "resolved":
        return {"success": False, "error": f"Alert '{alert_id}' is already resolved."}

    now = datetime.now(timezone.utc).isoformat()
    ref.update({
        "status": "acknowledged",
        "acknowledged_by": acknowledged_by,
        "acknowledged_at": now,
        "notes": notes,
    })

    add_audit_log(
        action="alert_acknowledged",
        entity_type="alert",
        entity_id=alert_id,
        details=f"Acknowledged by {acknowledged_by}" + (f": {notes}" if notes else ""),
        performed_by=acknowledged_by,
    )

    updated = ref.get().to_dict()
    return {
        "success": True,
        "alert_id": alert_id,
        "message": f"Alert {alert_id} acknowledged by {acknowledged_by}.",
        "alert": updated,
    }


def escalate_alert(
    alert_id: str,
    escalate_to: str,
    reason: str,
) -> dict:
    """Escalate an alert — flag it for a specific person or bump its severity.

    Args:
        alert_id: The alert ID to escalate
        escalate_to: Name or role to escalate to (e.g. 'Operations Manager', 'Rajesh Kumar')
        reason: Why this alert is being escalated

    Returns:
        Dict with updated alert and confirmation
    """
    db = get_client()
    ref = db.collection("alerts").document(alert_id)
    doc = ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Alert '{alert_id}' not found."}

    alert = doc.to_dict()
    if alert.get("status") == "resolved":
        return {"success": False, "error": f"Alert '{alert_id}' is already resolved."}

    # Auto-bump severity on escalation
    severity_bump = {"low": "medium", "medium": "high", "high": "critical", "critical": "critical"}
    current_severity = alert.get("severity", "low")
    new_severity = severity_bump.get(current_severity, current_severity)

    ref.update({
        "escalated_to": escalate_to,
        "escalation_reason": reason,
        "severity": new_severity,
    })

    add_audit_log(
        action="alert_escalated",
        entity_type="alert",
        entity_id=alert_id,
        details=f"Escalated to {escalate_to}. Severity: {current_severity} → {new_severity}. Reason: {reason}",
    )

    updated = ref.get().to_dict()
    return {
        "success": True,
        "alert_id": alert_id,
        "message": f"Alert {alert_id} escalated to {escalate_to}. Severity bumped from {current_severity} to {new_severity}.",
        "alert": updated,
    }
def resolve_alert(
    alert_id: str,
    resolved_by: str,
    resolution_notes: str,
) -> dict:
    """Resolve an alert — marks the issue as fixed. This closes the alert lifecycle.

    Args:
        alert_id: The alert ID to resolve
        resolved_by: Name of the person confirming resolution
        resolution_notes: What was done to resolve the issue

    Returns:
        Dict with updated alert and confirmation
    """
    db = get_client()
    ref = db.collection("alerts").document(alert_id)
    doc = ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Alert '{alert_id}' not found."}

    alert = doc.to_dict()
    if alert.get("status") == "resolved":
        return {"success": False, "error": f"Alert '{alert_id}' is already resolved."}

    now = datetime.now(timezone.utc).isoformat()
    ref.update({
        "status": "resolved",
        "resolved_by": resolved_by,
        "resolved_at": now,
        "resolution_notes": resolution_notes,
    })

    add_audit_log(
        action="alert_resolved",
        entity_type="alert",
        entity_id=alert_id,
        details=f"Resolved by {resolved_by}: {resolution_notes}",
        performed_by=resolved_by,
    )

    updated = ref.get().to_dict()
    return {
        "success": True,
        "alert_id": alert_id,
        "message": f"Alert {alert_id} resolved by {resolved_by}.",
        "alert": updated,
    }