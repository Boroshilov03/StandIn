# /new-agent

Scaffold a new StandIn agent for the Fetch.ai Agentverse network.

## Usage

`/new-agent <role>`

Where `<role>` is one of: `orchestrator`, `engineering`, `design`, `product`, `gtm`, `verifier`, `escalation`, or a custom name.

## What to generate

Create `agents/<role>_agent.py` using these exact patterns (from `.cursor/rules/fetchai.mdc`):

### 1. Header comment block

```python
# Agentverse: https://agentverse.ai
# Name: StandIn <Role> Agent
# Description: <one sentence>
# Protocol: StandInProtocol v1.0.0
# Mailbox: enabled
```

### 2. Imports

```python
from uagents import Agent, Context, Model, Protocol
from pydantic import Field
from datetime import datetime, UTC
from pymongo import MongoClient
import google.generativeai as genai
from dotenv import load_dotenv
import os

load_dotenv()
```

### 3. Agent creation

Use `uagents==0.22.5`. Port assignment: orchestrator=8000, engineering=8001, design=8002, product=8003, gtm=8004, verifier=8005, escalation=8006.

```python
agent = Agent(
    name="standin_<role>_agent",
    seed=os.getenv("<ROLE>_SEED", "<role>_standin_default_seed"),
    port=<port>,
    endpoint=["http://localhost:<port>/submit"],
    mailbox=True
)
```

### 4. Message models

Use `uagents.Model` — never `pydantic.BaseModel`. Never use `@field_validator`.

```python
class UpdateRequest(Model):
    request_id: str = Field(..., description="Unique identifier")
    topic: str = Field(..., description="What to update on")
    timestamp: str = Field(default="", description="ISO timestamp")

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(UTC).isoformat()
        super().__init__(**data)

class UpdateResponse(Model):
    request_id: str = Field(..., description="Echoed request ID")
    summary: str = Field(..., description="Agent's update")
    confidence: str = Field(default="medium", description="high|medium|low")
    source_links: list[str] = Field(default_factory=list)
    timestamp: str = Field(default="", description="ISO timestamp")

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(UTC).isoformat()
        super().__init__(**data)
```

### 5. MongoDB connection

```python
mongo_client = MongoClient(os.getenv("MONGODB_URI"))
db = mongo_client["standin"]
updates_col = db["updates"]
evidence_col = db["evidence"]
action_items_col = db["action_items"]
```

### 6. Gemini setup

```python
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
gemini = genai.GenerativeModel("gemini-2.0-flash")
```

### 7. Protocol and message handler

```python
standin_protocol = Protocol(name="StandInProtocol", version="1.0.0")

@standin_protocol.on_message(model=UpdateRequest, replies={UpdateResponse})
async def handle_update_request(ctx: Context, sender: str, msg: UpdateRequest):
    try:
        # Query MongoDB for relevant state
        recent = list(updates_col.find(
            {"agent_id": agent.name},
            sort=[("timestamp", -1)],
            limit=5
        ))
        context_text = "\n".join([u.get("content", "") for u in recent])

        # Gemini synthesis
        prompt = f"Summarize the current {ctx.agent.name} status for topic '{msg.topic}'.\nContext:\n{context_text}"
        response = gemini.generate_content(prompt)
        summary = response.text

        # Persist update
        updates_col.insert_one({
            "agent_id": agent.name,
            "content": summary,
            "topic": msg.topic,
            "timestamp": datetime.now(UTC).isoformat(),
            "confidence": "medium",
            "request_id": msg.request_id,
        })

        await ctx.send(sender, UpdateResponse(
            request_id=msg.request_id,
            summary=summary,
        ))
    except Exception as e:
        ctx.logger.error(f"handle_update_request failed: {e}")
        await ctx.send(sender, UpdateResponse(
            request_id=msg.request_id,
            summary=f"Error: {e}",
            confidence="low",
        ))

agent.include(standin_protocol)
```

### 8. Startup/shutdown handlers

```python
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"StandIn {agent.name} started: {ctx.agent.address}")

@agent.on_event("shutdown")
async def shutdown(ctx: Context):
    ctx.logger.info(f"StandIn {agent.name} shutting down")
    mongo_client.close()
```

### 9. Role-specific interval task stub

Add an `on_interval` with a docstring describing what this role's periodic job is:
- **orchestrator**: poll for pending delegation requests
- **verifier**: scan recent updates for contradictions
- **escalation**: check action_items past their due date
- **role agents**: refresh local state cache from MongoDB

```python
@agent.on_interval(period=30.0)
async def periodic_task(ctx: Context):
    """TODO: <role-specific description>"""
    try:
        pass  # implement role-specific periodic behavior
    except Exception as e:
        ctx.logger.error(f"Periodic task failed: {e}")
```

### 10. Entry point

```python
if __name__ == "__main__":
    agent.run()
```

---

## After creating the file

Remind the user to:
- Add `<ROLE>_SEED=` to `.env`
- Add the agent's Agentverse address to the table in `CLAUDE.md` once deployed
- Start this agent in its own terminal; start listeners before initiators
