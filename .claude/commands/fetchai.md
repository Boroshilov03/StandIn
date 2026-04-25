---
description: Fetch.ai uAgents development rules — apply to all Python files using uagents, uagents-core, uagents-adapter, or Agentverse patterns
globs: ["**/*.py"]
alwaysApply: false
---

# Fetch.ai uAgents Development Rules

## Package Versions (exact — tested for compatibility)

```
uagents==0.22.5
uagents-adapter==0.4.0
langchain==0.3.23
langgraph==0.3.20
crewai==0.126.0
langchain-openai==0.2.14
```

Always use a virtual environment.

---

## Agent Creation

```python
from uagents import Agent, Context, Model, Protocol
from pydantic import Field
from datetime import datetime, UTC

agent = Agent(
    name="descriptive_service_name",       # lowercase_snake_case, descriptive
    seed="unique_deterministic_seed_phrase", # env var in production
    port=8000,
    endpoint=["http://localhost:8000/submit"],
    mailbox=True                            # enables hybrid local/Agentverse
)
```

**Never** use `Agent(name="agent")` or generic names — names must describe the service.

---

## Message Models

Use `uagents.Model`, never `pydantic.BaseModel`.

```python
from uagents import Model
from pydantic import Field
from datetime import datetime, UTC

class ServiceRequest(Model):
    request_id: str = Field(..., description="Unique identifier")
    timestamp: str = Field(default="", description="ISO timestamp")

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now(UTC).isoformat()
        super().__init__(**data)
```

**Never use** `@field_validator` — causes pickle errors in uAgents message passing.
**Never use** `datetime.utcnow()` — use `datetime.now(UTC)` instead.

---

## REST Endpoints

```python
# GET: response model only
@agent.on_rest_get("/health", HealthResponse)
async def health_check(ctx: Context) -> HealthResponse:
    return HealthResponse(status="ok")

# POST: request AND response models
@agent.on_rest_post("/process", ProcessRequest, ProcessResponse)
async def process(ctx: Context, request: ProcessRequest) -> ProcessResponse:
    return ProcessResponse(result="...")
```

GET handlers take only `ctx`. POST handlers take `ctx` and the request model.

---

## Agent Communication

Agents must run in **separate terminals**. Always start the listener (Bob) first, then the initiator (Alice).

```python
# Step 1: run bob.py, copy the printed agent address
# Step 2: paste the real address into alice.py
BOB_ADDRESS = "agent1q..."   # real address from bob's output, never hardcoded placeholder

@alice.on_interval(period=5.0)
async def send_message(ctx: Context):
    await ctx.send(BOB_ADDRESS, Request(text="hello"))

@alice.on_message(model=Response)
async def handle_response(ctx: Context, sender: str, msg: Response):
    ctx.logger.info(f"Response from {sender}: {msg.text}")
```

---

## Protocol Definition

```python
my_protocol = Protocol(name="ServiceProtocol", version="1.0.0")

@my_protocol.on_message(model=ServiceRequest, replies={ServiceResponse})
async def handle_request(ctx: Context, sender: str, msg: ServiceRequest):
    try:
        result = await process(msg)
        await ctx.send(sender, ServiceResponse(result=result))
    except Exception as e:
        ctx.logger.error(f"Error: {e}")
        await ctx.send(sender, ServiceResponse(result="error", error=str(e)))

agent.include(my_protocol)
```

---

## LangGraph Integration

Use the **simple function wrapper** pattern — the official Fetch.ai approach. Do not build complex StateGraph pipelines for simple tasks.

```python
# ✅ DO: simple function wrapper
from langgraph.prebuilt import chat_agent_executor
from langchain_openai import ChatOpenAI

tools = [...]
model = ChatOpenAI(temperature=0)
app = chat_agent_executor.create_tool_calling_executor(model, tools)

def run_langgraph_agent(query: str) -> str:
    from langchain_core.messages import HumanMessage
    if isinstance(query, dict):
        query = query.get("input", str(query))
    messages = {"messages": [HumanMessage(content=query)]}
    final = None
    for output in app.stream(messages):
        final = list(output.values())[0]
    return final["messages"][-1].content if final else "No response"
```

```python
# ❌ DON'T: complex StateGraph for simple tasks
class ComplexAgent:
    def build_graph(self):
        graph = StateGraph(...)
        graph.add_node("ROUTER", ...)
        # ... 10+ nodes for what could be a function call
```

---

## Startup / Shutdown Handlers

```python
@agent.on_event("startup")
async def startup(ctx: Context):
    ctx.logger.info(f"Agent started: {ctx.agent.address}")
    # initialize connections, load config

@agent.on_event("shutdown")
async def shutdown(ctx: Context):
    ctx.logger.info("Agent shutting down")
    # close DB connections, flush state
```

---

## Error Handling

All `on_message` and `on_interval` handlers must catch exceptions and log them. Never let exceptions propagate silently.

```python
@agent.on_interval(period=30.0)
async def periodic_task(ctx: Context):
    try:
        await do_work(ctx)
    except Exception as e:
        ctx.logger.error(f"Periodic task failed: {e}")
```

---

## Entry Point

```python
if __name__ == "__main__":
    agent.run()
```

---

## Agentverse Deployment

Comment block at top of every agent file:

```python
# Agentverse: https://agentverse.ai
# Name: <Descriptive Agent Name>
# Description: <one sentence>
# Protocol: <ProtocolName> v<version>
# Mailbox: enabled
```

For hosted agents, remove `port` and `endpoint` — Agentverse provides these automatically.

---

## Official Documentation

- Agent creation: https://innovation.fetch.ai/docs/agents/create-agent
- Communication: https://innovation.fetch.ai/docs/agents/communicate
- LangGraph example: https://innovation.fetch.ai/docs/frameworks/langgraph
- REST endpoints: https://innovation.fetch.ai/docs/agents/rest-api
- Agentverse deployment: https://innovation.fetch.ai/docs/agentverse/deploy
