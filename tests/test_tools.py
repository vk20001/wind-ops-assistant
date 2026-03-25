"""
Tests for all tool functions.
Mocks Firestore — run without GCP credentials.
Run: python -m pytest tests/ -v
"""

import os
import sys
import pytest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone

os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"


# ---------------------------------------------------------------------------
# Firestore mock helpers
# ---------------------------------------------------------------------------

def make_doc(data: dict):
    """Return a mock Firestore DocumentSnapshot."""
    doc = MagicMock()
    doc.exists = True
    doc.to_dict.return_value = data
    return doc


def make_query_result(docs: list):
    """Return a mock that streams a list of dicts as DocumentSnapshots."""
    mock_query = MagicMock()
    mock_query.stream.return_value = [make_doc(d) for d in docs]
    mock_query.where.return_value = mock_query
    return mock_query


# ---------------------------------------------------------------------------
# Task tools
# ---------------------------------------------------------------------------

class TestCreateTask:

    def test_creates_task_successfully(self):
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.task_tools.get_client", return_value=mock_db), \
             patch("tools.task_tools.add_audit_log"):
            from tools.task_tools import create_task
            result = create_task(
                turbine_id="T-007",
                title="Gearbox vibration check",
                priority="P1",
                assigned_to="Rajesh Kumar",
                fault_type="gearbox",
            )

        assert result["success"] is True
        assert "task_id" in result
        assert result["task"]["turbine_id"] == "T-007"
        assert result["task"]["priority"] == "P1"
        assert result["task"]["status"] == "open"
        mock_ref.set.assert_called_once()

    def test_rejects_invalid_turbine(self):
        with patch("tools.task_tools.get_client"):
            from tools.task_tools import create_task
            result = create_task(turbine_id="T-099", title="test", priority="P1")
        assert result["success"] is False
        assert "T-099" in result["error"]

    def test_rejects_invalid_priority(self):
        with patch("tools.task_tools.get_client"):
            from tools.task_tools import create_task
            result = create_task(turbine_id="T-001", title="test", priority="P4")
        assert result["success"] is False
        assert "P4" in result["error"]

    def test_rejects_invalid_fault_type(self):
        with patch("tools.task_tools.get_client"):
            from tools.task_tools import create_task
            result = create_task(turbine_id="T-001", title="test", priority="P2", fault_type="fire")
        assert result["success"] is False

    def test_all_turbine_ids_valid(self):
        mock_db = MagicMock()
        with patch("tools.task_tools.get_client", return_value=mock_db), \
             patch("tools.task_tools.add_audit_log"):
            from tools.task_tools import create_task
            for i in range(1, 16):
                turbine_id = f"T-{str(i).zfill(3)}"
                result = create_task(turbine_id=turbine_id, title="test", priority="P3")
                assert result["success"] is True, f"Failed for {turbine_id}"


class TestListTasks:

    def test_lists_open_tasks_sorted_by_priority(self):
        tasks = [
            {"task_id": "TASK-003", "priority": "P3", "status": "open"},
            {"task_id": "TASK-001", "priority": "P1", "status": "open"},
            {"task_id": "TASK-002", "priority": "P2", "status": "open"},
        ]
        mock_db = MagicMock()
        mock_query = make_query_result(tasks)
        mock_db.collection.return_value = mock_query

        with patch("tools.task_tools.get_client", return_value=mock_db):
            from tools.task_tools import list_tasks
            result = list_tasks(status="open")

        assert result["success"] is True
        assert result["count"] == 3
        priorities = [t["priority"] for t in result["tasks"]]
        assert priorities == ["P1", "P2", "P3"]

    def test_returns_empty_list_when_no_tasks(self):
        mock_db = MagicMock()
        mock_query = make_query_result([])
        mock_db.collection.return_value = mock_query

        with patch("tools.task_tools.get_client", return_value=mock_db):
            from tools.task_tools import list_tasks
            result = list_tasks()

        assert result["success"] is True
        assert result["count"] == 0
        assert result["tasks"] == []

    def test_filter_by_turbine(self):
        mock_db = MagicMock()
        mock_query = make_query_result([])
        mock_db.collection.return_value = mock_query

        with patch("tools.task_tools.get_client", return_value=mock_db):
            from tools.task_tools import list_tasks
            list_tasks(turbine_id="T-007")

        # Verify where clause was called for turbine filter
        mock_query.where.assert_any_call("turbine_id", "==", "T-007")


