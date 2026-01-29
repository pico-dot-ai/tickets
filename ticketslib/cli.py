import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml

from ticketslib import templates
from ticketslib.ticketing import (
    IssueResult,
    load_ticket,
    find_tickets,
    validate_ticket,
    validate_logs,
    repair_ticket,
)
from ticketslib.utils import (
    append_jsonl,
    ensure_dir,
    format_iso_utc,
    generate_uuidv7,
    parse_run_started_filename,
    utc_now,
    write_text,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tickets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")

    new_parser = subparsers.add_parser("new")
    new_parser.add_argument("--title", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--ticket")
    validate_parser.add_argument("--issues", action="store_true")
    validate_parser.add_argument("--output")
    validate_parser.add_argument("--format", choices=["yaml", "json"], default="yaml")

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--ticket", required=True)
    status_parser.add_argument("--status", required=True)
    status_parser.add_argument("--log", action="store_true")
    status_parser.add_argument("--run-id")

    log_parser = subparsers.add_parser("log")
    log_parser.add_argument("--ticket", required=True)
    log_parser.add_argument("--actor-type", required=True, choices=["human", "agent"])
    log_parser.add_argument("--actor-id", required=True)
    log_parser.add_argument("--summary")
    log_parser.add_argument("--machine", action="store_true")
    log_parser.add_argument("--run-id")
    log_parser.add_argument("--run-started")
    log_parser.add_argument("--changes-file", action="append", default=[])
    log_parser.add_argument("--changes-commit", action="append", default=[])
    log_parser.add_argument("--changes-pr", action="append", default=[])
    log_parser.add_argument("--verification-command", action="append", default=[])
    log_parser.add_argument("--verification-results")
    log_parser.add_argument("--created-from")
    log_parser.add_argument("--tickets-created", action="append", default=[])
    log_parser.add_argument("--context-carried-over", action="append", default=[])
    log_parser.add_argument("--decision", action="append", default=[])
    log_parser.add_argument("--next-step", action="append", default=[])
    log_parser.add_argument("--blocker", action="append", default=[])

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--status")
    list_parser.add_argument("--priority")
    list_parser.add_argument("--assignment-mode")
    list_parser.add_argument("--owner")
    list_parser.add_argument("--label")
    list_parser.add_argument("--text")
    list_parser.add_argument("--json", action="store_true")

    repair_parser = subparsers.add_parser("repair")
    repair_parser.add_argument("--ticket")
    repair_parser.add_argument("--all", action="store_true")
    repair_parser.add_argument("--interactive", action="store_true")
    repair_parser.add_argument("--non-interactive", action="store_true")
    repair_parser.add_argument("--issues-file")

    return parser


def repo_root() -> str:
    return os.getcwd()


def tickets_root() -> str:
    return os.path.join(repo_root(), ".tickets")


def resolve_ticket_path(ticket: str) -> str:
    if os.path.isfile(ticket):
        return ticket
    if os.path.isdir(ticket):
        return os.path.join(ticket, "ticket.md")
    return os.path.join(tickets_root(), ticket, "ticket.md")


def run_init() -> int:
    ensure_dir(tickets_root())
    if not os.path.exists("tickets.md"):
        write_text("tickets.md", templates.TICKETS_MD_TEMPLATE)
    if not os.path.exists("AGENTS_EXAMPLE.md"):
        write_text("AGENTS_EXAMPLE.md", templates.AGENTS_EXAMPLE_TEMPLATE)
    return 0


def run_new(args: argparse.Namespace) -> int:
    ticket_id = generate_uuidv7()
    ticket_dir = os.path.join(tickets_root(), ticket_id)
    ensure_dir(ticket_dir)
    ensure_dir(os.path.join(ticket_dir, "logs"))
    content = templates.TICKET_TEMPLATE.format(
        ticket_id=ticket_id,
        title=args.title,
        created_at=format_iso_utc(utc_now()),
    )
    write_text(os.path.join(ticket_dir, "ticket.md"), content)
    return 0


def run_validate(args: argparse.Namespace) -> int:
    root = repo_root()
    targets = []
    if args.ticket:
        targets = [resolve_ticket_path(args.ticket)]
    else:
        targets = find_tickets(root)

    all_issues: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    for ticket_path in targets:
        ticket_dir = os.path.dirname(ticket_path)
        try:
            ticket = load_ticket(ticket_path)
        except Exception as exc:  # noqa: BLE001
            issue = {
                "id": f"I{len(all_issues) + 1:04d}",
                "severity": "error",
                "code": "TICKET_LOAD_FAILED",
                "message": str(exc),
                "ticket_path": ticket_path,
            }
            all_issues.append(issue)
            continue
        ticket_result = validate_ticket(ticket)
        log_result = validate_logs(ticket_dir)
        for issue in ticket_result.issues + log_result.issues:
            all_issues.append(issue.to_dict())
        repairs.extend(ticket_result.repairs)

    if args.issues:
        payload = {
            "schema_version": 1,
            "generated_at": format_iso_utc(utc_now()),
            "tool": "tickets",
            "targets": targets,
            "issues": all_issues,
            "repairs": repairs,
        }
        output = yaml.safe_dump(payload, sort_keys=False)
        if args.format == "json":
            output = json.dumps(payload, indent=2)
        if args.output:
            write_text(args.output, output)
        else:
            print(output)
    if any(issue["severity"] == "error" for issue in all_issues):
        return 1
    return 0


def run_status(args: argparse.Namespace) -> int:
    ticket_path = resolve_ticket_path(args.ticket)
    ticket = load_ticket(ticket_path)
    ticket.front_matter["status"] = args.status
    content = "---\n" + yaml.safe_dump(ticket.front_matter, sort_keys=False).strip() + "\n---\n" + ticket.body.lstrip()
    write_text(ticket.path, content)
    if args.log:
        run_id = args.run_id or generate_uuidv7()
        run_started_iso = format_iso_utc(utc_now())
        run_started_basic = run_started_iso.replace("-", "").replace(":", "")
        log_dir = os.path.join(os.path.dirname(ticket_path), "logs")
        ensure_dir(log_dir)
        log_path = os.path.join(log_dir, f"{run_started_basic}-{run_id}.jsonl")
        entry = {
            "ts": format_iso_utc(utc_now()),
            "run_started": run_started_iso,
            "actor_type": "human",
            "actor_id": "tickets",
            "summary": f"Status set to {args.status}",
            "written_by": "tickets",
        }
        append_jsonl(log_path, entry)
    return 0


def run_log(args: argparse.Namespace) -> int:
    ticket_path = resolve_ticket_path(args.ticket)
    ticket_dir = os.path.dirname(ticket_path)
    logs_dir = os.path.join(ticket_dir, "logs")
    ensure_dir(logs_dir)

    run_id = args.run_id or generate_uuidv7()
    run_started = args.run_started
    log_file = None
    if run_id and not run_started:
        for filename in os.listdir(logs_dir):
            if filename.endswith(f"-{run_id}.jsonl"):
                parsed = parse_run_started_filename(filename)
                if parsed:
                    run_started = parsed[0]
                    log_file = os.path.join(logs_dir, filename)
                    break
    if not run_started:
        run_started = format_iso_utc(utc_now())
        run_started_basic = run_started.replace("-", "").replace(":", "")
        log_file = os.path.join(logs_dir, f"{run_started_basic}-{run_id}.jsonl")
    if not log_file:
        run_started_basic = run_started.replace("-", "").replace(":", "")
        log_file = os.path.join(logs_dir, f"{run_started_basic}-{run_id}.jsonl")

    summary = args.summary
    if summary is None:
        summary = sys.stdin.read().strip()
    if not summary:
        raise SystemExit("summary is required (use --summary or stdin)")

    entry: dict[str, Any] = {
        "ts": format_iso_utc(utc_now()),
        "run_started": run_started,
        "actor_type": args.actor_type,
        "actor_id": args.actor_id,
        "summary": summary,
    }
    changes = {}
    if args.changes_file:
        changes["files"] = args.changes_file
    if args.changes_commit:
        changes["commits"] = args.changes_commit
    if args.changes_pr:
        changes["prs"] = args.changes_pr
    if changes:
        entry["changes"] = changes
    verification = {}
    if args.verification_command:
        verification["commands"] = args.verification_command
    if args.verification_results:
        verification["results"] = args.verification_results
    if verification:
        entry["verification"] = verification
    if args.created_from:
        entry["created_from"] = args.created_from
    if args.tickets_created:
        entry["tickets_created"] = args.tickets_created
    if args.context_carried_over:
        entry["context_carried_over"] = args.context_carried_over
    if args.decision:
        entry["decisions"] = args.decision
    if args.next_step:
        entry["next_steps"] = args.next_step
    if args.blocker:
        entry["blockers"] = args.blocker
    if args.machine:
        entry["written_by"] = "tickets"

    append_jsonl(log_file, entry)
    return 0


def run_list(args: argparse.Namespace) -> int:
    ticket_paths = find_tickets(repo_root())
    rows = []
    for path in ticket_paths:
        ticket = load_ticket(path)
        front = ticket.front_matter
        title = front.get("title", "")
        status = front.get("status", "")
        priority = front.get("priority", "")
        assignment = front.get("assignment", {}) if isinstance(front.get("assignment"), dict) else {}
        owner = assignment.get("owner", "")
        mode = assignment.get("mode", "")
        labels = front.get("labels", []) if isinstance(front.get("labels"), list) else []
        description = ticket.body

        if args.status and status != args.status:
            continue
        if args.priority and priority != args.priority:
            continue
        if args.assignment_mode and mode != args.assignment_mode:
            continue
        if args.owner and owner != args.owner:
            continue
        if args.label and args.label not in labels:
            continue
        if args.text and args.text.lower() not in (title + " " + description).lower():
            continue

        rows.append(
            {
                "id": front.get("id", ""),
                "title": title,
                "status": status,
                "priority": priority,
                "owner": owner,
                "path": path,
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2))
        return 0

    headers = ["id", "title", "status", "priority", "owner"]
    col_widths = {header: len(header) for header in headers}
    for row in rows:
        for header in headers:
            col_widths[header] = max(col_widths[header], len(str(row.get(header, ""))))

    line = "  ".join(header.ljust(col_widths[header]) for header in headers)
    print(line)
    print("  ".join("-" * col_widths[header] for header in headers))
    for row in rows:
        print("  ".join(str(row.get(header, "")).ljust(col_widths[header]) for header in headers))
    return 0


def run_repair(args: argparse.Namespace) -> int:
    if args.ticket:
        targets = [resolve_ticket_path(args.ticket)]
    elif args.all:
        targets = find_tickets(repo_root())
    elif args.issues_file:
        targets = []
    else:
        raise SystemExit("Provide --ticket, --all, or --issues-file")

    if args.issues_file:
        issues_data = yaml.safe_load(Path(args.issues_file).read_text(encoding="utf-8"))
        repairs = issues_data.get("repairs", [])
        pending = [repair for repair in repairs if repair.get("enabled")]
        if args.non_interactive:
            for repair in pending:
                params = repair.get("params", {})
                if any(value is None for value in params.values()):
                    raise SystemExit("Repair requires interactive input")
        changed = False
        for repair in pending:
            ticket_path = repair.get("ticket_path")
            if not ticket_path:
                continue
            ticket = load_ticket(ticket_path)
            changed |= repair_ticket(ticket, [repair])
        return 0 if changed else 0

    changed_any = False
    for ticket_path in targets:
        ticket = load_ticket(ticket_path)
        result = validate_ticket(ticket)
        safe_repairs = [repair for repair in result.repairs if repair.get("safe")]
        if not safe_repairs:
            continue
        if args.non_interactive and any(repair.get("params", {}).get("value") is None for repair in safe_repairs):
            raise SystemExit("Repair requires interactive input")
        if args.interactive:
            confirm = input(f"Apply {len(safe_repairs)} repairs to {ticket_path}? [y/N]: ").strip().lower()
            if confirm != "y":
                continue
        changed = repair_ticket(ticket, safe_repairs)
        changed_any = changed_any or changed
    return 0 if not changed_any else 0


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        return run_init()
    if args.command == "new":
        return run_new(args)
    if args.command == "validate":
        return run_validate(args)
    if args.command == "status":
        return run_status(args)
    if args.command == "log":
        return run_log(args)
    if args.command == "list":
        return run_list(args)
    if args.command == "repair":
        return run_repair(args)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
