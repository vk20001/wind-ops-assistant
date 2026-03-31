"""
Schedule Agent tools — technician shift rosters and maintenance window management.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List

from db.firestore_client import get_client, generate_id, add_audit_log


def get_schedule(
    technician: str = "",
    date: str = "",
    week_of: str = "",
) -> dict:
    """Get shift schedule for a technician or date range.

    Args:
        technician: Filter by technician name (empty = all technicians)
        date: Specific date in YYYY-MM-DD format
        week_of: Get full 7-day week starting from this date (YYYY-MM-DD)

    Returns:
        Dict with list of shifts and any maintenance windows in that period
    """
    db = get_client()
    shifts_query = db.collection("shifts")
    windows_query = db.collection("maintenance_windows")

    if technician:
        shifts_query = shifts_query.where("technician_name", "==", technician)

    shifts = [d.to_dict() for d in shifts_query.stream()]

    # Date filtering in Python (Firestore string range queries on date strings work but
    # doing it here avoids composite index requirements)
    if date:
        shifts = [s for s in shifts if s.get("date") == date]
    elif week_of:
        try:
            start = datetime.strptime(week_of, "%Y-%m-%d")
            end = start + timedelta(days=6)
            start_str = start.strftime("%Y-%m-%d")
            end_str = end.strftime("%Y-%m-%d")
            shifts = [s for s in shifts if start_str <= s.get("date", "") <= end_str]
        except ValueError:
            return {"success": False, "error": f"Invalid week_of date format: '{week_of}'. Use YYYY-MM-DD."}

    shifts.sort(key=lambda s: (s.get("date", ""), s.get("shift_type", "")))

    # Pull maintenance windows for context
    windows = [d.to_dict() for d in windows_query.stream()]
    if date:
        windows = [w for w in windows if w.get("start_date", "") <= date <= w.get("end_date", "")]
    elif week_of:
        windows = [
            w for w in windows
            if w.get("start_date", "") <= end_str and w.get("end_date", "") >= start_str
        ]

    return {
        "success": True,
        "shift_count": len(shifts),
        "shifts": shifts,
        "maintenance_windows": windows,
    }


def add_shift(
    technician_name: str,
    date: str,
    shift_type: str,
    turbines_assigned: Optional[List[str]] = None,
    notes: str = "",
) -> dict:
    """Add a shift to the roster.

    Args:
        technician_name: Full name of the technician
        date: Date of the shift in YYYY-MM-DD format
        shift_type: morning (06:00-14:00), afternoon (14:00-22:00), or night (22:00-06:00)
        turbines_assigned: List of turbine IDs assigned for this shift (e.g. ['T-005', 'T-006'])
        notes: Optional shift notes

    Returns:
        Dict with shift_id and confirmation, or conflict warning if technician is double-booked
    """
    if shift_type not in ("morning", "afternoon", "night"):
        return {"success": False, "error": f"Invalid shift_type '{shift_type}'. Use morning, afternoon, or night."}

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"success": False, "error": f"Invalid date format '{date}'. Use YYYY-MM-DD."}

    turbines_assigned = turbines_assigned or []

    db = get_client()

    # Conflict check: same technician, same date, same shift_type
    existing = (
        db.collection("shifts")
        .where("technician_name", "==", technician_name)
        .where("date", "==", date)
        .where("shift_type", "==", shift_type)
        .stream()
    )
    conflicts = [d.to_dict() for d in existing]
    if conflicts:
        return {
            "success": False,
            "conflict": True,
            "message": f"{technician_name} is already scheduled for a {shift_type} shift on {date}.",
            "existing_shift": conflicts[0],
        }

    shift_id = generate_id("SHIFT")
    shift = {
        "shift_id": shift_id,
        "technician_name": technician_name,
        "date": date,
        "shift_type": shift_type,
        "turbines_assigned": turbines_assigned,
        "notes": notes,
    }

    db.collection("shifts").document(shift_id).set(shift)
    add_audit_log(
        action="shift_added",
        entity_type="shift",
        entity_id=shift_id,
        details=f"{technician_name} scheduled for {shift_type} shift on {date}",
    )

    return {
        "success": True,
        "shift_id": shift_id,
        "message": f"Shift {shift_id} added for {technician_name} on {date} ({shift_type}).",
        "shift": shift,
    }


def check_conflicts(
    technician: str = "",
    turbine_id: str = "",
    date_range_start: str = "",
    date_range_end: str = "",
) -> dict:
    """Check for scheduling conflicts in a date range.

    Args:
        technician: Check double-booking conflicts for this technician name
        turbine_id: Check maintenance window overlaps for this turbine ID
        date_range_start: Start date in YYYY-MM-DD format
        date_range_end: End date in YYYY-MM-DD format

    Returns:
        Dict with list of conflicts found, or empty list if none
    """
    db = get_client()
    conflicts = []

    if technician:
        shifts_query = db.collection("shifts").where("technician_name", "==", technician)
        shifts = [d.to_dict() for d in shifts_query.stream()]

        if date_range_start and date_range_end:
            shifts = [s for s in shifts if date_range_start <= s.get("date", "") <= date_range_end]

        # Detect double-booking: same date + same shift_type
        seen = {}
        for s in shifts:
            key = (s["date"], s["shift_type"])
            if key in seen:
                conflicts.append({
                    "type": "double_booking",
                    "technician": technician,
                    "date": s["date"],
                    "shift_type": s["shift_type"],
                    "shift_ids": [seen[key]["shift_id"], s["shift_id"]],
                })
            else:
                seen[key] = s

    if turbine_id:
        windows = [d.to_dict() for d in db.collection("maintenance_windows").stream()]
        turbine_windows = [w for w in windows if w.get("turbine_id") == turbine_id]

        if date_range_start and date_range_end:
            turbine_windows = [
                w for w in turbine_windows
                if w.get("start_date", "") <= date_range_end and w.get("end_date", "") >= date_range_start
            ]

        # Detect overlapping windows for same turbine
        for i, w1 in enumerate(turbine_windows):
            for w2 in turbine_windows[i + 1:]:
                if w1["start_date"] <= w2["end_date"] and w1["end_date"] >= w2["start_date"]:
                    conflicts.append({
                        "type": "maintenance_window_overlap",
                        "turbine_id": turbine_id,
                        "window_ids": [w1["window_id"], w2["window_id"]],
                        "overlap_period": f"{max(w1['start_date'], w2['start_date'])} to {min(w1['end_date'], w2['end_date'])}",
                    })

    return {
        "success": True,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "message": "No conflicts found." if not conflicts else f"{len(conflicts)} conflict(s) detected.",
    }

def get_availability(
    date: str,
    shift_type: str = "",
) -> dict:
    """Find which technicians are available (not already scheduled) on a given date and shift.

    Args:
        date: Date to check in YYYY-MM-DD format
        shift_type: Specific shift to check: morning, afternoon, night (empty = show all shifts)

    Returns:
        Dict with available technicians per shift type
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"success": False, "error": f"Invalid date format '{date}'. Use YYYY-MM-DD."}

    if shift_type and shift_type not in ("morning", "afternoon", "night"):
        return {"success": False, "error": f"Invalid shift_type '{shift_type}'. Use morning, afternoon, or night."}

    db = get_client()

    # Pull technician roster from Firestore instead of hardcoding
    all_technicians = [
        d.to_dict()["name"]
        for d in db.collection("technicians").stream()
    ]

    if not all_technicians:
        return {"success": False, "error": "No technicians found in database."}

    shift_types = [shift_type] if shift_type else ["morning", "afternoon", "night"]

    existing_shifts = [
        d.to_dict()
        for d in db.collection("shifts").where("date", "==", date).stream()
    ]

    availability = {}
    for st in shift_types:
        scheduled = [
            s["technician_name"]
            for s in existing_shifts
            if s.get("shift_type") == st
        ]
        available = [t for t in all_technicians if t not in scheduled]
        availability[st] = {
            "available": available,
            "scheduled": scheduled,
        }

    return {
        "success": True,
        "date": date,
        "availability": availability,
        "message": f"Availability for {date}" + (f" ({shift_type} shift)" if shift_type else " (all shifts)"),
    }


