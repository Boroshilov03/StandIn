"""Run the StandIn agent topology with an ASI:One-facing orchestrator."""

import asyncio
import os

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

BUREAU_PORT = int(os.getenv("BUREAU_PORT", "8000"))


def _normalize_submit_endpoint(raw_endpoint: str | None, port: int) -> str:
    if raw_endpoint:
        endpoint = raw_endpoint.rstrip("/")
        if endpoint.endswith("/submit"):
            return endpoint
        return f"{endpoint}/submit"
    return f"http://localhost:{port}/submit"


def _resolve_public_endpoint(port: int) -> str:
    explicit = os.getenv("BUREAU_ENDPOINT")
    public_base = os.getenv("PUBLIC_BASE_URL")
    return _normalize_submit_endpoint(explicit or public_base, port)


def _resolve_agentverse() -> str | None:
    agentverse = os.getenv("AGENTVERSE_URL")
    if not agentverse:
        return None
    return agentverse.rstrip("/")


def main():
    public_endpoint = _resolve_public_endpoint(BUREAU_PORT)
    agentverse_url = _resolve_agentverse()
    bureau = Bureau(
        port=BUREAU_PORT,
        endpoint=[public_endpoint],
        agentverse=agentverse_url,
    )
    bureau.add(orchestrator)
    bureau.add(status_agent)
    bureau.add(historical_agent)
    bureau.add(perform_action_agent)
    bureau.add(watchdog_agent)

    print("\n=== StandIn Topology ===")
    print(f"  Bureau Port:      {BUREAU_PORT}")
    print(f"  Public Submit:    {public_endpoint}")
    print(f"  Orchestrator:    {orchestrator.address}")
    print(f"  Status Agent:    {status_agent.address}")
    print(f"  Historical:      {historical_agent.address}")
    print(f"  Perform Action:  {perform_action_agent.address}")
    print(f"  Watchdog:        {watchdog_agent.address}")
    if agentverse_url:
        print(f"  Agentverse URL:   {agentverse_url}")
    print("========================\n")

    bureau.run()


if __name__ == "__main__":
    main()
