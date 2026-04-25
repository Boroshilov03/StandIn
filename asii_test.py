import requests, os, json

from dotenv import load_dotenv
import os

load_dotenv()


# api_key = os.getenv('ASI_ONE_API_KEY')
# print(api_key)

url = "https://api.asi1.ai/v1/chat/completions"
headers = {
"Authorization": f"Bearer {os.getenv('ASI_ONE_API_KEY')}",
"Content-Type": "application/json"
}
body = {
"model": "asi1",
"messages": [{"role": "user", "content": "Hello! How can you help me today?"}]
}
res = requests.post(url, headers=headers, json=body)
print(res)
print(res.json()["choices"][0]["message"]["content"])