def swap_shifts(
    shift_id_1: str,
    shift_id_2: str,
) -> dict:
    """Swap two technicians' shifts. Both shifts must exist. Swaps technician_name and turbines_assigned between them.

    Args:
        shift_id_1: First shift ID to swap
        shift_id_2: Second shift ID to swap

    Returns:
        Dict with confirmation and updated shift details
    """
    if shift_id_1 == shift_id_2:
        return {"success": False, "error": "Cannot swap a shift with itself."}

    db = get_client()
    ref1 = db.collection("shifts").document(shift_id_1)
    ref2 = db.collection("shifts").document(shift_id_2)

    doc1 = ref1.get()
    doc2 = ref2.get()

    if not doc1.exists:
        return {"success": False, "error": f"Shift '{shift_id_1}' not found."}
    if not doc2.exists:
        return {"success": False, "error": f"Shift '{shift_id_2}' not found."}

    s1 = doc1.to_dict()
    s2 = doc2.to_dict()

    ref1.update({
        "technician_name": s2["technician_name"],
        "turbines_assigned": s2.get("turbines_assigned", []),
    })
    ref2.update({
        "technician_name": s1["technician_name"],
        "turbines_assigned": s1.get("turbines_assigned", []),
    })

    add_audit_log(
        action="shift_swapped",
        entity_type="shift",
        entity_id=f"{shift_id_1},{shift_id_2}",
        details=f"Swapped {s1['technician_name']} ({shift_id_1}) with {s2['technician_name']} ({shift_id_2})",
    )

    return {
        "success": True,
        "message": f"Swapped: {s1['technician_name']} now has {shift_id_2}, {s2['technician_name']} now has {shift_id_1}.",
        "shift_1": {
            "shift_id": shift_id_1,
            "now_assigned_to": s2["technician_name"],
            "date": s1.get("date"),
            "shift_type": s1.get("shift_type"),
        },
        "shift_2": {
            "shift_id": shift_id_2,
            "now_assigned_to": s1["technician_name"],
            "date": s2.get("date"),
            "shift_type": s2.get("shift_type"),
        },
    }  
def delete_shift(
    shift_id: str,
) -> dict:
    """Delete a shift from the roster (e.g. to free up a technician for a specific day).

    Args:
        shift_id: The shift ID to delete (e.g. SHIFT-024)

    Returns:
        Dict with confirmation of deleted shift details
    """
    db = get_client()
    ref = db.collection("shifts").document(shift_id)
    doc = ref.get()

    if not doc.exists:
        return {"success": False, "error": f"Shift '{shift_id}' not found."}

    shift = doc.to_dict()
    ref.delete()

    add_audit_log(
        action="shift_deleted",
        entity_type="shift",
        entity_id=shift_id,
        details=f"Deleted {shift['technician_name']}'s {shift.get('shift_type', '')} shift on {shift.get('date', '')}",
    )

    return {
        "success": True,
        "message": f"Shift {shift_id} deleted. {shift['technician_name']} is now free on {shift.get('date', '')} ({shift.get('shift_type', '')}).",
        "deleted_shift": shift,
    }