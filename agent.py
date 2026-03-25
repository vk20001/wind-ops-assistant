"""
WindOps — root orchestrator agent.
"""

import os
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import FunctionTool

from tools.task_tools import create_task, list_tasks, update_task
from tools.schedule_tools import get_schedule, add_shift, check_conflicts
from tools.knowledge_tools import search_docs, add_note, get_doc

# Standalone agents for direct requests
task_agent = LlmAgent(
    name="task_agent",
    model="gemini-2.5-flash",
    description="Creates, lists, and updates maintenance tasks for turbines T-001 to T-015.",
    instruction="""You are the Task Agent for a wind farm operations team.
Manage maintenance work orders for 15 wind turbines (T-001 to T-015).
Priority: P1 (safety-critical), P2 (performance), P3 (routine).
Status: open, in_progress, completed, blocked.
When creating tasks confirm turbine_id and priority. Flag P1 as safety-critical.
When listing tasks default to open tasks sorted by priority (P1 first).
""",
    tools=[FunctionTool(create_task), FunctionTool(list_tasks), FunctionTool(update_task)],
)

schedule_agent = LlmAgent(
    name="schedule_agent",
    model="gemini-2.5-flash",
    description="Manages technician shifts and maintenance windows.",
    instruction=f"""Today's date is {date.today().isoformat()}. When user says 'this week' use week_of='{date.today().isoformat()}'.
You are the Schedule Agent for a wind farm operations team.
Shift types: morning (06:00-14:00), afternoon (14:00-22:00), night (22:00-06:00).
Always use YYYY-MM-DD date format. Always use T-001 format for turbine IDs.
Show shifts grouped by date. Flag maintenance windows clearly.
""",
    tools=[FunctionTool(get_schedule), FunctionTool(add_shift), FunctionTool(check_conflicts)],
)

knowledge_agent = LlmAgent(
    name="knowledge_agent",
    model="gemini-2.5-flash",
    description="Retrieves SOPs, manuals, safety bulletins. Saves field notes.",
    instruction="""You are the Knowledge Agent for a wind farm operations team.
Categories: sop, manual, field_note, safety_bulletin.
When searching return title, category, snippet, doc_id.
When adding field notes confirm the doc_id in your response.
""",
    tools=[FunctionTool(search_docs), FunctionTool(add_note), FunctionTool(get_doc)],
)

# Separate instances for the triage sequential flow
triage_knowledge_agent = LlmAgent(
    name="triage_knowledge_agent",
    model="gemini-2.5-flash",
    description="Fetches SOP for a turbine fault.",
    instruction="""You are the Knowledge Agent handling a turbine fault triage.
Search for the most relevant SOP based on the fault type mentioned.
Return the SOP title, snippet, and doc_id clearly.
""",
    tools=[FunctionTool(search_docs), FunctionTool(get_doc)],
)

triage_task_agent = LlmAgent(
    name="triage_task_agent",
    model="gemini-2.5-flash",
    description="Checks open tasks for a turbine during fault triage.",
    instruction="""You are the Task Agent handling a turbine fault triage.
List all open tasks for the turbine mentioned in the conversation.
If a P1 task exists, flag it as URGENT and safety-critical.
If no open tasks exist, state that clearly.
""",
    tools=[FunctionTool(list_tasks), FunctionTool(create_task)],
)

# Sequential triage pipeline
fault_triage_agent = SequentialAgent(
    name="fault_triage_agent",
    description="Handles turbine fault alerts. Fetches SOP then checks open tasks.",
    sub_agents=[triage_knowledge_agent, triage_task_agent],
)

root_agent = LlmAgent(
    name="windops_coordinator",
    model="gemini-2.5-flash",
    description="WindOps: multi-agent assistant for wind farm operations.",
    instruction=f"""You are WindOps, a productivity assistant for wind farm operations teams.
Today's date is {date.today().isoformat()}.

Route to exactly one agent per request:

- fault_triage_agent: ANY turbine fault or sensor alert ("T-007 gearbox vibration high", "what should I do about T-003")
- task_agent: create, list, or update tasks (no fault context)
- schedule_agent: shifts, scheduling, weekly planning, conflicts
- knowledge_agent: add field notes, search SOPs without a fault context

Always use turbine IDs T-001 to T-015.
Technician names: Rajesh Kumar, Mei Chen, Arjun Patel, Priya Sharma.
Flag P1 tasks as URGENT in every response.
""",
    sub_agents=[fault_triage_agent, task_agent, schedule_agent, knowledge_agent],
)