class TestUpdateTask:

    def test_updates_status_successfully(self):
        existing = {"task_id": "TASK-001", "turbine_id": "T-007", "priority": "P1", "status": "open"}
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_ref.get.return_value = make_doc(existing)
        mock_ref.get.return_value.exists = True
        # Second get (after update) returns updated doc
        updated = {**existing, "status": "in_progress"}
        mock_ref.get.side_effect = [make_doc(existing), make_doc(updated)]
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.task_tools.get_client", return_value=mock_db), \
             patch("tools.task_tools.add_audit_log"):
            from tools.task_tools import update_task
            result = update_task(task_id="TASK-001", status="in_progress")

        assert result["success"] is True
        mock_ref.update.assert_called_once()

    def test_returns_error_for_missing_task(self):
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_ref.get.return_value.exists = False
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.task_tools.get_client", return_value=mock_db):
            from tools.task_tools import update_task
            result = update_task(task_id="TASK-999", status="completed")

        assert result["success"] is False
        assert "TASK-999" in result["error"]

    def test_rejects_invalid_status(self):
        existing = {"task_id": "TASK-001", "status": "open"}
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_ref.get.return_value = make_doc(existing)
        mock_ref.get.return_value.exists = True
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.task_tools.get_client", return_value=mock_db):
            from tools.task_tools import update_task
            result = update_task(task_id="TASK-001", status="deleted")

        assert result["success"] is False

    def test_rejects_update_with_no_fields(self):
        existing = {"task_id": "TASK-001", "status": "open"}
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_ref.get.return_value = make_doc(existing)
        mock_ref.get.return_value.exists = True
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.task_tools.get_client", return_value=mock_db):
            from tools.task_tools import update_task
            result = update_task(task_id="TASK-001")

        assert result["success"] is False
        assert "No valid fields" in result["error"]


# ---------------------------------------------------------------------------
# Schedule tools
# ---------------------------------------------------------------------------

class TestGetSchedule:

    def test_returns_shifts_for_technician(self):
        shifts = [
            {"shift_id": "SHIFT-001", "technician_name": "Rajesh Kumar", "date": "2026-03-26", "shift_type": "morning", "turbines_assigned": ["T-007"]},
        ]
        mock_db = MagicMock()
        shifts_query = make_query_result(shifts)
        windows_query = make_query_result([])

        def collection_side_effect(name):
            if name == "shifts":
                return shifts_query
            return windows_query

        mock_db.collection.side_effect = collection_side_effect

        with patch("tools.schedule_tools.get_client", return_value=mock_db):
            from tools.schedule_tools import get_schedule
            result = get_schedule(technician="Rajesh Kumar", date="2026-03-26")

        assert result["success"] is True
        assert result["shift_count"] == 1

    def test_filters_by_week(self):
        shifts = [
            {"shift_id": "S1", "date": "2026-03-30", "shift_type": "morning", "technician_name": "Rajesh Kumar", "turbines_assigned": []},
            {"shift_id": "S2", "date": "2026-04-10", "shift_type": "morning", "technician_name": "Rajesh Kumar", "turbines_assigned": []},
        ]
        mock_db = MagicMock()
        shifts_query = make_query_result(shifts)
        windows_query = make_query_result([])

        def collection_side_effect(name):
            return shifts_query if name == "shifts" else windows_query

        mock_db.collection.side_effect = collection_side_effect

        with patch("tools.schedule_tools.get_client", return_value=mock_db):
            from tools.schedule_tools import get_schedule
            result = get_schedule(week_of="2026-03-30")

        assert result["success"] is True
        assert result["shift_count"] == 1
        assert result["shifts"][0]["shift_id"] == "S1"

    def test_invalid_week_format(self):
        with patch("tools.schedule_tools.get_client", return_value=MagicMock()):
            from tools.schedule_tools import get_schedule
            result = get_schedule(week_of="30-03-2026")
        assert result["success"] is False


