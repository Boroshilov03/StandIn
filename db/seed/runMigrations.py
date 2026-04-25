import importlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIGRATIONS = [
    "db.migrations.001_users",
    "db.migrations.002_slack_channels",
    "db.migrations.004_meetings",
    "db.migrations.005_decisions",
    "db.migrations.006_agent_briefs",
    "db.migrations.007_slack_messages",
    "db.migrations.008_action_log",
]


def run() -> None:
    root_env = ROOT / ".env"
    services_env = ROOT / "services" / ".env"
    if root_env.exists():
        load_dotenv(dotenv_path=root_env)
    elif services_env.exists():
        load_dotenv(dotenv_path=services_env)
    else:
        load_dotenv()
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI must be set in .env")

    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=6000)
    db = client["standin"]

    print("Running StandIn MongoDB migrations...")
    for module_name in MIGRATIONS:
        migration = importlib.import_module(module_name)
        changed = migration.migrate(db)
        print(f"  {module_name.split('.')[-1]}: {changed} upserted/modified")

    print("Done.")


if __name__ == "__main__":
    run()
