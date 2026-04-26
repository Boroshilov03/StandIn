import logging
import os
from datetime import UTC, datetime
from urllib.parse import quote_plus

import requests
from pymongo import MongoClient

from services.jira_auth import get_base_url, get_jira_headers, get_project_key

_LOGGER = logging.getLogger("jira_service")


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _to_adf(text: str) -> dict:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


def _require_jira_config() -> tuple[str, str]:
    base_url = get_base_url()
    project_key = get_project_key()
    if not base_url:
        raise RuntimeError("JIRA_BASE_URL is not set.")
    if not project_key:
        raise RuntimeError("JIRA_PROJECT_KEY is not set.")
    return base_url, project_key


def _jira_error(response: requests.Response) -> str:
    try:
        payload = response.json()
        return str(payload)
    except Exception:
        return response.text


def _get_project_issue_type_map(base_url: str, headers: dict, project_key: str) -> dict[str, str]:
    response = requests.get(
        f"{base_url}/rest/api/3/project/{project_key}",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    project = response.json()
    issue_types = project.get("issueTypes", [])
    available = [item.get("name", "") for item in issue_types if item.get("name")]
    if not available:
        raise RuntimeError(f"No issue types found for Jira project '{project_key}'.")

    normalized_to_actual = {name.strip().lower(): name for name in available}
    requested = ["Bug", "Task", "Story"]
    preferred = {"Bug": "Task", "Task": "Task", "Story": "Story"}
    resolved: dict[str, str] = {}
    for name in requested:
        mapped = preferred.get(name, name)
        resolved[name] = normalized_to_actual.get(mapped.lower(), available[0])
    return resolved


def _create_issue_with_fallbacks(
    base_url: str,
    headers: dict,
    project_key: str,
    details: dict,
    issue_type_map: dict[str, str],
) -> dict:
    issuetype_raw = details.get("issuetype", "Task")
    mapped_issuetype = issue_type_map.get(issuetype_raw, issue_type_map.get("Task", "Task"))
    fields: dict = {
        "project": {"key": project_key},
        "summary": details["summary"],
        "description": _to_adf(details.get("description", "")),
        "issuetype": {"name": mapped_issuetype},
        "priority": {"name": details.get("priority", "Medium")},
        "labels": details.get("labels", []),
    }

    assignee_account_id = (details.get("assignee_account_id") or "").strip()
    if assignee_account_id:
        fields["assignee"] = {"accountId": assignee_account_id}

    def _post(current_fields: dict):
        response = requests.post(
            f"{base_url}/rest/api/3/issue",
            headers=headers,
            json={"fields": current_fields},
            timeout=20,
        )
        if response.ok:
            return response.json()
        return None, response

    result = _post(fields)
    if not isinstance(result, tuple):
        return result

    _, response = result
    all_errors = _jira_error(response).lower()
    if "assignee" in all_errors:
        fields.pop("assignee", None)
        result = _post(fields)
        if not isinstance(result, tuple):
            return result
        _, response = result
        all_errors = _jira_error(response).lower()

    if "priority" in all_errors:
        fields.pop("priority", None)
        result = _post(fields)
        if not isinstance(result, tuple):
            return result
        _, response = result

    raise RuntimeError(
        f"Failed creating Jira issue ({response.status_code}): {_jira_error(response)}"
    )


def _transition_issue_to_status(base_url: str, headers: dict, issue_key: str, target_status: str) -> None:
    status = (target_status or "").strip()
    if not status or status.lower() == "to do":
        return

    transitions_response = requests.get(
        f"{base_url}/rest/api/3/issue/{issue_key}/transitions",
        headers=headers,
        timeout=20,
    )
    transitions_response.raise_for_status()
    transitions = transitions_response.json().get("transitions", [])
    transition_id = None
    for transition in transitions:
        if transition.get("name", "").strip().lower() == status.lower():
            transition_id = transition.get("id")
            break
    if not transition_id:
        raise RuntimeError(f"Transition '{status}' not available for {issue_key}")

    response = requests.post(
        f"{base_url}/rest/api/3/issue/{issue_key}/transitions",
        headers=headers,
        json={"transition": {"id": transition_id}},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(
            f"Failed transitioning {issue_key} to {status} ({response.status_code}): {_jira_error(response)}"
        )


def _resolve_sprint_id(base_url: str, headers: dict, project_key: str, sprint_name: str) -> int | None:
    boards_response = requests.get(
        f"{base_url}/rest/agile/1.0/board?projectKeyOrId={project_key}",
        headers=headers,
        timeout=20,
    )
    boards_response.raise_for_status()
    boards = boards_response.json().get("values", [])
    target = sprint_name.strip().lower()
    for board in boards:
        board_id = board.get("id")
        if board_id is None:
            continue
        sprints_response = requests.get(
            f"{base_url}/rest/agile/1.0/board/{board_id}/sprint",
            headers=headers,
            timeout=20,
        )
        if not sprints_response.ok:
            continue
        for sprint in sprints_response.json().get("values", []):
            if sprint.get("name", "").strip().lower() == target:
                sprint_id = sprint.get("id")
                if sprint_id is not None:
                    return int(sprint_id)
    return None


def _add_issue_to_sprint(base_url: str, headers: dict, sprint_id: int, issue_key: str) -> None:
    response = requests.post(
        f"{base_url}/rest/agile/1.0/sprint/{sprint_id}/issue",
        headers=headers,
        json={"issues": [issue_key]},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(
            f"Failed adding {issue_key} to sprint {sprint_id} ({response.status_code}): {_jira_error(response)}"
        )


def create_ticket(details: dict) -> dict:
    """
    details = {
        "summary": str,
        "description": str,       # plain text, converted to ADF internally
        "issuetype": str,         # "Bug", "Task", "Story"
        "priority": str,          # "High", "Medium", "Low"
        "labels": list[str]       # optional
    }
    Returns {"issueKey": "Q126SPRINT-X", "url": "..."}
    """
    base_url, project_key = _require_jira_config()
    headers = get_jira_headers()

    _LOGGER.info(
        "Jira create_ticket request | "
        f"project={project_key} | summary='{details.get('summary', '')[:120]}' | "
        f"issuetype={details.get('issuetype', 'Task')} | "
        f"priority={details.get('priority', 'Medium')} | "
        f"labels={details.get('labels', [])} | "
        f"status={details.get('status', 'To Do')} | "
        f"sprint='{details.get('sprint_name', '')}' | "
        f"assignee={details.get('assignee_account_id', '')}"
    )

    issue_type_map = _get_project_issue_type_map(base_url, headers, project_key)
    created = _create_issue_with_fallbacks(base_url, headers, project_key, details, issue_type_map)

    issue_key = created["key"]
    issue_id = created.get("id", "")
    issue_url = f"{base_url}/browse/{issue_key}"
    final_status = details.get("status", "To Do")

    transition_error = ""
    try:
        _transition_issue_to_status(base_url, headers, issue_key, final_status)
    except Exception as exc:
        transition_error = str(exc)

    sprint_name = (details.get("sprint_name") or "").strip()
    sprint_error = ""
    sprint_id = None
    if sprint_name:
        sprint_id = _resolve_sprint_id(base_url, headers, project_key, sprint_name)
        if sprint_id is None:
            sprint_error = f"Sprint '{sprint_name}' not found"
        else:
            try:
                _add_issue_to_sprint(base_url, headers, sprint_id, issue_key)
            except Exception as exc:
                sprint_error = str(exc)

    db = _get_db()
    db["jira_tickets"].update_one(
        {"_id": issue_key},
        {
            "$set": {
                "issueKey": issue_key,
                "issueId": issue_id,
                "summary": details["summary"],
                "issuetype": details.get("issuetype", "Task"),
                "priority": details.get("priority", "Medium"),
                "status": final_status,
                "labels": details.get("labels", []),
                "url": issue_url,
                "createdAt": datetime.now(UTC).isoformat(),
                "sprintName": sprint_name or None,
                "sprintId": sprint_id,
            }
        },
        upsert=True,
    )

    result: dict = {"issueKey": issue_key, "url": issue_url}
    if transition_error:
        result["transitionWarning"] = transition_error
    if sprint_error:
        result["sprintWarning"] = sprint_error

    _LOGGER.info(
        "Jira create_ticket success | "
        f"issueKey={issue_key} | issueId={issue_id} | url={issue_url} | "
        f"status={final_status} | sprintId={sprint_id} | sprintName='{sprint_name or ''}' | "
        f"transitionWarning='{transition_error}' | sprintWarning='{sprint_error}'"
    )
    return result


def update_ticket_status(issue_key: str, new_status: str) -> dict:
    base_url, _project_key = _require_jira_config()
    headers = get_jira_headers()
    _transition_issue_to_status(base_url, headers, issue_key, new_status)
    return {"issueKey": issue_key, "status": new_status}


def search_tickets(query: str = "", max_results: int = 20) -> list:
    """
    Fetch open tickets from the configured Jira project.
    query: optional text to narrow results (JQL `text ~`). Empty = all open tickets.
    Returns raw Jira issue dicts with fields populated.
    """
    base_url, project_key = _require_jira_config()
    headers = get_jira_headers()

    jql_parts = [f"project = {project_key}", "statusCategory != Done"]
    if query.strip():
        safe_q = query.strip().replace('"', '\\"')
        jql_parts.append(f'text ~ "{safe_q}"')

    jql = " AND ".join(jql_parts) + " ORDER BY updated DESC"
    encoded_jql = quote_plus(jql)

    query_string = (
        f"jql={encoded_jql}&maxResults={max_results}"
        f"&fields=summary,description,status,priority,assignee,labels,updated,created"
    )
    # Jira Cloud search endpoints differ across tenants/API rollouts.
    # Try the newer endpoint first, then fall back to the legacy one.
    candidate_urls = [
        f"{base_url}/rest/api/3/search?{query_string}",
    ]
    last_response = None
    for url in candidate_urls:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            last_response = response
            continue
        response.raise_for_status()
        return response.json().get("issues", [])

    if last_response is not None:
        last_response.raise_for_status()
    return []


def get_tickets(filters: dict) -> list:
    """
    filters = {
        "status": "To Do",       # optional
        "priority": "High",      # optional
        "labels": ["v1"],        # optional
    }
    Builds a JQL query and calls:
    GET {JIRA_BASE_URL}/rest/api/3/issue/search?jql={jql}&maxResults=20
    Returns list of issues.
    """
    base_url, project_key = _require_jira_config()
    headers = get_jira_headers()

    jql_parts = [f"project = {project_key}"]
    status = filters.get("status")
    priority = filters.get("priority")
    labels = filters.get("labels")

    if status:
        jql_parts.append(f'status = "{status}"')
    if priority:
        jql_parts.append(f'priority = "{priority}"')
    if labels:
        if isinstance(labels, list):
            quoted_labels = ", ".join([f'"{label}"' for label in labels])
            jql_parts.append(f"labels IN ({quoted_labels})")
        else:
            jql_parts.append(f'labels = "{labels}"')

    jql = " AND ".join(jql_parts)
    encoded_jql = quote_plus(jql)

    query_string = f"jql={encoded_jql}&maxResults=20"
    candidate_urls = [
        f"{base_url}/rest/api/3/search/jql?{query_string}",
        f"{base_url}/rest/api/3/search?{query_string}",
        f"{base_url}/rest/api/3/issue/search?{query_string}",
    ]
    last_response = None
    for url in candidate_urls:
        response = requests.get(url, headers=headers, timeout=20)
        if response.status_code == 404:
            last_response = response
            continue
        response.raise_for_status()
        result = response.json()
        return result.get("issues", [])

    if last_response is not None:
        last_response.raise_for_status()
    return []
