"""
WindOps — root orchestrator agent.
"""

import os
from datetime import date
from dotenv import load_dotenv
load_dotenv()

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StreamableHTTPConnectionParams

from tools.task_tools import create_task, list_tasks, update_task
from tools.schedule_tools import get_schedule, add_shift, check_conflicts

task_agent = LlmAgent(
    name="task_agent",
    model="gemini-2.5-flash",
    description="Creates, lists, and updates maintenance tasks for turbines T-001 to T-015.",
    instruction="""You are the Task Agent for a wind farm operations team.
Manage maintenance work orders for 15 wind turbines (T-001 to T-015).
Priority: P1 (safety-critical), P2 (performance), P3 (routine).
Status: open, in_progress, completed, blocked.
When creating tasks confirm turbine_id and priority. Flag P1 as URGENT and safety-critical.
When listing tasks default to open tasks sorted by priority (P1 first).
Always use exact turbine IDs (T-001 format).
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
Always use YYYY-MM-DD format. Always use T-001 format for turbine IDs.
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
When searching return title, category, snippet, and doc_id.
When adding field notes confirm the doc_id in your response.
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

root_agent = LlmAgent(
    name="windops_coordinator",
    model="gemini-2.5-flash",
    description="WindOps: multi-agent assistant for wind farm operations.",
    instruction=f"""You are WindOps, a productivity assistant for wind farm operations teams.
Today's date is {date.today().isoformat()}.

You coordinate three specialist agents:
- task_agent: create, list, update maintenance tasks
- schedule_agent: shifts, scheduling, weekly planning, conflicts
- knowledge_agent: SOPs, manuals, field notes

Route to exactly one agent per request:
- Turbine fault or sensor alert → knowledge_agent first to get SOP, then task_agent to check open tasks, combine both in your response
- Create/list/update tasks → task_agent
- Shifts, scheduling, weekly planning → schedule_agent
- Add field note or search SOPs → knowledge_agent

Always use turbine IDs T-001 to T-015.
Technician names: Rajesh Kumar, Mei Chen, Arjun Patel, Priya Sharma.
Flag P1 tasks as URGENT in every response.
""",
    sub_agents=[task_agent, schedule_agent, knowledge_agent],
)
