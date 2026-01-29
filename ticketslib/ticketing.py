import json
import os
from dataclasses import dataclass
from typing import Any, Iterable

import yaml

from ticketslib.utils import (
    ISO_UTC_REGEX,
    Issue,
    format_iso_utc,
    generate_uuidv7,
    is_uuidv7,
    parse_iso_utc,
    parse_run_started_filename,
    read_text,
    write_text,
)

REQUIRED_SECTIONS = ["# Ticket", "## Description", "## Acceptance Criteria", "## Verification"]

STATUS_VALUES = {"todo", "doing", "blocked", "done", "canceled"}
PRIORITY_VALUES = {"low", "medium", "high", "critical"}
ASSIGNMENT_MODES = {"human_only", "agent_only", "mixed"}

RELATIONSHIP_FIELDS = {"dependencies", "blocks", "related"}
RELATIONSHIP_LIKE_FIELDS = {
    "blocked_by",
    "depends_on",
    "parent",
    "parents",
    "child",
    "children",
    "duplicate",
    "duplicates",
    "duplicate_of",
    "supersedes",
    "superseded_by",
    "related_to",
}


@dataclass
class Ticket:
    path: str
    front_matter: dict[str, Any]
    body: str


@dataclass
class LogEntry:
    data: dict[str, Any]
    line_no: int


@dataclass
class LogFile:
    path: str
    entries: list[LogEntry]
    filename_run_started: str | None
    filename_run_id: str | None


@dataclass
class IssueResult:
    issues: list[Issue]
    repairs: list[dict[str, Any]]


class TicketLoadError(Exception):
    pass


class NoTimestampLoader(yaml.SafeLoader):
    pass


for ch, patterns in list(NoTimestampLoader.yaml_implicit_resolvers.items()):
    NoTimestampLoader.yaml_implicit_resolvers[ch] = [
        (tag, regexp) for tag, regexp in patterns if tag != "tag:yaml.org,2002:timestamp"
    ]


def split_front_matter(content: str) -> tuple[dict[str, Any], str]:
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        raise TicketLoadError("Missing YAML front matter")
    try:
        end_index = lines[1:].index("---") + 1
    except ValueError as exc:
        raise TicketLoadError("Unterminated YAML front matter") from exc
    front_matter_text = "\n".join(lines[1:end_index])
    body = "\n".join(lines[end_index + 1 :])
    try:
        front_matter = yaml.load(front_matter_text, Loader=NoTimestampLoader) or {}
    except yaml.YAMLError as exc:
        raise TicketLoadError("Invalid YAML front matter") from exc
    if not isinstance(front_matter, dict):
        raise TicketLoadError("Front matter must be a mapping")
    return front_matter, body


def load_ticket(ticket_path: str) -> Ticket:
    content = read_text(ticket_path)
    front_matter, body = split_front_matter(content)
    return Ticket(path=ticket_path, front_matter=front_matter, body=body)


def find_tickets(root: str) -> list[str]:
    tickets_dir = os.path.join(root, ".tickets")
    if not os.path.isdir(tickets_dir):
        return []
    results: list[str] = []
    for entry in sorted(os.listdir(tickets_dir)):
        ticket_path = os.path.join(tickets_dir, entry, "ticket.md")
        if os.path.isfile(ticket_path):
            results.append(ticket_path)
    return results


def find_logs(ticket_dir: str) -> list[str]:
    logs_dir = os.path.join(ticket_dir, "logs")
    if not os.path.isdir(logs_dir):
        return []
    logs = [
        os.path.join(logs_dir, filename)
        for filename in sorted(os.listdir(logs_dir))
        if filename.endswith(".jsonl")
    ]
    return logs


