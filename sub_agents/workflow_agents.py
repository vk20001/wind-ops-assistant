"""
Workflow agents — production patterns for wind farm operations.

Design decisions:
- SequentialAgent for triage: each step has side effects (create alert, create task)
  that the next step depends on. Audit trail is required for safety-critical procedures.
- LoopAgent for escalation: retry pattern until condition is met.
- Single LlmAgent for handover/planner/briefing: these aggregate independent data
  sources into one consolidated report. No side effects, no step dependencies.
  A single agent with multi-server tool access produces cleaner output.
"""

from datetime import date

from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams


# ---------------------------------------------------------------------------
# MCP connection factories
# ---------------------------------------------------------------------------

def _task_mcp():
    return MCPToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8002/mcp"))

def _schedule_mcp():
    return MCPToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8003/mcp"))

def _knowledge_mcp():
    return MCPToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8001/mcp"))

def _analytics_mcp():
    return MCPToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8004/mcp"))

def _alert_mcp():
    return MCPToolset(connection_params=StreamableHTTPConnectionParams(url="http://localhost:8005/mcp"))


# ===========================================================================================
# 1. TRIAGE WORKFLOW (SequentialAgent)
#
# WHY SEQUENTIAL: Each step has side effects the next step depends on.
#   Step 1 creates an alert → Step 2 uses the fault type to find the SOP →
#   Step 3 creates a task based on the SOP → Step 4 assigns based on the task.
# This is a safety-critical procedure. The sequential audit trail is required
# so operations managers can review exactly what happened at each stage.
# ===========================================================================================

triage_step1_alert = LlmAgent(
    name="triage_step1_alert",
    model="gemini-2.5-flash",
    description="Step 1: Check existing alerts and create one if needed.",
    output_key="triage_alert_result",
    instruction="""You are step 1 of a fault triage procedure.
A fault has been reported. Your job:
1. Use list_alerts to check if an active alert already exists for this turbine.
2. If no alert exists, use create_alert with the appropriate type and severity.
3. Summarize: alert status (new or existing), alert_id, severity, turbine_id, fault_type.
Keep your response factual and brief. The next agent needs the turbine_id, fault_type, and alert severity.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_alert_mcp()],
)

triage_step2_knowledge = LlmAgent(
    name="triage_step2_knowledge",
    model="gemini-2.5-flash",
    description="Step 2: Retrieve relevant SOP for the fault type.",
    output_key="triage_sop_result",
    instruction="""You are step 2 of a fault triage procedure.
An alert has been created or confirmed in the previous step. Your job:
1. Use search_docs to find the SOP for the fault type mentioned in the previous step.
2. If found, use get_doc to retrieve the full procedure.
3. Summarize only the key action steps from the SOP.
Do not repeat information from step 1. Only output SOP content.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_knowledge_mcp()],
)

triage_step3_task = LlmAgent(
    name="triage_step3_task",
    model="gemini-2.5-flash",
    description="Step 3: Check or create a maintenance task.",
    output_key="triage_task_result",
    instruction="""You are step 3 of a fault triage procedure.
An alert exists and an SOP has been retrieved. Your job:
1. Use list_tasks to check if an open task already exists for this turbine and fault type.
2. If no task exists, use create_task with priority matching the alert severity (critical/high=P1, medium=P2, low=P3).
3. Output only: task_id, priority, turbine_id, assigned technician (if any).
Do not repeat alert or SOP information from previous steps.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_task_mcp()],
)

triage_step4_schedule = LlmAgent(
    name="triage_step4_schedule",
    model="gemini-2.5-flash",
    description="Step 4: Find available technician for the task.",
    output_key="triage_schedule_result",
    instruction=f"""You are step 4 of a fault triage procedure. Today is {date.today().isoformat()}.
A task has been created or confirmed. Your job:
1. Use get_availability for today to find who is free.
2. Recommend the best available technician for this task.
3. Output only: recommended technician, their available shift, and reasoning.
Do not repeat alert, SOP, or task information from previous steps.
End with a clear one-line recommendation.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_schedule_mcp()],
)

