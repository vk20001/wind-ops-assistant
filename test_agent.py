import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from agent import root_agent

async def run(message: str):
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="wind-ops-assistant",
        user_id="test_user"
    )
    runner = Runner(
        agent=root_agent,
        app_name="wind-ops-assistant",
        session_service=session_service
    )
    content = Content(parts=[Part(text=message)])
    async for event in runner.run_async(
        user_id="test_user",
        session_id=session.id,
        new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    print(f"[{event.author}]: {part.text}")

asyncio.run(run("Add a field note: T-012 blade tip shows minor erosion, spotted during morning inspection"))
