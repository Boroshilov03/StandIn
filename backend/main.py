"""Run the StandIn agent topology with an ASI:One-facing orchestrator."""

import asyncio

from uagents import Agent, Bureau
from uagents_core.types import AgentInfo

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

from agents.historical_agent.agent import agent as historical_agent
from agents.orchestrator.agent import orchestrator
from agents.perform_action.agent import agent as perform_action_agent
from agents.status_agent.agent import agent as status_agent
from agents.watchdog_agent.agent import agent as watchdog_agent

BUREAU_PORT = int(__import__("os").getenv("BUREAU_PORT", "8000"))


def main():
    bureau = Bureau(
        port=BUREAU_PORT,
        endpoint=[f"http://localhost:{BUREAU_PORT}/submit"],
    )
    bureau.add(orchestrator)
    bureau.add(status_agent)
    bureau.add(historical_agent)
    bureau.add(perform_action_agent)
    bureau.add(watchdog_agent)

    print("\n=== StandIn Topology ===")
    print(f"  Bureau Port:      {BUREAU_PORT}")
    print(f"  Orchestrator:    {orchestrator.address}")
    print(f"  Status Agent:    {status_agent.address}")
    print(f"  Historical:      {historical_agent.address}")
    print(f"  Perform Action:  {perform_action_agent.address}")
    print(f"  Watchdog:        {watchdog_agent.address}")
    print("========================\n")

    bureau.run()


if __name__ == "__main__":
    main()