triage_workflow = SequentialAgent(
    name="triage_workflow",
    description="Full fault triage: alert → SOP lookup → task creation → technician assignment. Use when a new fault or sensor anomaly is reported.",
    sub_agents=[triage_step1_alert, triage_step2_knowledge, triage_step3_task, triage_step4_schedule],
)


# ===========================================================================================
# 2. WEEKLY PLANNER (Single LlmAgent with multi-server tools)
#
# WHY SINGLE AGENT: Weekly planning aggregates independent data (schedule, tasks, workloads)
# into one plan. No step creates data the next step needs. A single agent with access to
# schedule, task, and analytics tools produces one consolidated plan without duplication.
# ===========================================================================================

weekly_planner = LlmAgent(
    name="weekly_planner",
    model="gemini-2.5-flash",
    description="Weekly maintenance planner: analyzes schedule, tasks, and workloads to produce a maintenance plan. Use for 'plan my week' or 'weekly maintenance plan'.",
    output_key="weekly_plan_result",
    instruction=f"""You are the weekly maintenance planner for a wind farm operations team.
Today is {date.today().isoformat()}.

Produce a weekly maintenance plan by following these steps in order:

1. Get this week's shift schedule using get_schedule with week_of='{date.today().isoformat()}'.
2. Get all open tasks using list_tasks with status='open'.
3. Check technician workloads using technician_workload.
4. Based on all three data sources, produce a maintenance plan:
   - Assign P1 tasks first to the least loaded available technicians
   - Then P2, then P3
   - Flag any overloaded technicians
   - Present as a day-by-day plan

Output one consolidated weekly plan. Do not output intermediate results.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_schedule_mcp(), _task_mcp(), _analytics_mcp()],
)


# ===========================================================================================
# 3. SHIFT HANDOVER (Single LlmAgent with multi-server tools)
#
# WHY SINGLE AGENT: A handover is one consolidated briefing, not three separate reports.
# The person writing a handover decides what's relevant across tasks, notes, and alerts
# and presents it as a single narrative. No side effects, no step dependencies.
# ===========================================================================================

shift_handover = LlmAgent(
    name="shift_handover",
    model="gemini-2.5-flash",
    description="Shift handover: consolidated summary of tasks, field notes, and alerts for the incoming shift. Use for 'shift handover' or 'end of shift report'.",
    output_key="handover_result",
    instruction="""You are preparing a shift handover briefing for the incoming shift.

Gather data from three sources, then produce ONE consolidated handover report:

1. Use list_tasks with status='in_progress' to find tasks being worked on.
   Then use list_tasks with status='completed' to find recently completed tasks.
2. Use list_recent_notes to get recent field observations.
3. Use list_alerts with status='open' to find unacknowledged alerts.

Then produce a single handover report with these sections:
- **Tasks**: what is in progress, what was completed
- **Field Notes**: any observations the incoming shift should know about, especially safety concerns
- **Open Alerts**: any unacknowledged alerts, with critical/high flagged prominently

End with: 'Handover complete. Incoming shift is briefed.'

Output one consolidated report. Do not output intermediate results after each tool call.
Call each tool exactly once per filter. Do not repeat tool calls.""",
    tools=[_task_mcp(), _knowledge_mcp(), _alert_mcp()],
)


# ===========================================================================================
# 4. ESCALATION LOOP (LoopAgent)
#
# WHY LOOP: The escalation check repeats until all critical alerts are acknowledged.
# This models real SCADA alarm behavior: the system keeps alerting until someone responds.
# max_iterations prevents infinite loops in case alerts can't be resolved.
# ===========================================================================================

escalation_checker = LlmAgent(
    name="escalation_checker",
    model="gemini-2.5-flash",
    description="Check for unacknowledged critical alerts and escalate them.",
    output_key="escalation_check_result",
    instruction="""You check for unacknowledged critical alerts.
1. Use list_alerts with status='open' and severity='critical'.
2. If any are found, use escalate_alert to escalate each one to 'Operations Manager' with reason 'Unacknowledged critical alert requires immediate attention'.
3. Report what you found and what was escalated.
4. If no unacknowledged critical alerts remain, say 'All critical alerts have been acknowledged. Escalation check complete.' and stop.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_alert_mcp()],
)

