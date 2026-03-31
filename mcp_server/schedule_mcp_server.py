"""
Schedule MCP Server — exposes get_schedule, add_shift, check_conflicts as MCP tools.
Runs on port 8003.
"""
import sys
import os

os.environ["FASTMCP_PORT"] = "8003"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from tools.schedule_tools import get_schedule, add_shift, check_conflicts, get_availability, swap_shifts, delete_shift

mcp = FastMCP("WindOps Schedule MCP Server")

mcp.tool()(get_schedule)
mcp.tool()(add_shift)
mcp.tool()(check_conflicts)
mcp.tool()(get_availability)
mcp.tool()(swap_shifts)
mcp.tool()(delete_shift)

if __name__ == "__main__":
    mcp.run(transport="http")
