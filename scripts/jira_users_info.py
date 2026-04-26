import os
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

email = os.getenv("JIRA_EMAIL")
token = os.getenv("JIRA_API_TOKEN")
base_url = os.getenv("JIRA_BASE_URL").rstrip("/")

credentials = base64.b64encode(f"{email}:{token}".encode()).decode()
headers = {
    "Authorization": f"Basic {credentials}",
    "Accept": "application/json"
}

response = requests.get(f"{base_url}/rest/api/3/users/search?maxResults=50", headers=headers)
users = response.json()

for user in users:
    print(f"Name: {user.get('displayName')} | accountId: {user.get('accountId')}")