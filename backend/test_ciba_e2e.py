"""
End-to-end CIBA test through the perform_action agent.

Spins up perform_action + a tiny test client in one Bureau, sends a
send_slack ActionRequest with owner=mika.borosh@gmail.com, watches for
the CIBA push, and polls until you approve on phone (or it times out).

Run from project root:
    .venv\\Scripts\\activate
    python backend/test_ciba_e2e.py

Phone should buzz within ~3 seconds. Tap Allow → script prints "approved".
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from datetime import UTC, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from uagents import Agent, Bureau, Context, Protocol
from uagents.setup import fund_agent_if_low

from agents.perform_action.agent import agent as perform_action_agent
from models import ActionRequest, ActionResponse


TEST_OWNER_EMAIL = os.getenv("TEST_OWNER_EMAIL", "mika.borosh@gmail.com")
PORT = 8123

client = Agent(
    name="ciba_test_client",
    seed="ciba_test_client_seed_v1",
    port=PORT,
    endpoint=[f"http://localhost:{PORT}/submit"],
)

_done = asyncio.Event()


@client.on_event("startup")
async def fire(ctx: Context):
    req = ActionRequest(
        request_id=f"ciba-test-{uuid.uuid4().hex[:8]}",
        action_type="send_slack",
        payload=json.dumps({
            "text":    "[CIBA TEST] StandIn approval gate test message",
            "channel": "general",
        }),
        owner=TEST_OWNER_EMAIL,
        owner_name="Mika",
        title="CIBA E2E test",
        summary="Verify push lands on phone via perform_action → auth0_ai",
        priority="normal",
        risk="medium",
    )
    ctx.logger.info(f">>> Sending ActionRequest to perform_action | owner={TEST_OWNER_EMAIL}")
    ctx.logger.info(">>> CHECK YOUR PHONE — Guardian push should arrive within ~3 sec")
    await ctx.send(perform_action_agent.address, req)


@client.on_message(ActionResponse)
async def on_response(ctx: Context, sender: str, msg: ActionResponse):
    ctx.logger.info("=" * 60)
    ctx.logger.info(f"RESPONSE | success={msg.success} | action_id={msg.action_id}")
    ctx.logger.info(f"  status={getattr(msg, 'status', None)}")
    ctx.logger.info(f"  error={msg.error}")
    if hasattr(msg, "auth0_ciba"):
        ctx.logger.info(f"  auth0_ciba={msg.auth0_ciba}")
    ctx.logger.info("=" * 60)
    _done.set()


async def main():
    bureau = Bureau()
    bureau.add(perform_action_agent)
    bureau.add(client)

    task = asyncio.create_task(bureau.run_async())
    try:
        await asyncio.wait_for(_done.wait(), timeout=180)
    except asyncio.TimeoutError:
        print("TIMEOUT — no ActionResponse within 180s")
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())
