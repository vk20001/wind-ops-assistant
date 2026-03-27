"""
Knowledge MCP Server — exposes search_docs, add_note, get_doc as MCP tools.
Runs as a subprocess on port 8001 (localhost only, same container as ADK server).
"""
import sys
import os

# Works both locally (~/wind-ops-assistant) and in container (/app)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastmcp import FastMCP
from tools.knowledge_tools import search_docs, add_note, get_doc

mcp = FastMCP("WindOps Knowledge MCP Server")

mcp.tool()(search_docs)
mcp.tool()(add_note)
mcp.tool()(get_doc)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", port=8001)
