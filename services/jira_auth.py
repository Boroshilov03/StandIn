import base64
import os


def get_jira_headers() -> dict:
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def get_base_url() -> str:
    return os.getenv("JIRA_BASE_URL", "").rstrip("/")


def get_project_key() -> str:
    return os.getenv("JIRA_PROJECT_KEY", "")
