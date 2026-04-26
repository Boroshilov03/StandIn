import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("JIRA_EMAIL")
token = os.getenv("JIRA_API_TOKEN")
base_url = os.getenv("JIRA_BASE_URL").rstrip("/")
project_key = os.getenv("JIRA_PROJECT_KEY")

credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
headers = {
    "Authorization": f"Basic {credentials}",
    "Accept": "application/json"
}

response = requests.get(
    f"{base_url}/rest/api/3/project/{project_key}",
    headers=headers
)
project = response.json()

print("Issue types for", project_key)
for issue_type in project.get("issueTypes", []):
    print(f"  Name: {issue_type['name']} | ID: {issue_type['id']}")