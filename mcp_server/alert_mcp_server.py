"""
Alert MCP Server — exposes create_alert, list_alerts, acknowledge_alert, escalate_alert.
Runs on port 8005.
"""
import sys
import os

os.environ["FASTMCP_PORT"] = "8005"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from tools.alert_tools import create_alert, list_alerts, acknowledge_alert, escalate_alert, resolve_alert

mcp = FastMCP("WindOps Alert MCP Server")

mcp.tool()(create_alert)
mcp.tool()(list_alerts)
mcp.tool()(acknowledge_alert)
mcp.tool()(escalate_alert)
mcp.tool()(resolve_alert)

if __name__ == "__main__":
    mcp.run(transport="http")