class TestAddShift:

    def test_adds_shift_when_no_conflict(self):
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.where.return_value.where.return_value.where.return_value.stream.return_value = []
        mock_doc_ref = MagicMock()
        mock_col.document.return_value = mock_doc_ref
        mock_db.collection.return_value = mock_col

        with patch("tools.schedule_tools.get_client", return_value=mock_db), \
             patch("tools.schedule_tools.add_audit_log"):
            from tools.schedule_tools import add_shift
            result = add_shift(
                technician_name="Rajesh Kumar",
                date="2026-04-01",
                shift_type="morning",
                turbines_assigned=["T-005", "T-006"],
            )

        assert result["success"] is True
        assert "shift_id" in result

    def test_returns_conflict_on_double_booking(self):
        existing_shift = {
            "shift_id": "SHIFT-001",
            "technician_name": "Rajesh Kumar",
            "date": "2026-04-01",
            "shift_type": "morning",
        }
        mock_db = MagicMock()
        mock_col = MagicMock()
        mock_col.where.return_value.where.return_value.where.return_value.stream.return_value = [make_doc(existing_shift)]
        mock_db.collection.return_value = mock_col

        with patch("tools.schedule_tools.get_client", return_value=mock_db):
            from tools.schedule_tools import add_shift
            result = add_shift(
                technician_name="Rajesh Kumar",
                date="2026-04-01",
                shift_type="morning",
            )

        assert result["success"] is False
        assert result["conflict"] is True

    def test_rejects_invalid_shift_type(self):
        with patch("tools.schedule_tools.get_client", return_value=MagicMock()):
            from tools.schedule_tools import add_shift
            result = add_shift(technician_name="Rajesh Kumar", date="2026-04-01", shift_type="evening")
        assert result["success"] is False

    def test_rejects_invalid_date_format(self):
        with patch("tools.schedule_tools.get_client", return_value=MagicMock()):
            from tools.schedule_tools import add_shift
            result = add_shift(technician_name="Rajesh Kumar", date="01-04-2026", shift_type="morning")
        assert result["success"] is False


class TestCheckConflicts:

    def test_no_conflicts_returns_empty(self):
        shifts = [
            {"shift_id": "S1", "date": "2026-03-30", "shift_type": "morning", "technician_name": "Rajesh Kumar"},
            {"shift_id": "S2", "date": "2026-03-31", "shift_type": "morning", "technician_name": "Rajesh Kumar"},
        ]
        mock_db = MagicMock()

        def collection_side_effect(name):
            q = MagicMock()
            q.where.return_value = q
            q.stream.return_value = [make_doc(s) for s in shifts] if name == "shifts" else []
            return q

        mock_db.collection.side_effect = collection_side_effect

        with patch("tools.schedule_tools.get_client", return_value=mock_db):
            from tools.schedule_tools import check_conflicts
            result = check_conflicts(technician="Rajesh Kumar", date_range_start="2026-03-30", date_range_end="2026-04-05")

        assert result["success"] is True
        assert result["conflict_count"] == 0

    def test_detects_double_booking(self):
        shifts = [
            {"shift_id": "S1", "date": "2026-03-30", "shift_type": "morning", "technician_name": "Rajesh Kumar"},
            {"shift_id": "S2", "date": "2026-03-30", "shift_type": "morning", "technician_name": "Rajesh Kumar"},
        ]
        mock_db = MagicMock()

        def collection_side_effect(name):
            q = MagicMock()
            q.where.return_value = q
            q.stream.return_value = [make_doc(s) for s in shifts] if name == "shifts" else []
            return q

        mock_db.collection.side_effect = collection_side_effect

        with patch("tools.schedule_tools.get_client", return_value=mock_db):
            from tools.schedule_tools import check_conflicts
            result = check_conflicts(technician="Rajesh Kumar")

        assert result["conflict_count"] == 1
        assert result["conflicts"][0]["type"] == "double_booking"


