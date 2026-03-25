"""
Seed data for Wind Ops Assistant.
Run once: python -m db.seed_data
Idempotent — checks for existing data before inserting.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
load_dotenv()

from db.firestore_client import get_client

db = get_client()

TODAY = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

TASKS = [
    {
        "task_id": "TASK-001",
        "turbine_id": "T-007",
        "title": "Gearbox vibration above threshold",
        "description": "Vibration sensor reading 4.8mm/s, operational threshold is 4.5mm/s. Monitor and prepare for inspection.",
        "priority": "P1",
        "status": "open",
        "assigned_to": "Rajesh Kumar",
        "fault_type": "gearbox",
        "created_at": (TODAY - timedelta(days=1)).isoformat(),
        "updated_at": (TODAY - timedelta(days=1)).isoformat(),
    },
    {
        "task_id": "TASK-002",
        "turbine_id": "T-012",
        "title": "Blade crack detected on leading edge",
        "description": "Visual inspection flagged a 15cm hairline crack on blade 2 leading edge. Turbine should be taken offline pending repair assessment.",
        "priority": "P1",
        "status": "open",
        "assigned_to": "Arjun Patel",
        "fault_type": "blade",
        "created_at": (TODAY - timedelta(days=2)).isoformat(),
        "updated_at": (TODAY - timedelta(days=2)).isoformat(),
    },
    {
        "task_id": "TASK-003",
        "turbine_id": "T-003",
        "title": "Pitch system inspection due",
        "description": "Scheduled 6-month pitch actuator inspection. Check hydraulic pressure, bearing wear, and calibration.",
        "priority": "P2",
        "status": "open",
        "assigned_to": "Mei Chen",
        "fault_type": "pitch_system",
        "created_at": (TODAY - timedelta(days=3)).isoformat(),
        "updated_at": (TODAY - timedelta(days=3)).isoformat(),
    },
    {
        "task_id": "TASK-004",
        "turbine_id": "T-009",
        "title": "Yaw motor slow response",
        "description": "Yaw alignment taking 40+ seconds vs 20-second baseline. Possible motor wear or encoder fault.",
        "priority": "P2",
        "status": "in_progress",
        "assigned_to": "Rajesh Kumar",
        "fault_type": "yaw",
        "created_at": (TODAY - timedelta(days=4)).isoformat(),
        "updated_at": TODAY.isoformat(),
    },
    {
        "task_id": "TASK-005",
        "turbine_id": "T-001",
        "title": "Routine main bearing lubrication",
        "description": "Scheduled quarterly lubrication cycle. Apply 2kg grease to main bearing housing.",
        "priority": "P3",
        "status": "open",
        "assigned_to": "Mei Chen",
        "fault_type": "bearing",
        "created_at": TODAY.isoformat(),
        "updated_at": TODAY.isoformat(),
    },
    {
        "task_id": "TASK-006",
        "turbine_id": "T-014",
        "title": "Anemometer and wind vane calibration",
        "description": "Annual sensor calibration check. Compare readings against reference station.",
        "priority": "P3",
        "status": "open",
        "assigned_to": "Arjun Patel",
        "fault_type": "",
        "created_at": TODAY.isoformat(),
        "updated_at": TODAY.isoformat(),
    },
    {
        "task_id": "TASK-007",
        "turbine_id": "T-006",
        "title": "Intermittent electrical fault — converter cabinet",
        "description": "SCADA shows sporadic overcurrent trips on the grid-side converter. No clear pattern yet. Check cable connections and IGBT modules.",
        "priority": "P2",
        "status": "open",
        "assigned_to": "Rajesh Kumar",
        "fault_type": "electrical",
        "created_at": (TODAY - timedelta(days=1)).isoformat(),
        "updated_at": (TODAY - timedelta(days=1)).isoformat(),
    },
    {
        "task_id": "TASK-008",
        "turbine_id": "T-011",
        "title": "Annual safety inspection",
        "description": "Full safety compliance inspection: ladder safety system, nacelle access hatch, fire suppression check, grounding continuity.",
        "priority": "P3",
        "status": "open",
        "assigned_to": "Arjun Patel",
        "fault_type": "",
        "created_at": TODAY.isoformat(),
        "updated_at": TODAY.isoformat(),
    },
]


# ---------------------------------------------------------------------------
# Shifts (next 7 days for all technicians)
# ---------------------------------------------------------------------------

def build_shifts():
    shifts = []
    shift_id = 1

    assignments = {
        "Rajesh Kumar": {"shift_type": "morning", "turbines": ["T-005", "T-006", "T-007", "T-008", "T-009", "T-010"]},
        "Mei Chen":     {"shift_type": "afternoon", "turbines": ["T-001", "T-002", "T-003", "T-004", "T-005"]},
        "Arjun Patel":  {"shift_type": "morning", "turbines": ["T-011", "T-012", "T-013", "T-014", "T-015"]},
        "Priya Sharma": {"shift_type": "night", "turbines": ["T-001", "T-003", "T-007", "T-011", "T-015"]},
    }

    for day_offset in range(7):
        date = (TODAY + timedelta(days=day_offset)).strftime("%Y-%m-%d")
        for tech, config in assignments.items():
            shifts.append({
                "shift_id": f"SHIFT-{shift_id:03d}",
                "technician_name": tech,
                "date": date,
                "shift_type": config["shift_type"],
                "turbines_assigned": config["turbines"],
                "notes": "",
            })
            shift_id += 1

    return shifts


# ---------------------------------------------------------------------------
# Maintenance windows
# ---------------------------------------------------------------------------

MAINTENANCE_WINDOWS = [
    {
        "window_id": "MW-001",
        "turbine_id": "T-012",
        "start_date": (TODAY + timedelta(days=1)).strftime("%Y-%m-%d"),
        "end_date": (TODAY + timedelta(days=3)).strftime("%Y-%m-%d"),
        "reason": "repair",
        "status": "planned",
    },
    {
        "window_id": "MW-002",
        "turbine_id": "T-007",
        "start_date": (TODAY + timedelta(days=2)).strftime("%Y-%m-%d"),
        "end_date": (TODAY + timedelta(days=2)).strftime("%Y-%m-%d"),
        "reason": "inspection",
        "status": "planned",
    },
]


# ---------------------------------------------------------------------------
# Documents (SOPs, manuals, safety bulletins)
# ---------------------------------------------------------------------------

DOCUMENTS = [
    {
        "doc_id": "DOC-001",
        "title": "SOP: Gearbox Vibration Response",
        "category": "sop",
        "content": (
            "When gearbox vibration exceeds 4.5mm/s:\n"
            "1. Reduce turbine to 50% power output immediately.\n"
            "2. Log a P1 task in the work order system with current sensor readings.\n"
            "3. Inspect oil sample for metal particle contamination.\n"
            "4. Check gearbox mounting bolts for looseness.\n"
            "5. If vibration exceeds 6.0mm/s, shut down the turbine and escalate to senior engineer.\n"
            "6. Do not restart without written clearance from operations manager."
        ),
        "tags": ["gearbox", "vibration", "safety", "P1"],
        "related_fault_type": "gearbox",
        "related_turbine_id": "",
        "created_by": "Operations Manager",
        "created_at": "2026-01-15T08:00:00Z",
    },
    {
        "doc_id": "DOC-002",
        "title": "SOP: Blade Damage Assessment",
        "category": "sop",
        "content": (
            "Visual or sensor-triggered blade damage protocol:\n"
            "1. Stop the turbine immediately and lock out/tag out.\n"
            "2. Document crack location, length, and direction with photos.\n"
            "3. Classify: surface crazing (<5mm) = monitor; hairline crack (5-20cm) = P1 repair; structural damage (>20cm or near root) = emergency shutdown.\n"
            "4. For hairline cracks: commission drone inspection before allowing any personnel near the blade.\n"
            "5. Notify insurance and schedule approved repair contractor within 48 hours."
        ),
        "tags": ["blade", "crack", "damage", "inspection", "safety"],
        "related_fault_type": "blade",
        "related_turbine_id": "",
        "created_by": "Operations Manager",
        "created_at": "2026-01-20T08:00:00Z",
    },
    {
        "doc_id": "DOC-003",
        "title": "SOP: Pitch System Inspection Checklist",
        "category": "sop",
        "content": (
            "6-month pitch system inspection steps:\n"
            "1. Check hydraulic pressure: nominal 180-220 bar. Flag if outside range.\n"
            "2. Inspect pitch bearing for wear indicators — pitting, spalling, or discolouration.\n"
            "3. Verify pitch angle calibration: all three blades should read within ±0.3° of each other at 0° feather position.\n"
            "4. Test emergency feathering: blade should reach full feather in <8 seconds.\n"
            "5. Lubricate pitch gear ring per manufacturer spec.\n"
            "6. Log all readings in the maintenance record system."
        ),
        "tags": ["pitch", "inspection", "hydraulic", "bearing", "calibration"],
        "related_fault_type": "pitch_system",
        "related_turbine_id": "",
        "created_by": "Lead Technician",
        "created_at": "2026-02-01T08:00:00Z",
    },
    {
        "doc_id": "DOC-004",
        "title": "SOP: Electrical Fault Isolation Procedure",
        "category": "sop",
        "content": (
            "For overcurrent trips or converter faults:\n"
            "1. Check SCADA fault log for fault code and frequency pattern.\n"
            "2. Inspect cable connections in converter cabinet for looseness or heat damage.\n"
            "3. Check IGBT module gate driver signals — oscilloscope required.\n"
            "4. Test DC link capacitor voltage levels.\n"
            "5. If fault recurs within 24 hours after reset, do not restart — escalate to OEM support.\n"
            "6. Document all test readings in the work order."
        ),
        "tags": ["electrical", "converter", "IGBT", "overcurrent", "fault"],
        "related_fault_type": "electrical",
        "related_turbine_id": "",
        "created_by": "Electrical Engineer",
        "created_at": "2026-02-10T08:00:00Z",
    },
    {
        "doc_id": "DOC-005",
        "title": "SOP: Yaw System Troubleshooting",
        "category": "sop",
        "content": (
            "For yaw alignment delays or hunting:\n"
            "1. Check yaw motor current draw — should not exceed 15A during normal alignment.\n"
            "2. Inspect yaw encoder for contamination or loose mounting.\n"
            "3. Verify yaw brake release pressure: nominal 60-80 bar.\n"
            "4. Check nacelle wind vane alignment — misaligned vane causes continuous yaw correction.\n"
            "5. Lubricate yaw ring gear if last lubrication was >3 months ago.\n"
            "6. If response time still exceeds 30 seconds, schedule motor replacement within 2 weeks."
        ),
        "tags": ["yaw", "alignment", "motor", "encoder", "brake"],
        "related_fault_type": "yaw",
        "related_turbine_id": "",
        "created_by": "Lead Technician",
        "created_at": "2026-02-15T08:00:00Z",
    },
    {
        "doc_id": "DOC-006",
        "title": "Safety Bulletin: High Wind Turbine Shutdown Procedure",
        "category": "safety_bulletin",
        "content": (
            "Mandatory shutdown thresholds:\n"
            "- Wind speed >25 m/s (10-min average): automatic pitch-to-feather, controlled shutdown.\n"
            "- Wind speed >30 m/s: emergency stop, mechanical brake engaged.\n"
            "- Gusts exceeding 40 m/s: do not attempt manual restart until wind drops below 20 m/s for 30 minutes.\n"
            "Personnel safety:\n"
            "- No nacelle access when wind speed >15 m/s.\n"
            "- No tower climb when wind speed >12 m/s.\n"
            "- All personnel must be on ground and at least 150m from turbine during emergency shutdown."
        ),
        "tags": ["safety", "wind", "shutdown", "emergency", "personnel"],
        "related_fault_type": "",
        "related_turbine_id": "",
        "created_by": "HSE Manager",
        "created_at": "2026-01-05T08:00:00Z",
    },
    {
        "doc_id": "DOC-007",
        "title": "Manual: Sensor Calibration Reference (T-001 to T-015)",
        "category": "manual",
        "content": (
            "Annual calibration targets for all 15 turbines:\n"
            "- Anemometer: ±0.2 m/s accuracy vs reference station\n"
            "- Wind vane: ±2° alignment accuracy\n"
            "- Vibration sensors (main bearing, gearbox): calibrate to ISO 10816-21 class WTG\n"
            "- Power transducer: ±0.5% full scale\n"
            "- Temperature sensors (gearbox oil, generator winding): ±1°C\n"
            "Calibration tools required: Fluke 435-II power analyser, reference anemometer, vibration calibrator.\n"
            "Frequency: annual for all sensors, plus after any sensor replacement."
        ),
        "tags": ["calibration", "sensors", "anemometer", "vibration", "annual"],
        "related_fault_type": "",
        "related_turbine_id": "",
        "created_by": "Instrumentation Engineer",
        "created_at": "2026-01-10T08:00:00Z",
    },
    {
        "doc_id": "DOC-008",
        "title": "SOP: Bearing Replacement Procedure",
        "category": "sop",
        "content": (
            "Main bearing replacement (planned outage, ~3 days):\n"
            "1. Confirm crane availability and schedule 3-day outage window.\n"
            "2. Lock out / tag out full turbine. Verify zero energy state.\n"
            "3. Remove rotor assembly using main crane — minimum 100-tonne crane required.\n"
            "4. Extract old bearing using hydraulic puller. Inspect shaft for scoring.\n"
            "5. Clean bearing housing to Ra 0.8 surface finish before fitting new bearing.\n"
            "6. Heat new bearing to 80°C max for fitting — do not exceed.\n"
            "7. Reassemble, torque all fasteners to specification sheet, run 72-hour acceptance test before returning to service."
        ),
        "tags": ["bearing", "replacement", "main bearing", "crane", "outage"],
        "related_fault_type": "bearing",
        "related_turbine_id": "",
        "created_by": "Senior Mechanical Engineer",
        "created_at": "2026-01-25T08:00:00Z",
    },
]


# ---------------------------------------------------------------------------
# Seeding logic
# ---------------------------------------------------------------------------

def seed_collection(collection_name: str, docs: list, id_field: str):
    col = db.collection(collection_name)
    seeded = 0
    for doc in docs:
        doc_id = doc[id_field]
        ref = col.document(doc_id)
        if not ref.get().exists:
            ref.set(doc)
            seeded += 1
    print(f"  {collection_name}: seeded {seeded}/{len(docs)} documents")


def main():
    print("Seeding Firestore...")
    seed_collection("tasks", TASKS, "task_id")
    seed_collection("shifts", build_shifts(), "shift_id")
    seed_collection("maintenance_windows", MAINTENANCE_WINDOWS, "window_id")
    seed_collection("documents", DOCUMENTS, "doc_id")
    print("Done.")


if __name__ == "__main__":
    main()