def parse_log_file(path: str) -> LogFile:
    filename = os.path.basename(path)
    filename_run_started = None
    filename_run_id = None
    parsed = parse_run_started_filename(filename)
    if parsed:
        filename_run_started, filename_run_id = parsed
    entries: list[LogEntry] = []
    with open(path, "r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                data = {"_parse_error": "invalid_json"}
            entries.append(LogEntry(data=data, line_no=index))
    return LogFile(
        path=path,
        entries=entries,
        filename_run_started=filename_run_started,
        filename_run_id=filename_run_id,
    )


def has_required_sections(body: str) -> list[str]:
    missing: list[str] = []
    lowered = body.lower()
    for section in REQUIRED_SECTIONS:
        if section.lower() not in lowered:
            missing.append(section)
    return missing


def normalize_section_body(body: str) -> str:
    lines = body.splitlines()
    present = set()
    for line in lines:
        if line.strip().startswith("#"):
            present.add(line.strip())
    additions = []
    for section in REQUIRED_SECTIONS:
        if section not in present:
            additions.append("\n" + section + "\n")
    return body.rstrip() + "".join(additions) + "\n"


def collect_string_list(value: Any) -> list[str] | None:
    if value is None:
        return []
    if isinstance(value, list):
        if all(isinstance(item, str) for item in value):
            return value
        return None
    if isinstance(value, str):
        return [value]
    return None


def validate_ticket(ticket: Ticket) -> IssueResult:
    issues: list[Issue] = []
    repairs: list[dict[str, Any]] = []

    def add_issue(severity: str, code: str, message: str) -> None:
        issue_id = f"I{len(issues) + 1:04d}"
        issues.append(
            Issue(
                issue_id=issue_id,
                severity=severity,
                code=code,
                message=message,
                ticket_path=ticket.path,
            )
        )

    front = ticket.front_matter
    required = ["id", "title", "status", "created_at"]
    for field in required:
        if field not in front:
            add_issue("error", "TICKET_REQUIRED_FIELD_MISSING", f"Missing required field: {field}")

    ticket_id = front.get("id")
    if ticket_id is not None and not (isinstance(ticket_id, str) and is_uuidv7(ticket_id)):
        add_issue("error", "TICKET_ID_INVALID", "Ticket id must be a UUIDv7 string")
        repairs.append(
            {
                "id": f"R{len(repairs) + 1:04d}",
                "enabled": False,
                "safe": False,
                "issue_ids": [issues[-1].issue_id],
                "action": "set_front_matter_field",
                "ticket_path": ticket.path,
                "params": {
                    "field": "id",
                    "value": None,
                    "generate_uuidv7": True,
                    "update_references": None,
                },
            }
        )

    status = front.get("status")
    if status is not None:
        if not isinstance(status, str) or status.lower() not in STATUS_VALUES:
            add_issue("error", "TICKET_STATUS_INVALID", "Ticket status must be one of todo/doing/blocked/done/canceled")
        elif status != status.lower():
            add_issue("warning", "TICKET_STATUS_NORMALIZE", "Ticket status should be lowercase")
            repairs.append(
                {
                    "id": f"R{len(repairs) + 1:04d}",
                    "enabled": False,
                    "safe": True,
                    "issue_ids": [issues[-1].issue_id],
                    "action": "normalize_enum",
                    "ticket_path": ticket.path,
                    "params": {"field": "status", "value": status.lower()},
                }
            )

    created_at = front.get("created_at")
    if created_at is not None:
        if not isinstance(created_at, str) or parse_iso_utc(created_at) is None:
            add_issue("error", "TICKET_CREATED_AT_INVALID", "created_at must be ISO 8601 UTC timestamp")
        elif created_at != format_iso_utc(parse_iso_utc(created_at)):
            add_issue("warning", "TICKET_CREATED_AT_NORMALIZE", "created_at should be normalized to UTC Z format")
            repairs.append(
                {
                    "id": f"R{len(repairs) + 1:04d}",
                    "enabled": False,
                    "safe": True,
                    "issue_ids": [issues[-1].issue_id],
                    "action": "normalize_created_at",
                    "ticket_path": ticket.path,
                    "params": {"value": format_iso_utc(parse_iso_utc(created_at))},
                }
            )

    priority = front.get("priority")
    if priority is not None:
        if not isinstance(priority, str) or priority.lower() not in PRIORITY_VALUES:
            add_issue("error", "TICKET_PRIORITY_INVALID", "priority must be low/medium/high/critical")
        elif priority != priority.lower():
            add_issue("warning", "TICKET_PRIORITY_NORMALIZE", "priority should be lowercase")
            repairs.append(
                {
                    "id": f"R{len(repairs) + 1:04d}",
                    "enabled": False,
                    "safe": True,
                    "issue_ids": [issues[-1].issue_id],
                    "action": "normalize_enum",
                    "ticket_path": ticket.path,
                    "params": {"field": "priority", "value": priority.lower()},
                }
            )

    assignment = front.get("assignment")
    if assignment is not None:
        if not isinstance(assignment, dict):
            add_issue("error", "TICKET_ASSIGNMENT_INVALID", "assignment must be a mapping")
        else:
            mode = assignment.get("mode")
            if mode is not None and (not isinstance(mode, str) or mode not in ASSIGNMENT_MODES):
                add_issue("error", "TICKET_ASSIGNMENT_MODE_INVALID", "assignment.mode must be human_only/agent_only/mixed")

    for relationship in RELATIONSHIP_FIELDS:
        if relationship in front:
            values = collect_string_list(front.get(relationship))
            if values is None:
                add_issue(
                    "error",
                    "TICKET_RELATIONSHIP_INVALID",
                    f"{relationship} must be a list of UUID strings",
                )
            else:
                invalid_ids = [value for value in values if not is_uuidv7(value)]
                if invalid_ids:
                    add_issue(
                        "error",
                        "TICKET_RELATIONSHIP_ID_INVALID",
                        f"{relationship} contains invalid UUIDv7 values",
                    )
                if isinstance(front.get(relationship), str) or "" in values:
                    normalized = [value for value in values if value]
                    repairs.append(
                        {
                            "id": f"R{len(repairs) + 1:04d}",
                            "enabled": False,
                            "safe": True,
                            "issue_ids": [issues[-1].issue_id] if issues else [],
                            "action": "normalize_relationship_list",
                            "ticket_path": ticket.path,
                            "params": {"field": relationship, "value": normalized},
                        }
                    )

    for key in front.keys():
        if key in RELATIONSHIP_LIKE_FIELDS:
            add_issue(
                "error",
                "TICKET_RELATIONSHIP_FIELD_INVALID",
                f"Relationship-like field '{key}' should not be persisted in ticket front matter",
            )

    missing_sections = has_required_sections(ticket.body)
    if missing_sections:
        add_issue(
            "error",
            "TICKET_MISSING_SECTIONS",
            f"Missing required sections: {', '.join(missing_sections)}",
        )
        repairs.append(
            {
                "id": f"R{len(repairs) + 1:04d}",
                "enabled": False,
                "safe": True,
                "issue_ids": [issues[-1].issue_id],
                "action": "add_required_sections",
                "ticket_path": ticket.path,
                "params": {"missing": missing_sections},
            }
        )

    return IssueResult(issues=issues, repairs=repairs)


def validate_logs(ticket_dir: str) -> IssueResult:
    issues: list[Issue] = []

    def add_issue(severity: str, code: str, message: str, log_path: str, line_no: int | None = None) -> None:
        issue_id = f"I{len(issues) + 1:04d}"
        location = {"line": line_no} if line_no else None
        issues.append(
            Issue(
                issue_id=issue_id,
                severity=severity,
                code=code,
                message=message,
                ticket_path=log_path,
                location=location,
            )
        )

    logs = find_logs(ticket_dir)
    for log_path in logs:
        log_file = parse_log_file(log_path)
        run_started_values = set()
        for entry in log_file.entries:
            data = entry.data
            if "_parse_error" in data:
                add_issue("error", "LOG_JSON_INVALID", "Invalid JSON in log entry", log_path, entry.line_no)
                continue
            run_started = data.get("run_started")
            if not isinstance(run_started, str) or not ISO_UTC_REGEX.match(run_started):
                add_issue("error", "LOG_RUN_STARTED_INVALID", "run_started must be ISO 8601 UTC timestamp", log_path, entry.line_no)
            else:
                run_started_values.add(run_started)

            is_machine = data.get("written_by") == "tickets" or data.get("machine") is True
            required_fields = ["ts", "run_started", "actor_type", "actor_id", "summary"]
            for field in required_fields:
                if field not in data:
                    severity = "error" if is_machine else "warning"
                    add_issue(
                        severity,
                        "LOG_REQUIRED_FIELD_MISSING",
                        f"Missing required log field: {field}",
                        log_path,
                        entry.line_no,
                    )
            if is_machine:
                if data.get("actor_type") not in {"human", "agent"}:
                    add_issue(
                        "error",
                        "LOG_ACTOR_TYPE_INVALID",
                        "actor_type must be human or agent",
                        log_path,
                        entry.line_no,
                    )
                ts_value = data.get("ts")
                if not isinstance(ts_value, str) or not ISO_UTC_REGEX.match(ts_value):
                    add_issue(
                        "error",
                        "LOG_TS_INVALID",
                        "ts must be ISO 8601 UTC timestamp",
                        log_path,
                        entry.line_no,
                    )

        if run_started_values and len(run_started_values) > 1:
            add_issue(
                "error",
                "LOG_RUN_STARTED_MISMATCH",
                "Log file contains multiple run_started values",
                log_path,
            )
        if log_file.filename_run_started and run_started_values:
            if log_file.filename_run_started not in run_started_values:
                add_issue(
                    "warning",
                    "LOG_RUN_STARTED_FILENAME_MISMATCH",
                    "run_started does not match filename prefix",
                    log_path,
                )
    return IssueResult(issues=issues, repairs=[])


def repair_ticket(ticket: Ticket, actions: Iterable[dict[str, Any]]) -> bool:
    changed = False
    front = ticket.front_matter
    body = ticket.body
    for action in actions:
        name = action.get("action")
        params = action.get("params", {})
        if name == "add_required_sections":
            body = normalize_section_body(body)
            changed = True
        elif name == "normalize_enum":
            field = params.get("field")
            value = params.get("value")
            if field and value is not None:
                front[field] = value
                changed = True
        elif name == "normalize_created_at":
            value = params.get("value")
            if value:
                front["created_at"] = value
                changed = True
        elif name == "normalize_relationship_list":
            field = params.get("field")
            value = params.get("value")
            if field and isinstance(value, list):
                front[field] = value
                changed = True
        elif name == "set_front_matter_field":
            field = params.get("field")
            value = params.get("value")
            generate_uuid = params.get("generate_uuidv7")
            if field:
                if generate_uuid:
                    value = generate_uuidv7()
                front[field] = value
                changed = True
    if changed:
        content = "---\n" + yaml.safe_dump(front, sort_keys=False).strip() + "\n---\n" + body.lstrip()
        write_text(ticket.path, content)
    return changed
