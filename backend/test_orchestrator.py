"""Run a one-shot local Chat Protocol test against the orchestrator."""

import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

from uagents import Agent, Bureau
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    TextContent,
    chat_protocol_spec,
)
from uagents_core.types import AgentInfo

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


def _patch_agent_info() -> None:
    def _info(self) -> AgentInfo:
        return AgentInfo(
            address=self.address,
            prefix=self._prefix,
            endpoints=self._endpoints,
            protocols=list(self.protocols.keys()),
            agent_type="uagent",
            metadata=self.metadata,
        )

    Agent.info = property(_info)


_patch_agent_info()

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from agents.historical_agent.agent import agent as historical_agent
from agents.orchestrator.agent import orchestrator
from agents.perform_action.agent import agent as perform_action_agent
from agents.status_agent.agent import agent as status_agent
from uagents import Context, Protocol

TEST_BUREAU_PORT = int(os.getenv("TEST_BUREAU_PORT", "8100"))
TEST_TIMEOUT_SECONDS = int(os.getenv("TEST_TIMEOUT_SECONDS", "60"))

client = Agent(
    name="standin_test_client",
    seed="standin_test_client_seed_v1",
    port=TEST_BUREAU_PORT,
    endpoint=[f"http://localhost:{TEST_BUREAU_PORT}/submit"],
)
client_proto = Protocol(spec=chat_protocol_spec)
_completed = False


async def _shutdown(exit_code: int) -> None:
    sys.stdout.flush()
    sys.stderr.flush()
    await asyncio.sleep(0.2)
    os._exit(exit_code)


@client.on_event("startup")
async def send_test_message(ctx: Context) -> None:
    prompt = " ".join(sys.argv[1:]).strip() or "Give me a briefing on Launch Alpha readiness."
    ctx.logger.info(f"Sending test prompt to orchestrator: {prompt}")

    async def _timeout() -> None:
        await asyncio.sleep(TEST_TIMEOUT_SECONDS)
        if not _completed:
            print("Timed out waiting for orchestrator response.", file=sys.stderr, flush=True)
            await _shutdown(1)

    asyncio.create_task(_timeout())
    await ctx.send(
        orchestrator.address,
        ChatMessage(
            timestamp=datetime.now(UTC),
            msg_id=uuid.uuid4(),
            content=[TextContent(type="text", text=prompt)],
        ),
    )


@client_proto.on_message(ChatAcknowledgement)
async def handle_ack(ctx: Context, sender: str, msg: ChatAcknowledgement) -> None:
    ctx.logger.info(f"Acknowledged by {sender}")


@client_proto.on_message(ChatMessage)
async def handle_reply(ctx: Context, sender: str, msg: ChatMessage) -> None:
    global _completed
    _completed = True
    print("\n=== Orchestrator Reply ===\n", flush=True)
    print(msg.text(), flush=True)
    print("\n==========================\n", flush=True)
    await _shutdown(0)


client.include(client_proto)


def main() -> None:
    bureau = Bureau(
        port=TEST_BUREAU_PORT,
        endpoint=[f"http://localhost:{TEST_BUREAU_PORT}/submit"],
    )
    bureau.add(orchestrator)
    bureau.add(status_agent)
    bureau.add(historical_agent)
    bureau.add(perform_action_agent)
    bureau.add(client)
    bureau.run()


if __name__ == "__main__":
    main()