escalation_loop = LoopAgent(
    name="escalation_loop",
    description="Escalation loop: repeatedly checks for unacknowledged critical alerts and escalates them. Use for 'check escalations' or 'run escalation check'.",
    sub_agents=[escalation_checker],
    max_iterations=3,
)


# ===========================================================================================
# 5. MORNING BRIEFING (Single LlmAgent with multi-server tools)
#
# WHY SINGLE AGENT: A morning briefing is one document, not four separate reports.
# An operations manager reads one page, not four tabs. A single agent with access
# to all data sources produces the format that matches how briefings actually work.
# ===========================================================================================

parallel_morning_briefing = LlmAgent(
    name="parallel_morning_briefing",
    model="gemini-2.5-flash",
    description="Morning briefing: consolidated farm status, tasks, schedule, and alerts. Use for 'morning briefing' or 'daily briefing'.",
    output_key="morning_briefing_result",
    instruction=f"""You are preparing the daily morning briefing for the wind farm operations team.
Today is {date.today().isoformat()}.

Gather data from four sources, then produce ONE consolidated briefing:

1. Use farm_overview to get turbine health status.
2. Use get_task_stats to get the task summary.
3. Use get_schedule with date='{date.today().isoformat()}' to get today's shifts.
4. Use list_alerts with status='open' to get current alerts.

Then produce a single morning briefing with these sections:
- **Farm Health**: how many turbines critical/attention/healthy, list critical ones by ID
- **Open Tasks**: total count by priority, list any P1 tasks with turbine and assignee
- **Today's Schedule**: who is on which shift, which turbines they cover
- **Alerts**: total open, list critical and high severity alerts

Keep each section brief. This is a one-page briefing, not a detailed report.
Output one consolidated briefing. Do not output intermediate results after each tool call.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_analytics_mcp(), _task_mcp(), _schedule_mcp(), _alert_mcp()],
)

# ===========================================================================================
# 6. TURBINE SITUATION REPORT (Single LlmAgent with all 5 MCP servers)
#
# WHY THIS EXISTS: The most impressive demo query. "Full situation report on T-007"
# pulls health data, open tasks, alerts, SOPs, field notes, and schedule info for one
# turbine into a single consolidated report. Shows all 5 agents working together.
# ===========================================================================================

turbine_situation_report = LlmAgent(
    name="turbine_situation_report",
    model="gemini-2.5-flash",
    description="Full cross-agent situation report for a single turbine. Use for 'full situation report on T-XXX' or 'what is the complete status of T-XXX'.",
    output_key="situation_report_result",
    instruction=f"""You produce a comprehensive situation report for a single wind turbine.
Today is {date.today().isoformat()}.

When given a turbine ID, gather data from ALL available sources:

1. Use turbine_health_summary to get the overall health status, open tasks, and active alerts.
2. Use search_by_turbine to find all SOPs, field notes, and documents related to this turbine.
3. Use list_alerts filtered by this turbine to get detailed alert information.
4. Use get_schedule with date='{date.today().isoformat()}' to find which technician covers this turbine today.
5. Use technician_workload to check the assigned technician's current load.

Then produce ONE comprehensive situation report with these sections:

- **Turbine Status**: CRITICAL / NEEDS ATTENTION / HEALTHY with reasoning
- **Active Alerts**: list with severity, type, and current status (open/acknowledged/escalated)
- **Open Tasks**: list with priority, assignee, and description
- **Relevant Documentation**: SOPs and field notes related to this turbine's current issues
- **Assigned Personnel**: who covers this turbine today, their shift, and their current workload
- **Recommended Actions**: prioritized list of what should happen next based on all the data

This is an executive summary. Be thorough but structured.
Call each tool exactly once. Do not repeat tool calls.""",
    tools=[_analytics_mcp(), _knowledge_mcp(), _alert_mcp(), _schedule_mcp(), _task_mcp()],
)