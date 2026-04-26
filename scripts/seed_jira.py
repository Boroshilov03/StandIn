import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.jira_auth import get_base_url, get_jira_headers, get_project_key


ASSIGNEES = {
    "Derek": "712020:4de101a8-b63e-4725-81af-8dbf66b1a484",
    "Kai": "712020:3508513c-ffa5-413c-ac52-e884cd371e95",
    "Sam": "712020:ef71eea8-62f9-49e3-9f20-69cabbe510a5",
   }


def to_adf(text: str) -> dict:
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


def _get_db():
    mongodb_uri = os.getenv("MONGODB_URI", "")
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is not set.")
    client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=4000)
    return client["standin"]


def _validate_config() -> tuple[str, str]:
    base_url = get_base_url()
    project_key = get_project_key()
    if not base_url:
        raise RuntimeError("JIRA_BASE_URL is not set.")
    if not project_key:
        raise RuntimeError("JIRA_PROJECT_KEY is not set.")
    return base_url, project_key


def _print_users_and_pause(base_url: str, headers: dict) -> None:
    response = requests.get(
        f"{base_url}/rest/api/3/users/search?maxResults=50",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    users = response.json()

    print("Jira users (map names to accountIds before seeding):")
    for user in users:
        display_name = user.get("displayName", "(no name)")
        account_id = user.get("accountId", "(no accountId)")
        email = user.get("emailAddress", "")
        print(f" - {display_name} | accountId={account_id} | email={email}")

    input("\nUpdate ASSIGNEES with accountIds, then press Enter to continue...")


def _find_existing_issue_key(base_url: str, headers: dict, project_key: str, summary: str) -> str | None:
    encoded_summary = quote_plus(summary)
    response = requests.get(
        f"{base_url}/rest/api/3/issue/picker?query={encoded_summary}&projectKeys={project_key}",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    data = response.json()
    for section in data.get("sections", []):
        for issue in section.get("issues", []):
            if issue.get("summary") == summary:
                return issue.get("key")
    return None


def _get_project_issue_type_map(base_url: str, headers: dict, project_key: str) -> dict[str, str]:
    response = requests.get(
        f"{base_url}/rest/api/3/project/{project_key}",
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    project = response.json()
    issue_types = project.get("issueTypes", [])
    if not issue_types:
        raise RuntimeError(f"No issue types found for Jira project '{project_key}'.")

    available = [item.get("name", "") for item in issue_types if item.get("name")]
    print(f"Project issue types available: {', '.join(available)}")

    normalized_to_actual: dict[str, str] = {name.strip().lower(): name for name in available}

    # Canonical mapping from requested seed types to project-supported types.
    # Q126SPRINT supports Epic/Subtask/Task/Story, so Bug should map to Task.
    resolved = {}
    requested = ["Bug", "Task", "Story"]
    preferred_for_requested = {"Bug": "Task", "Task": "Task", "Story": "Story"}
    for name in requested:
        preferred = preferred_for_requested.get(name, name)
        preferred_lower = preferred.lower()
        if preferred_lower in normalized_to_actual:
            resolved[name] = normalized_to_actual[preferred_lower]
            continue

        # Heuristic fallback if project uses prefixed/suffixed names.
        lower_name = name.lower()
        partial_match = next(
            (
                actual
                for actual in available
                if preferred_lower in actual.strip().lower() or lower_name in actual.strip().lower()
            ),
            None,
        )
        if partial_match:
            resolved[name] = partial_match
            continue

        # Last resort: keep data flowing by mapping unknown type to first available.
        resolved[name] = available[0]
        print(
            f"Warning: could not map issue type '{name}' exactly; "
            f"falling back to '{available[0]}'."
        )

    return resolved


def _create_issue(
    base_url: str,
    headers: dict,
    project_key: str,
    ticket: dict,
    issue_type_map: dict[str, str],
) -> dict:
    assignee_key = ticket.get("assignee", "")
    assignee_id = ASSIGNEES.get(assignee_key, "")
    if not assignee_id or assignee_id == "paste-accountId-here":
        raise RuntimeError(f"Missing ASSIGNEES mapping for '{assignee_key}'")

    resolved_issue_type = issue_type_map.get(ticket["issuetype"], ticket["issuetype"])
    fields = {
        "project": {"key": project_key},
        "summary": ticket["summary"],
        "description": to_adf(ticket["description"]),
        "issuetype": {"name": resolved_issue_type},
        "priority": {"name": ticket["priority"]},
        "labels": ticket.get("labels", []),
        "assignee": {"accountId": assignee_id},
    }

    def _post_issue(current_fields: dict):
        response = requests.post(
            f"{base_url}/rest/api/3/issue",
            headers=headers,
            json={"fields": current_fields},
            timeout=20,
        )
        if response.ok:
            return response.json()
        return None, response

    result = _post_issue(fields)
    if not isinstance(result, tuple):
        return result

    _, response = result
    error_payload = {}
    try:
        error_payload = response.json()
    except Exception:
        pass
    error_messages = " ".join(error_payload.get("errorMessages", []))
    field_errors = error_payload.get("errors", {})
    field_errors_text = " ".join([f"{k}: {v}" for k, v in field_errors.items()])
    all_errors = f"{error_messages} {field_errors_text}".lower()

    # Team-managed Jira projects may reject assignee/priority on create if not on screen.
    # Retry progressively with optional fields removed.
    if "assignee" in all_errors:
        print(f"Warning: create issue rejected assignee for '{ticket['summary']}'. Retrying without assignee.")
        fields.pop("assignee", None)
        result = _post_issue(fields)
        if not isinstance(result, tuple):
            return result
        _, response = result
        try:
            error_payload = response.json()
        except Exception:
            error_payload = {}
        error_messages = " ".join(error_payload.get("errorMessages", []))
        field_errors = error_payload.get("errors", {})
        field_errors_text = " ".join([f"{k}: {v}" for k, v in field_errors.items()])
        all_errors = f"{error_messages} {field_errors_text}".lower()

    if "priority" in all_errors:
        print(f"Warning: create issue rejected priority for '{ticket['summary']}'. Retrying without priority.")
        fields.pop("priority", None)
        result = _post_issue(fields)
        if not isinstance(result, tuple):
            return result
        _, response = result
        try:
            error_payload = response.json()
        except Exception:
            error_payload = {}

    details = error_payload if error_payload else response.text
    raise RuntimeError(
        f"Failed creating ticket '{ticket['summary']}' ({response.status_code}): {details}"
    )


def _maybe_transition_issue(base_url: str, headers: dict, issue_key: str, target_status: str) -> None:
    if target_status == "To Do":
        return

    transitions_response = requests.get(
        f"{base_url}/rest/api/3/issue/{issue_key}/transitions",
        headers=headers,
        timeout=20,
    )
    transitions_response.raise_for_status()
    transitions = transitions_response.json().get("transitions", [])

    target_id = None
    for transition in transitions:
        name = transition.get("name", "").strip().lower()
        if name == target_status.strip().lower():
            target_id = transition.get("id")
            break

    if not target_id:
        print(
            f"Warning: transition '{target_status}' not available for {issue_key}. "
            "Skipping transition."
        )
        return

    try:
        response = requests.post(
            f"{base_url}/rest/api/3/issue/{issue_key}/transitions",
            headers=headers,
            json={"transition": {"id": target_id}},
            timeout=20,
        )
        response.raise_for_status()
    except Exception as exc:
        print(f"Warning: failed to transition {issue_key} to '{target_status}': {exc}")


def _store_ticket(db, base_url: str, issue_key: str, issue_id: str, ticket: dict) -> None:
    db["jira_tickets"].update_one(
        {"_id": issue_key},
        {
            "$set": {
                "issueKey": issue_key,
                "issueId": issue_id,
                "summary": ticket["summary"],
                "issuetype": ticket["issuetype"],
                "priority": ticket["priority"],
                "status": ticket["status"],
                "labels": ticket["labels"],
                "assignee": ticket["assignee"],
                "url": f"{base_url}/browse/{issue_key}",
            }
        },
        upsert=True,
    )


def _get_target_sprint_id(
    base_url: str,
    headers: dict,
    project_key: str,
    sprint_name: str = "Sprint 1",
) -> int | None:
    boards_response = requests.get(
        f"{base_url}/rest/agile/1.0/board?projectKeyOrId={project_key}",
        headers=headers,
        timeout=20,
    )
    boards_response.raise_for_status()
    boards = boards_response.json().get("values", [])
    if not boards:
        print(f"Warning: no Jira boards found for project '{project_key}'.")
        return None

    target_lower = sprint_name.strip().lower()
    for board in boards:
        board_id = board.get("id")
        board_name = board.get("name", "")
        if not board_id:
            continue

        sprints_response = requests.get(
            f"{base_url}/rest/agile/1.0/board/{board_id}/sprint",
            headers=headers,
            timeout=20,
        )
        if not sprints_response.ok:
            print(f"Warning: could not list sprints for board '{board_name}' ({board_id}).")
            continue
        sprints = sprints_response.json().get("values", [])
        for sprint in sprints:
            name = sprint.get("name", "")
            if name.strip().lower() == target_lower:
                sprint_id = sprint.get("id")
                if sprint_id is not None:
                    print(f"Using sprint '{name}' (id={sprint_id}) from board '{board_name}'.")
                    return int(sprint_id)

    print(f"Warning: sprint '{sprint_name}' not found on boards for project '{project_key}'.")
    return None


def _add_issue_to_sprint(base_url: str, headers: dict, sprint_id: int, issue_key: str) -> None:
    response = requests.post(
        f"{base_url}/rest/agile/1.0/sprint/{sprint_id}/issue",
        headers=headers,
        json={"issues": [issue_key]},
        timeout=20,
    )
    if response.ok:
        print(f"Added {issue_key} to sprint id {sprint_id}")
        return
    details = {}
    try:
        details = response.json()
    except Exception:
        pass
    print(
        f"Warning: failed to add {issue_key} to sprint {sprint_id} "
        f"({response.status_code}): {details or response.text}"
    )


def run() -> None:
    load_dotenv(ROOT / ".env")
    base_url, project_key = _validate_config()
    headers = get_jira_headers()
    db = _get_db()

    _print_users_and_pause(base_url, headers)
    issue_type_map = _get_project_issue_type_map(base_url, headers, project_key)
    sprint_id = _get_target_sprint_id(base_url, headers, project_key, sprint_name="Sprint 1")

    tickets = [
        {
            "summary": "OAuth token not invalidated on delegate handoff",
            "description": "Stale auth contexts persist after agent handoff. Token refresh interceptor not resetting on delegate init. Found during QA regression. See Slack #engineering-bugs thread Day 1.",
            "issuetype": "Bug",
            "priority": "High",
            "status": "Done",
            "labels": ["auth", "critical-path", "v1"],
            "assignee": "Derek",
        },
        {
            "summary": "Token expiry edge case — race condition under <30s tokens",
            "description": "Flaky test in auth regression suite. Reproduces only with artificially short-lived tokens. Not a real-world risk for v1 but should be addressed post-launch.",
            "issuetype": "Bug",
            "priority": "Low",
            "status": "To Do",
            "labels": ["auth", "post-launch", "tech-debt"],
            "assignee": "Derek",
        },
        {
            "summary": "Remove delegate handoff UI from v1 scope",
            "description": "Scope cut agreed by Alice and Ben on Day 1. Core agent handoff still works, UI polish moves to v1.1. Update QA test plan accordingly.",
            "issuetype": "Task",
            "priority": "Medium",
            "status": "Done",
            "labels": ["scope", "v1", "demo"],
            "assignee": "Kai",
        },
        {
            "summary": "RAG evidence pipeline smoke test",
            "description": "Priya flagged this needs a smoke test before launch. Verify vector search returns correct evidence documents for status and history queries.",
            "issuetype": "Task",
            "priority": "High",
            "status": "Done",
            "labels": ["rag", "testing", "v1"],
            "assignee": "Kai",
        },
        {
            "summary": "Seed production MongoDB with Meridian scenario data",
            "description": "James to load production seed into staging cluster by Thursday EOD. Required for demo dry run Friday morning.",
            "issuetype": "Task",
            "priority": "Medium",
            "status": "Done",
            "labels": ["data", "staging", "demo"],
            "assignee": "Sam",
        },
        {
            "summary": "Fix brief output label — wrong display on action dispatch result",
            "description": "Minor UI label issue caught during Friday dry run. One-liner fix. Priya flagged, James resolved same day.",
            "issuetype": "Bug",
            "priority": "Low",
            "status": "Done",
            "labels": ["ui", "brief", "demo"],
            "assignee": "Sam",
        },
        {
            "summary": "Data processing addendum (DPA) — vendor contract",
            "description": "Sara to handle async post signing. Vendor contract signed Monday. DPA is a follow-up requirement, not blocking launch.",
            "issuetype": "Task",
            "priority": "Medium",
            "status": "To Do",
            "labels": ["legal", "vendor", "ops"],
            "assignee": "Derek",
        },
        {
            "summary": "Set up v1.1 planning cycle",
            "description": "First planning cycle post-launch starts Wednesday. Alice to run. Key items: delegate handoff UI, token race condition fix, post-launch retro actions.",
            "issuetype": "Task",
            "priority": "Low",
            "status": "To Do",
            "labels": ["planning", "v1.1"],
            "assignee": "Sam",
        },
        {
            "summary": "Board demo script — finalize scope and flow",
            "description": "Demo covers: status query, conflict detection, action dispatch (calendar event creation). Handoff UI section dropped. Dry run Friday 10am.",
            "issuetype": "Task",
            "priority": "High",
            "status": "Done",
            "labels": ["demo", "board", "v1"],
            "assignee": "Kai",
        },
        {
            "summary": "Launch comms — internal announcement and external post",
            "description": "Sara coordinating. Goes out Monday 9am. Vendor signing at 11am same day. Make sure comms don't reference handoff UI — it's not in v1.",
            "issuetype": "Task",
            "priority": "Medium",
            "status": "To Do",
            "labels": ["comms", "launch", "ops"],
            "assignee": "Sam",
        },
    ]

    created = 0
    skipped = 0
    for ticket in tickets:
        existing_key = _find_existing_issue_key(base_url, headers, project_key, ticket["summary"])
        if existing_key:
            print(f"Skipping existing ticket: {ticket['summary']} -> {existing_key}")
            _store_ticket(db, base_url, existing_key, "", ticket)
            if sprint_id is not None:
                _add_issue_to_sprint(base_url, headers, sprint_id, existing_key)
            skipped += 1
            continue

        created_issue = _create_issue(base_url, headers, project_key, ticket, issue_type_map)
        issue_key = created_issue["key"]
        issue_id = created_issue.get("id", "")
        print(f"Created ticket: {ticket['summary']} -> {issue_key}")

        _maybe_transition_issue(base_url, headers, issue_key, ticket["status"])
        if sprint_id is not None:
            _add_issue_to_sprint(base_url, headers, sprint_id, issue_key)
        _store_ticket(db, base_url, issue_key, issue_id, ticket)
        created += 1

    print(f"seed_jira complete: created={created}, skipped={skipped}")


if __name__ == "__main__":
    run()
