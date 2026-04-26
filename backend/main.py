"""Run the StandIn agent topology locally with a Bureau."""

import asyncio
import os

from dotenv import load_dotenv
from uagents import Agent, Bureau
from uagents_core.types import AgentInfo

# Load .env first so user-defined addresses take priority
load_dotenv()

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())


def _patch_agent_info() -> None:
    # Current installed uagents omits agent_type from Agent.info, but Bureau expects it.
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

# Import sub-agents first to get their computed local addresses
from agents.status_agent.agent import agent as status_agent
from agents.historical_agent.agent import agent as historical_agent
from agents.perform_action.agent import agent as perform_action_agent

# Wire sub-agent addresses into env vars BEFORE importing orchestrator.
# os.environ.setdefault only sets if NOT already present (from .env or shell),
# so Agentverse addresses in .env always take priority over local addresses.
os.environ.setdefault("STATUS_AGENT_ADDRESS", status_agent.address)
os.environ.setdefault("HISTORICAL_AGENT_ADDRESS", historical_agent.address)
os.environ.setdefault("PERFORM_ACTION_ADDRESS", perform_action_agent.address)

# Now import orchestrator — it reads the addresses we just wired
from agents.orchestrator.agent import orchestrator

BUREAU_PORT = int(os.getenv("BUREAU_PORT", "8000"))


def main():
    bureau = Bureau(
        port=BUREAU_PORT,
        endpoint=[f"http://localhost:{BUREAU_PORT}/submit"],
    )
    bureau.add(orchestrator)
    bureau.add(status_agent)
    bureau.add(historical_agent)
    bureau.add(perform_action_agent)

    print("\n=== StandIn Topology ===")
    print(f"  Bureau Port:      {BUREAU_PORT}")
    print(f"  Orchestrator:     {orchestrator.address}")
    print(f"  Status Agent:     {status_agent.address}")
    print(f"  Historical:       {historical_agent.address}")
    print(f"  Perform Action:   {perform_action_agent.address}")
    print("========================\n")

    bureau.run()


if __name__ == "__main__":
    main()
