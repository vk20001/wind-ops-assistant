#!/bin/bash
set -e
echo "Starting Knowledge MCP Server on port 8001..."
python /agents/wind_ops_assistant/mcp_server/knowledge_mcp_server.py &
echo "Starting Task MCP Server on port 8002..."
python /agents/wind_ops_assistant/mcp_server/task_mcp_server.py &
echo "Starting Schedule MCP Server on port 8003..."
python /agents/wind_ops_assistant/mcp_server/schedule_mcp_server.py &
echo "Starting Analytics MCP Server on port 8004..."
python /agents/wind_ops_assistant/mcp_server/analytics_mcp_server.py &
echo "Starting Alert MCP Server on port 8005..."
python /agents/wind_ops_assistant/mcp_server/alert_mcp_server.py &
echo "Waiting for MCP servers to be ready..."
for port in 8001 8002 8003 8004 8005; do
    for i in $(seq 1 20); do
        if curl -s http://localhost:$port/ > /dev/null 2>&1; then
            echo "Port $port ready."
            break
        fi
        if [ "$i" -eq 20 ]; then
            echo "ERROR: Port $port not ready after 40s. Exiting."
            exit 1
        fi
        echo "Port $port attempt $i/20 — waiting 2s..."
        sleep 2
    done
done
echo "All MCP servers ready. Starting ADK Web server on port 8081..."
adk web --host 0.0.0.0 --port 8081 --allow_origins "*" /agents &
echo "Waiting for ADK to be ready on port 8081..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8081/dev-ui/ > /dev/null 2>&1; then
        echo "ADK ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: ADK not ready after 60s. Exiting."
        exit 1
    fi
    echo "ADK attempt $i/30 — waiting 2s..."
    sleep 2
done
echo "Starting nginx on port 8080..."
exec nginx -c /agents/wind_ops_assistant/nginx.conf -g "daemon off;"
