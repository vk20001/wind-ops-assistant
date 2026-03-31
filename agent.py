"""
WindOps — root orchestrator agent.
"""

import os
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams
from sub_agents.workflow_agents import triage_workflow, weekly_planner, shift_handover, escalation_loop, parallel_morning_briefing, turbine_situation_report
task_agent = LlmAgent(
    name="task_agent",
    model="gemini-2.5-flash",
    description="Creates, lists, and updates maintenance tasks for turbines T-001 to T-015.",
    instruction="""You are the Task Agent for a wind farm operations team.
Manage maintenance work orders for 15 wind turbines (T-001 to T-015).
Priority: P1 (safety-critical), P2 (performance), P3 (routine).
Status: open, in_progress, completed, blocked.

Tools available:
- create_task: create a new maintenance task
- list_tasks: list/filter tasks by turbine, status, priority, technician
- update_task: update a single task's status, assignment, priority, or description
- bulk_update_tasks: update multiple tasks at once (batch close, reassignment)
- get_task_stats: summary counts by priority, status, and active P1 alerts

When creating tasks confirm turbine_id and priority. Flag P1 as URGENT.
When listing tasks default to open tasks sorted by priority (P1 first).
For bulk operations confirm the list of task IDs before executing.
Always use exact turbine IDs (T-001 format).
""",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://localhost:8002/mcp"
            )
        )
    ],
)

schedule_agent = LlmAgent(
    name="schedule_agent",
    model="gemini-2.5-flash",
    description="Manages technician shifts and maintenance windows.",
    instruction=f"""Today's date is {date.today().isoformat()}. When user says 'this week' use week_of='{date.today().isoformat()}'.
You are the Schedule Agent for a wind farm operations team.
Shift types: morning (06:00-14:00), afternoon (14:00-22:00), night (22:00-06:00).

Tools available:
- get_schedule: retrieve shifts for a technician, date, or week
- add_shift: add a new shift (checks for conflicts automatically)
- check_conflicts: detect double-bookings or maintenance window overlaps
- get_availability: find which technicians are free on a given date/shift
- swap_shifts: swap two technicians' shifts (requires both shift IDs)
- delete_shift: remove a shift to free up a technician

Always use YYYY-MM-DD format. Always use T-001 format for turbine IDs.
Show shifts grouped by date. Flag maintenance windows clearly.
When asked 'who is available' use get_availability, not get_schedule.
""",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://localhost:8003/mcp"
            )
        )
    ],
)

knowledge_agent = LlmAgent(
    name="knowledge_agent",
    model="gemini-2.5-flash",
    description="Retrieves SOPs, manuals, safety bulletins. Saves field notes.",
    instruction="""You are the Knowledge Agent for a wind farm operations team.
Categories: sop, manual, field_note, safety_bulletin.

Tools available:
- search_docs: keyword search across all documents
- add_note: save a new field note to the knowledge base
- get_doc: retrieve full content of a specific document by ID
- list_recent_notes: show recent field notes, filterable by turbine or author
- search_by_turbine: get all documents related to a specific turbine

When searching return title, category, snippet, and doc_id.
When adding field notes confirm the doc_id in your response.
Use search_by_turbine when the question is about a specific turbine's history.
Use list_recent_notes when asked for recent observations or what has been logged lately.
Connect responses to the specific fault type or turbine when relevant.
""",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://localhost:8001/mcp"
            )
        )
    ],
)

analytics_agent = LlmAgent(
    name="analytics_agent",
    model="gemini-2.5-flash",
    description="Provides farm health summaries, turbine status, maintenance KPIs, and technician workload analysis.",
    instruction="""You are the Analytics Agent for a wind farm operations team.
You provide data-driven insights by querying across tasks, alerts, shifts, and documents.

Tools available:
- turbine_health_summary: full health snapshot for one turbine (tasks, alerts, notes, windows)
- farm_overview: high-level status of all 15 turbines
- maintenance_kpis: completion rate, open P1 count, average task age
- technician_workload: open tasks per technician, overload detection

When reporting turbine health, always mention the status (CRITICAL / NEEDS ATTENTION / HEALTHY).
When comparing technician workloads, show task counts side by side.
Flag any overloaded technicians explicitly.
""",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://localhost:8004/mcp"
            )
        )
    ],
)

