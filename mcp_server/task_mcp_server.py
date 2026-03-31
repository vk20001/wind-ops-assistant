"""
Task MCP Server — exposes create_task, list_tasks, update_task as MCP tools.
Runs on port 8002.
"""
import sys
import os

os.environ["FASTMCP_PORT"] = "8002"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from tools.task_tools import create_task, list_tasks, update_task, bulk_update_tasks, get_task_stats

mcp = FastMCP("WindOps Task MCP Server")

mcp.tool()(create_task)
mcp.tool()(list_tasks)
mcp.tool()(update_task)
mcp.tool()(bulk_update_tasks)
mcp.tool()(get_task_stats)

if __name__ == "__main__":
    mcp.run(transport="http")
