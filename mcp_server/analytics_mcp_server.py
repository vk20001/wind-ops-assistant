"""
Analytics MCP Server — exposes turbine_health_summary, farm_overview, maintenance_kpis, technician_workload.
Runs on port 8004.
"""
import sys
import os

os.environ["FASTMCP_PORT"] = "8004"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from tools.analytics_tools import turbine_health_summary, farm_overview, maintenance_kpis, technician_workload

mcp = FastMCP("WindOps Analytics MCP Server")

mcp.tool()(turbine_health_summary)
mcp.tool()(farm_overview)
mcp.tool()(maintenance_kpis)
mcp.tool()(technician_workload)

if __name__ == "__main__":
    mcp.run(transport="http")