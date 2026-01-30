import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import yaml

from . import templates, util, validation, repair, listing


def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def build_parser():
    p = argparse.ArgumentParser(prog="tickets", description="Repo-native ticketing CLI")
    sub = p.add_subparsers(dest="command", required=True)

    # init
    sp = sub.add_parser("init", help="Initialize tickets structure")
    sp.set_defaults(func=cmd_init)

    # new
    sp = sub.add_parser("new", help="Create new ticket")
    sp.add_argument("--title", required=True)
    sp.set_defaults(func=cmd_new)

    # validate
    sp = sub.add_parser("validate", help="Validate tickets")
    sp.add_argument("--ticket", help="Ticket id or path")
    sp.add_argument("--issues", action="store_true", help="Output machine-readable issues/repairs")
    sp.add_argument("--output", help="Output path for issues report")
    sp.set_defaults(func=cmd_validate)

    # status
    sp = sub.add_parser("status", help="Update ticket status")
    sp.add_argument("--ticket", required=True)
    sp.add_argument("--status", required=True, choices=["todo", "doing", "blocked", "done", "canceled"])
    sp.add_argument("--log", action="store_true", help="Write a status-change log entry")
    sp.add_argument("--run-id")
    sp.add_argument("--run-started")
    sp.set_defaults(func=cmd_status)

    # log
    sp = sub.add_parser("log", help="Append a run log entry")
    sp.add_argument("--ticket", required=True)
    sp.add_argument("--run-id")
    sp.add_argument("--run-started")
    sp.add_argument("--actor-type", required=True, choices=["human", "agent"])
    sp.add_argument("--actor-id", required=True)
    sp.add_argument("--summary", required=True)
    sp.add_argument("--machine", action="store_true")
    sp.add_argument("--changes", nargs="*")
    sp.add_argument("--decisions", nargs="*")
    sp.add_argument("--next-steps", nargs="*")
    sp.add_argument("--blockers", nargs="*")
    sp.add_argument("--tickets-created", nargs="*")
    sp.add_argument("--created-from")
    sp.add_argument("--context-carried-over", nargs="*")
    sp.add_argument("--verification-commands", nargs="*")
    sp.add_argument("--verification-results")
    sp.set_defaults(func=cmd_log)

    # list
    sp = sub.add_parser("list", help="List tickets")
    sp.add_argument("--status")
    sp.add_argument("--priority")
    sp.add_argument("--mode")
    sp.add_argument("--owner")
    sp.add_argument("--label")
    sp.add_argument("--text")
    sp.add_argument("--json", dest="json_out", action="store_true")
    sp.set_defaults(func=cmd_list)

    # repair
    sp = sub.add_parser("repair", help="Repair tickets")
    sp.add_argument("--ticket")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--issues-file")
    sp.add_argument("--interactive", action="store_true")
    sp.add_argument("--non-interactive", action="store_true")
    sp.set_defaults(func=cmd_repair)

    # graph (optional placeholder)
    sp = sub.add_parser("graph", help="Dependency graph (optional)")
    sp.set_defaults(func=cmd_graph)

    return p


# Commands


def cmd_init(args):
    util.ensure_dir(util.tickets_dir())
    # TICKETS.md
    tm = util.repo_root() / "TICKETS.md"
    if not tm.exists():
        tm.write_text(templates.TICKETS_MD_TEMPLATE)
    # AGENTS_EXAMPLE.md
    am = util.repo_root() / "AGENTS_EXAMPLE.md"
    if not am.exists():
        am.write_text(templates.AGENTS_EXAMPLE_TEMPLATE)
    print("Initialized.")
    return 0


def cmd_new(args):
    util.ensure_dir(util.tickets_dir())
    ticket_id = util.new_uuidv7().lower()
    tdir = util.tickets_dir() / ticket_id
    util.ensure_dir(tdir / "logs")
    fm = {
        "id": ticket_id,
        "title": args.title,
        "status": "todo",
        "created_at": util.iso8601(util.now_utc()),
    }
    body = templates.TICKET_TEMPLATE_BODY
    util.write_ticket(tdir / "ticket.md", fm, body)
    print(ticket_id)
    return 0


def cmd_validate(args):
    tickets = validation.collect_ticket_paths(args.ticket)
    issues_all: List[Dict[str, Any]] = []
    for tpath in tickets:
        issues, fm, body = validation.validate_ticket(tpath)
        issues_all.extend(issues)
        logs_dir = tpath.parent / "logs"
        if logs_dir.exists():
            for log_file in sorted(logs_dir.glob("*.jsonl")):
                issues_all.extend(validation.validate_run_log(log_file, machine_strict_default=False))
    # assign deterministic ids
    for idx, issue in enumerate(issues_all, start=1):
        issue.setdefault("id", f"I{idx:04d}")
    if args.issues:
        report = {
            "schema_version": 1,
            "generated_at": util.iso8601(util.now_utc()),
            "tool": "tickets",
            "targets": [str(p) for p in tickets],
            "issues": issues_all,
            "repairs": build_repairs_from_issues(issues_all),
        }
        out = yaml.safe_dump(report, sort_keys=False)
        if args.output:
            Path(args.output).write_text(out)
        else:
            sys.stdout.write(out)
    else:
        for issue in issues_all:
            print(f"{issue.get('severity','?').upper()}: {issue.get('message')} ({issue.get('ticket_path') or issue.get('log')})")
    return 0 if not [i for i in issues_all if i["severity"] == "error"] else 1


