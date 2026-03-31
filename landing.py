import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

app = FastAPI()

ADK_BASE = "http://localhost:8081"

LANDING_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>WindOps — Wind Farm Operations Assistant</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #0a0f1e; color: #e2e8f0; min-height: 100vh; }
  .hero { padding: 80px 40px 60px; max-width: 900px; margin: 0 auto; text-align: center; }
  .badge { display: inline-block; background: #1a3a5c; color: #60a5fa; padding: 6px 16px; border-radius: 20px; font-size: 13px; letter-spacing: 0.05em; margin-bottom: 32px; border: 1px solid #2563eb44; }
  h1 { font-size: 3rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #34d399); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin-bottom: 16px; }
  .subtitle { font-size: 1.2rem; color: #94a3b8; max-width: 600px; margin: 0 auto 48px; line-height: 1.6; }
  .cta { display: inline-block; background: linear-gradient(135deg, #2563eb, #059669); color: white; padding: 16px 40px; border-radius: 8px; font-size: 1.1rem; font-weight: 600; text-decoration: none; transition: opacity 0.2s; }
  .cta:hover { opacity: 0.85; }
  .arch { max-width: 900px; margin: 60px auto; padding: 0 40px; }
  .arch h2 { font-size: 1.4rem; color: #60a5fa; margin-bottom: 32px; text-align: center; }
  .agents { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px; margin-bottom: 40px; }
  .agent-card { background: #111827; border: 1px solid #1e3a5f; border-radius: 10px; padding: 20px 16px; text-align: center; }
  .agent-card .icon { font-size: 1.8rem; margin-bottom: 10px; }
  .agent-card .name { font-size: 0.85rem; font-weight: 600; color: #60a5fa; margin-bottom: 6px; }
  .agent-card .desc { font-size: 0.75rem; color: #64748b; line-height: 1.4; }
  .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 16px; max-width: 900px; margin: 0 auto 60px; padding: 0 40px; }
  .stat { background: #111827; border: 1px solid #1e3a5f; border-radius: 10px; padding: 24px 16px; text-align: center; }
  .stat .number { font-size: 2rem; font-weight: 700; color: #34d399; }
  .stat .label { font-size: 0.8rem; color: #64748b; margin-top: 4px; }
  .apac { background: #0f1f38; border: 1px solid #1e3a5f; border-radius: 12px; max-width: 900px; margin: 0 auto 60px; padding: 32px 40px; }
  .apac h3 { color: #60a5fa; margin-bottom: 12px; }
  .apac p { color: #94a3b8; line-height: 1.7; font-size: 0.95rem; }
  footer { text-align: center; padding: 32px; color: #334155; font-size: 0.85rem; border-top: 1px solid #1e293b; }
</style>
</head>
<body>
<div class="hero">
  <div class="badge">Gen AI Academy APAC — Cohort 1</div>
  <h1>WindOps Assistant</h1>
  <p class="subtitle">A multi-agent AI system for wind farm operations — handling maintenance tasks, technician scheduling, anomaly alerts, and operational analytics across 15 turbines.</p>
  <a href="/dev-ui/?app=wind_ops_assistant" target="_self" class="cta">Launch WindOps Chat →</a>
</div>

<div class="arch">
  <h2>Agent Architecture</h2>
  <div class="agents">
    <div class="agent-card"><div class="icon">🎯</div><div class="name">Coordinator</div><div class="desc">Routes all requests to the right specialist agent</div></div>
    <div class="agent-card"><div class="icon">🔧</div><div class="name">Task Agent</div><div class="desc">Creates and tracks maintenance work orders P1–P3</div></div>
    <div class="agent-card"><div class="icon">📅</div><div class="name">Schedule Agent</div><div class="desc">Manages technician shifts and maintenance windows</div></div>
    <div class="agent-card"><div class="icon">📚</div><div class="name">Knowledge Agent</div><div class="desc">Stores and retrieves field notes and fault reports</div></div>
    <div class="agent-card"><div class="icon">📊</div><div class="name">Analytics Agent</div><div class="desc">Turbine health, KPIs, and technician workload</div></div>
    <div class="agent-card"><div class="icon">🚨</div><div class="name">Alert Agent</div><div class="desc">Creates, acknowledges, and escalates fault alerts</div></div>
  </div>
</div>

<div class="stats">
  <div class="stat"><div class="number">15</div><div class="label">Turbines Monitored</div></div>
  <div class="stat"><div class="number">25</div><div class="label">Tools Available</div></div>
  <div class="stat"><div class="number">5</div><div class="label">MCP Servers</div></div>
  <div class="stat"><div class="number">7</div><div class="label">Firestore Collections</div></div>
</div>

<div class="apac" style="margin: 0 40px 60px; max-width: 820px; margin-left: auto; margin-right: auto;">
  <h3>APAC Relevance</h3>
  <p>India has 46 GW of installed wind capacity with aggressive 2030 targets. Australia, Vietnam, and the Philippines are scaling offshore and onshore wind rapidly. WindOps addresses the operational bottleneck common across APAC wind farms: fragmented tooling, manual handovers, and reactive maintenance. A conversational multi-agent system reduces mean time to resolution and keeps turbines generating.</p>
</div>

<footer>Built with Google ADK · Gemini 2.5 Flash · Vertex AI · Firestore · FastMCP · Cloud Run</footer>
</body>
</html>"""

AGENT_CARD = {
    "name": "WindOps Assistant",
    "description": "Multi-agent wind farm operations assistant. Handles maintenance tasks, technician scheduling, anomaly alerts, and operational analytics across 15 turbines.",
    "url": "https://wind-ops-assistant-cnd5nx432a-ew.a.run.app",
    "version": "1.0.0",
    "capabilities": {
        "streaming": True,
        "tools": ["task_management", "shift_scheduling", "knowledge_base", "analytics", "alert_management"]
    }
}

@app.get("/")
async def landing():
    return HTMLResponse(LANDING_HTML)

@app.get("/.well-known/agent.json")
async def agent_card():
    return JSONResponse(AGENT_CARD)

@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def proxy(request: Request, path: str):
    url = f"{ADK_BASE}/{path}"
    if request.query_string:
        url += f"?{request.query_string.decode()}"
    async with httpx.AsyncClient(timeout=120) as client:
        rp = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
            content=await request.body(),
        )
        return StreamingResponse(
            iter([rp.content]),
            status_code=rp.status_code,
            headers=dict(rp.headers),
        )