# ---------------------------------------------------------------------------
# Knowledge tools
# ---------------------------------------------------------------------------

class TestSearchDocs:

    def test_returns_matching_docs(self):
        docs = [
            {"doc_id": "DOC-001", "title": "SOP: Gearbox Vibration Response", "category": "sop",
             "content": "When gearbox vibration exceeds 4.5mm/s...", "tags": ["gearbox", "vibration"],
             "related_fault_type": "gearbox"},
            {"doc_id": "DOC-002", "title": "SOP: Blade Damage Assessment", "category": "sop",
             "content": "Visual blade inspection...", "tags": ["blade", "crack"],
             "related_fault_type": "blade"},
        ]
        mock_db = MagicMock()
        mock_query = make_query_result(docs)
        mock_db.collection.return_value = mock_query

        with patch("tools.knowledge_tools.get_client", return_value=mock_db):
            from tools.knowledge_tools import search_docs
            result = search_docs(query="gearbox vibration")

        assert result["success"] is True
        assert result["count"] >= 1
        assert result["documents"][0]["doc_id"] == "DOC-001"

    def test_returns_snippet_not_full_content(self):
        long_content = "x" * 500
        docs = [
            {"doc_id": "DOC-001", "title": "Long doc", "category": "sop",
             "content": long_content, "tags": ["xxx"],
             "related_fault_type": ""},
        ]
        mock_db = MagicMock()
        mock_query = make_query_result(docs)
        mock_db.collection.return_value = mock_query

        with patch("tools.knowledge_tools.get_client", return_value=mock_db):
            from tools.knowledge_tools import search_docs
            result = search_docs(query="xxx")

        assert len(result["documents"][0]["snippet"]) <= 203  # 200 + "..."

    def test_returns_empty_when_no_match(self):
        docs = [
            {"doc_id": "DOC-001", "title": "Gearbox SOP", "category": "sop",
             "content": "gearbox content", "tags": ["gearbox"],
             "related_fault_type": "gearbox"},
        ]
        mock_db = MagicMock()
        mock_query = make_query_result(docs)
        mock_db.collection.return_value = mock_query

        with patch("tools.knowledge_tools.get_client", return_value=mock_db):
            from tools.knowledge_tools import search_docs
            result = search_docs(query="blade pitch yaw")

        assert result["count"] == 0


class TestAddNote:

    def test_saves_field_note(self):
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.knowledge_tools.get_client", return_value=mock_db), \
             patch("tools.knowledge_tools.add_audit_log"):
            from tools.knowledge_tools import add_note
            result = add_note(
                title="T-012 blade tip erosion",
                content="Minor erosion on blade 2 leading edge, spotted during morning inspection",
                related_turbine_id="T-012",
                related_fault_type="blade",
                tags=["erosion", "blade"],
                created_by="Arjun Patel",
            )

        assert result["success"] is True
        assert "doc_id" in result
        assert result["document"]["category"] == "field_note"
        assert result["document"]["related_turbine_id"] == "T-012"
        mock_ref.set.assert_called_once()


class TestGetDoc:

    def test_retrieves_existing_doc(self):
        doc_data = {"doc_id": "DOC-001", "title": "SOP: Gearbox", "content": "Full content here"}
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_ref.get.return_value = make_doc(doc_data)
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.knowledge_tools.get_client", return_value=mock_db):
            from tools.knowledge_tools import get_doc
            result = get_doc("DOC-001")

        assert result["success"] is True
        assert result["document"]["doc_id"] == "DOC-001"

    def test_returns_error_for_missing_doc(self):
        mock_db = MagicMock()
        mock_ref = MagicMock()
        mock_ref.get.return_value.exists = False
        mock_db.collection.return_value.document.return_value = mock_ref

        with patch("tools.knowledge_tools.get_client", return_value=mock_db):
            from tools.knowledge_tools import get_doc
            result = get_doc("DOC-999")

        assert result["success"] is False
        assert "DOC-999" in result["error"]
