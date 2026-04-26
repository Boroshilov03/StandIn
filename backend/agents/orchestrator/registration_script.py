import os
from pathlib import Path

from dotenv import load_dotenv
from uagents_core.utils.registration import (
    register_chat_agent,
    RegistrationRequestCredentials,
)

# Load project-level .env so this script works when run directly.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(PROJECT_ROOT / ".env")

register_chat_agent(
    "StandIn Orchestrator",
    "https://agentverse.ai/v2/agents/mailbox/submit",
    active=True,
    credentials=RegistrationRequestCredentials(
        agentverse_api_key=os.environ["AGENTVERSE_KEY"],
        agent_seed_phrase=os.environ["AGENTVERSE_SEED"],
    ),
)