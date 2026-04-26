from typing import Any


def _as_clean_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _as_string_list(value: Any, default: list[str] | None = None) -> list[str]:
    if default is None:
        default = []
    if value is None:
        return list(default)
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items if items else list(default)
    text = str(value).strip()
    return [text] if text else list(default)


def normalize_action_payload(action_type: str, payload: dict[str, Any], meta: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
    normalized = dict(payload or {})
    owner = _as_clean_str(meta.get("owner"))
    title = _as_clean_str(meta.get("title"))
    summary = _as_clean_str(meta.get("summary"))
    context = _as_clean_str(meta.get("context"))
    priority = _as_clean_str(meta.get("priority"), "normal")

    if action_type == "send_slack":
        normalized["text"] = _as_clean_str(normalized.get("text"), summary or context or title)
        if not normalized["text"]:
            return False, normalized, "send_slack requires payload.text (or summary/context/title fallback)."
        normalized["channel"] = _as_clean_str(normalized.get("channel"), "#standin-updates")
        normalized["user_id"] = _as_clean_str(normalized.get("user_id"), owner)
        if not normalized["user_id"]:
            return False, normalized, "send_slack requires payload.user_id or ActionRequest.owner."
        return True, normalized, None

    if action_type == "draft_slack":
        normalized["channel"] = _as_clean_str(normalized.get("channel"), "#standin-updates")
        normalized["text"] = _as_clean_str(normalized.get("text"), summary or context or title or "StandIn draft message.")
        return True, normalized, None

    if action_type == "send_email":
        normalized["to"] = _as_string_list(normalized.get("to"), [])
        normalized["cc"] = _as_string_list(normalized.get("cc"), [])
        normalized["subject"] = _as_clean_str(normalized.get("subject"), title or "StandIn request")
        normalized["body"] = _as_clean_str(normalized.get("body"), summary or context or "Created by StandIn.")
        return True, normalized, None

    if action_type == "create_jira":
        normalized["summary"] = _as_clean_str(
            normalized.get("summary"),
            title or summary or "StandIn follow-up ticket",
        )
        normalized["description"] = _as_clean_str(
            normalized.get("description"),
            summary or context or normalized["summary"],
        )
        normalized["issuetype"] = _as_clean_str(normalized.get("issuetype"), "Task")
        normalized["priority"] = _as_clean_str(normalized.get("priority"), "Medium")
        normalized["labels"] = _as_string_list(normalized.get("labels"), ["standin", "auto-created"])
        normalized["status"] = _as_clean_str(normalized.get("status"), "To Do")
        normalized["sprint_name"] = _as_clean_str(normalized.get("sprint_name"), "Sprint 1")
        normalized["assignee_account_id"] = _as_clean_str(normalized.get("assignee_account_id"), "")
        return True, normalized, None

    if action_type == "update_jira_status":
        normalized["ticket_id"] = _as_clean_str(
            normalized.get("ticket_id"),
            _as_clean_str(normalized.get("issue_key")),
        )
        normalized["new_status"] = _as_clean_str(normalized.get("new_status"), "In Progress")
        normalized["comment"] = _as_clean_str(normalized.get("comment"), summary or context)
        if not normalized["ticket_id"]:
            return False, normalized, "update_jira_status requires payload.ticket_id (or issue_key)."
        return True, normalized, None

    if action_type == "schedule_meeting":
        normalized["title"] = _as_clean_str(normalized.get("title"), title or "StandIn follow-up")
        normalized["description"] = _as_clean_str(
            normalized.get("description"),
            summary or context or "Scheduled by StandIn perform_action.",
        )
        normalized["attendees"] = _as_string_list(normalized.get("attendees"), [])
        normalized["time_zone"] = _as_clean_str(normalized.get("time_zone"), "UTC")
        raw_duration = normalized.get("duration_minutes")
        try:
            duration = int(raw_duration) if raw_duration is not None else 30
        except (TypeError, ValueError):
            duration = 30
        normalized["duration_minutes"] = duration if duration > 0 else 30
        normalized["start_time"] = _as_clean_str(normalized.get("start_time"), "")
        normalized["end_time"] = _as_clean_str(normalized.get("end_time"), "")
        normalized["reminders"] = normalized.get("reminders") if isinstance(normalized.get("reminders"), list) else []
        return True, normalized, None

    if action_type in {"read_calendar_events", "read_calendar_event"}:
        raw_max = normalized.get("max_results")
        try:
            max_results = int(raw_max) if raw_max is not None else 10
        except (TypeError, ValueError):
            max_results = 10
        normalized["max_results"] = max(1, max_results)
        normalized["query"] = _as_clean_str(normalized.get("query"), "")
        normalized["time_min"] = _as_clean_str(normalized.get("time_min") or normalized.get("timeMin"), "")
        normalized["time_max"] = _as_clean_str(normalized.get("time_max") or normalized.get("timeMax"), "")
        normalized["event_id"] = _as_clean_str(normalized.get("event_id"), "")
        return True, normalized, None

    if action_type == "add_calendar_reminder":
        normalized["event_id"] = _as_clean_str(normalized.get("event_id"), "")
        reminders = normalized.get("reminders")
        if not isinstance(reminders, list):
            reminders = []
        normalized["reminders"] = reminders
        if not normalized["event_id"]:
            return False, normalized, "add_calendar_reminder requires payload.event_id."
        if not normalized["reminders"]:
            return False, normalized, "add_calendar_reminder requires payload.reminders list."
        return True, normalized, None

    if action_type == "create_action_item":
        normalized["description"] = _as_clean_str(normalized.get("description"), summary or context or "Action item from StandIn.")
        normalized["owner"] = _as_clean_str(normalized.get("owner"), owner or "unassigned")
        normalized["urgency"] = _as_clean_str(normalized.get("urgency"), "medium")
        normalized["escalation_required"] = bool(normalized.get("escalation_required", False))
        return True, normalized, None

    if action_type == "post_brief":
        normalized["brief_id"] = _as_clean_str(normalized.get("brief_id"), "")
        normalized["brief_data"] = normalized.get("brief_data") if isinstance(normalized.get("brief_data"), dict) else {}
        normalized["escalation_required"] = bool(normalized.get("escalation_required", False))
        return True, normalized, None

    normalized["priority"] = priority
    return True, normalized, None