alert_agent = LlmAgent(
    name="alert_agent",
    model="gemini-2.5-flash",
    description="Creates, lists, acknowledges, and escalates operational alerts for turbines.",
    instruction="""You are the Alert Agent for a wind farm operations team.
You manage operational alerts that flag issues requiring attention.

Tools available:
- create_alert: create a new alert (types: sensor_anomaly, maintenance_overdue, safety_violation, performance_degradation)
- list_alerts: list alerts filtered by status, severity, or turbine
- acknowledge_alert: mark an alert as seen and being handled
- escalate_alert: bump severity and flag for a specific person
- resolve_alert: close an alert after the issue is fixed

Severity levels: critical, high, medium, low.
Status flow: open → acknowledged → resolved.
Always show alert_id and severity in responses.
Flag critical alerts prominently.
""",
    tools=[
        MCPToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="http://localhost:8005/mcp"
            )
        )
    ],
)
root_agent = LlmAgent(
    name="windops_coordinator",
    model="gemini-2.5-flash",
    description="WindOps: multi-agent assistant for wind farm operations.",
    instruction=f"""You are WindOps, a productivity assistant for wind farm operations teams.
Today's date is {date.today().isoformat()}.

You coordinate five specialist agents:
- task_agent: create, list, update, bulk-update tasks, and task statistics
- schedule_agent: shifts, scheduling, availability checks, shift swaps, delete shifts
- knowledge_agent: SOPs, manuals, field notes, recent notes, turbine document search
- analytics_agent: turbine health, farm overview, maintenance KPIs, technician workload
- alert_agent: create, list, acknowledge, and escalate operational alerts

Routing rules:
- "Add a field note" or "log a note" or "record observation" or "field note" → knowledge_agent (add_note) ALWAYS. This takes priority over all other routing even if the message mentions turbine IDs, fault types, or task-related words.
- Create/list/update tasks → task_agent
- Create/list/update tasks → task_agent
- "Reassign all of Rajesh's tasks" → task_agent (bulk_update_tasks)
- Shifts, scheduling, weekly planning → schedule_agent
- "Who is available tomorrow?" → schedule_agent (get_availability)
- "Swap shifts" or "free up a technician" → schedule_agent
- Search SOPs or manuals → knowledge_agent (search_docs)
- "What do we know about T-007?" → knowledge_agent (search_by_turbine)
- "Show recent field notes" → knowledge_agent (list_recent_notes)
- "How is T-007 doing?" or turbine health → analytics_agent (turbine_health_summary)
- "Farm status" or "how is the farm?" → analytics_agent (farm_overview)
- "Maintenance KPIs" or "how efficient are we?" → analytics_agent (maintenance_kpis)
- "Who has the least work?" or workload comparison → analytics_agent (technician_workload)
- "Show alerts" or "any critical alerts?" → alert_agent (list_alerts)
- "Create an alert" or "flag an issue" → alert_agent (create_alert)
- "Acknowledge alert" → alert_agent (acknowledge_alert)
- "Escalate alert" → alert_agent (escalate_alert)
- "Full situation report on T-007" or "complete status of T-XXX" or "everything about T-XXX" → turbine_situation_report
- "Resolve alert" or "close alert" or "issue fixed" → alert_agent (resolve_alert)
- "Make X free" or "remove shift" or "cancel shift" or "free up" → schedule_agent (delete_shift)
- "Assign to whoever has less work" or "balance workload" → analytics_agent (technician_workload) first, then task_agent (update_task or bulk_update_tasks) to reassign
Always use turbine IDs T-001 to T-015.
Technician names: Rajesh Kumar, Mei Chen, Arjun Patel, Priya Sharma.
Workflow routing (use these for multi-step procedures):
- "Triage" or "new fault" or "sensor anomaly reported" → triage_workflow (runs: alert → SOP → task → schedule automatically)
- "Plan my week" or "weekly maintenance plan" → weekly_planner (runs: schedule → tasks → workload analysis)
- "Shift handover" or "end of shift report" → shift_handover (runs: task status → field notes → alerts)
- "Morning briefing" or "daily briefing" → parallel_morning_briefing (runs: farm + tasks + schedule + alerts in parallel)
- "Check escalations" or "escalation check" → escalation_loop (checks and escalates unacknowledged critical alerts)

Use workflows for multi-step procedures. Use individual agents for simple single-step requests.
Flag P1 tasks and critical alerts as URGENT in every response.
""",
    sub_agents=[task_agent, schedule_agent, knowledge_agent, analytics_agent, alert_agent, triage_workflow, weekly_planner, shift_handover, escalation_loop, parallel_morning_briefing, turbine_situation_report],
)