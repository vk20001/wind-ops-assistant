#!/bin/bash
set -e

echo "Starting Knowledge MCP Server on port 8001..."
python /app/mcp_server/knowledge_mcp_server.py &

echo "Waiting for MCP server to be ready..."
for i in $(seq 1 20); do
    if curl -s http://localhost:8001/ > /dev/null 2>&1; then
        echo "MCP server ready."
        break
    fi
    echo "Attempt $i/20 — waiting 2s..."
    sleep 2
done

echo "Starting ADK API server on port 8080..."
exec adk api_server --host 0.0.0.0 --port 8080 /app