def build_repairs_from_issues(issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    repairs = []
    seen = set()
    for issue in issues:
        code = issue.get("code")
        path = issue.get("ticket_path")
        if not path:
            continue
        key = (code, path)
        if key in seen:
            continue
        seen.add(key)
        if code in ["MISSING_SECTION"]:
            repairs.append(
                {"id": f"R{len(repairs)+1:04d}", "enabled": False, "safe": True, "issue_ids": [issue.get("id", "")], "action": "add_sections", "ticket_path": path, "params": {}}
            )
        elif code in ["CREATED_AT_INVALID", "MISSING_CREATED_AT"]:
            repairs.append(
                {"id": f"R{len(repairs)+1:04d}", "enabled": False, "safe": True, "issue_ids": [issue.get("id", "")], "action": "normalize_created_at", "ticket_path": path, "params": {}}
            )
        elif code in ["ID_NOT_UUIDV7", "MISSING_ID"]:
            repairs.append(
                {
                    "id": f"R{len(repairs)+1:04d}",
                    "enabled": False,
                    "safe": False,
                    "issue_ids": [issue.get("id", "")],
                    "action": "set_front_matter_field",
                    "ticket_path": path,
                    "params": {"field": "id", "value": None, "generate_uuidv7": True, "update_references": None},
                }
            )
    return repairs


def resolve_ticket_path(ticket_ref: str) -> Path:
    root = util.tickets_dir()
    p = Path(ticket_ref)
    if p.exists():
        if p.is_dir():
            return p / "ticket.md"
        return p
    candidate = root / ticket_ref / "ticket.md"
    if candidate.exists():
        return candidate
    raise SystemExit(f"Ticket not found: {ticket_ref}")


def cmd_status(args):
    tpath = resolve_ticket_path(args.ticket)
    fm, body = util.load_ticket(tpath)
    fm["status"] = args.status
    util.write_ticket(tpath, fm, body)
    if args.log:
        run_id = args.run_id or util.new_uuidv7()
        run_started = args.run_started or util.iso_basic(util.now_utc())
        log_entry = {
            "ts": util.iso8601(util.now_utc()),
            "run_started": run_started.replace(" ", ""),
            "actor_type": "human",
            "actor_id": "status-change",
            "summary": f"Status set to {args.status}",
            "written_by": "tickets",
        }
        log_path = tpath.parent / "logs" / f"{run_started}-{run_id}.jsonl"
        util.append_jsonl(log_path, log_entry)
    return 0


def cmd_log(args):
    tpath = resolve_ticket_path(args.ticket)
    run_id = args.run_id or util.new_uuidv7()
    run_started = args.run_started or util.iso_basic(util.now_utc())
    entry: Dict[str, Any] = {
        "ts": util.iso8601(util.now_utc()),
        "run_started": run_started.replace(" ", ""),
        "actor_type": args.actor_type,
        "actor_id": args.actor_id,
        "summary": args.summary,
    }
    if args.machine:
        entry["written_by"] = "tickets"
    if args.changes:
        entry["changes"] = {"files": args.changes}
    if args.decisions:
        entry["decisions"] = args.decisions
    if args.next_steps:
        entry["next_steps"] = args.next_steps
    if args.blockers:
        entry["blockers"] = args.blockers
    if args.tickets_created:
        entry["tickets_created"] = args.tickets_created
    if args.created_from:
        entry["created_from"] = args.created_from
    if args.context_carried_over:
        entry["context_carried_over"] = args.context_carried_over
    if args.verification_commands or args.verification_results:
        entry["verification"] = {"commands": args.verification_commands or [], "results": args.verification_results or ""}

    log_path = tpath.parent / "logs" / f"{run_started}-{run_id}.jsonl"
    util.append_jsonl(log_path, entry)
    return 0


def cmd_list(args):
    filters = {k: getattr(args, k) for k in ["status", "priority", "mode", "owner", "label", "text"]}
    rows = listing.list_tickets(filters)
    if args.json_out:
        json.dump(rows, sys.stdout, indent=2)
        return 0
    if not rows:
        print("No tickets.")
        return 0
    headers = ["id", "title", "status", "priority", "owner", "mode", "last_updated"]
    print(" | ".join(headers))
    for r in rows:
        print(" | ".join(str(r.get(h, "")) for h in headers))
    return 0


def cmd_repair(args):
    non_interactive = args.non_interactive
    if args.issues_file:
        issues_data = repair.load_issues_file(Path(args.issues_file))
        repairs = issues_data.get("repairs", [])
        changes = repair.apply_repairs(repairs, non_interactive=non_interactive)
        for c in changes:
            print(c)
        return 0 if changes else 1
    targets = []
    if args.ticket:
        targets = [resolve_ticket_path(args.ticket)]
    elif args.all or not args.ticket:
        targets = validation.collect_ticket_paths(None)
    changed = []
    for tpath in targets:
        issues, fm, body = validation.validate_ticket(tpath)
        need_sections = any(i["code"] == "MISSING_SECTION" for i in issues)
        bad_created = any(i["code"] == "CREATED_AT_INVALID" for i in issues)
        if need_sections:
            repair._add_missing_sections(tpath)  # type: ignore
            changed.append(f"{tpath}: add sections")
        if bad_created:
            repair._normalize_created_at(tpath)  # type: ignore
            changed.append(f"{tpath}: normalize created_at")
    for c in changed:
        print(c)
    return 0 if changed else 1


def cmd_graph(args):
    print("tickets graph: not implemented in this version.")
    return 0
