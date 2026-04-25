# Repository Guidelines

## Project Structure & Module Organization
`StandIn` now runs from the `backend/` tree. Shared uAgents models live in `backend/models.py`, the local multi-agent runner is `backend/main.py`, and the local Chat Protocol harness is `backend/test_orchestrator.py`. Runtime agents live under `backend/agents/<role>/agent.py` for `orchestrator`, `status_agent`, `historical_agent`, `perform_action`, and `watchdog_agent`. Seeded demo data and MongoDB seeding utilities live in `backend/data/`.

## Build, Test, and Development Commands
Use the local virtual environment before running anything:

```powershell
.venv\Scripts\activate
pip install uagents==0.22.5 uagents-adapter==0.4.0 google-generativeai pymongo python-dotenv elevenlabs langchain==0.3.23 langgraph==0.3.20 langchain-openai==0.2.14
python -m compileall backend
python backend\main.py
python backend\test_orchestrator.py "Create a Jira ticket for the checkout API v2 blocker."
python backend\data\seed_db.py
```

`python backend\main.py` starts the local Bureau with orchestrator, status, historical, and action agents. `python backend\test_orchestrator.py "<prompt>"` sends one Chat Protocol message through the orchestrator and prints the reply. Run the seeder only when `MONGODB_URI` is configured.

## Coding Style & Naming Conventions
Use 4-space indentation, snake_case names, and short docstrings only where behavior is non-obvious. For message schemas, always use `uagents.Model`, not `pydantic.BaseModel`, and avoid `@field_validator` because it breaks message passing. Prefer `datetime.now(UTC)` over `datetime.utcnow()`. Keep cross-agent contracts in `backend/models.py`; keep agent-local helpers inside the owning module.

## Testing Guidelines
There is no formal test suite yet. Minimum validation is `python -m compileall backend`, then either `python backend\main.py` for startup checks or `python backend\test_orchestrator.py "<prompt>"` for routing checks. Keep new ad hoc tests lightweight and colocated with the backend, using names like `*_test.py`.

## Commit & Pull Request Guidelines
History uses short imperative subjects. Keep commits focused and slightly more descriptive, for example `wire chat orchestrator to status agent`. PRs should include a short summary, commands run, required `.env` changes, and log excerpts when changing multi-agent flow or ASI:One behavior.

## Security & Configuration Tips
Keep secrets in `.env` only: `GEMINI_API_KEY`, `MONGODB_URI`, `ASI_ONE_API_KEY`, and any stable seed vars such as `ORCHESTRATOR_SEED`. Do not hardcode secrets or published addresses. For local testing, rely on deterministic seeds and the addresses printed at startup.
