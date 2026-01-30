from pathlib import Path
from typing import List, Dict, Any

import yaml

from . import util, validation


def load_issues_file(path: Path) -> Dict[str, Any]:
    return yaml.safe_load(path.read_text()) or {}


def apply_repairs(repairs: List[Dict[str, Any]], non_interactive: bool = False) -> List[str]:
    applied = []
    for rep in repairs:
        if not rep.get("enabled"):
            continue
        action = rep.get("action")
        params = rep.get("params", {})
        ticket_path = Path(rep.get("ticket_path", ""))

        if action == "set_front_matter_field":
            field = params.get("field")
            value = params.get("value")
            if value is None and params.get("generate_uuidv7"):
                value = util.new_uuidv7()
            if value is None:
                if non_interactive:
                    raise RuntimeError(f"Repair needs value for {field}")
                value = input(f"Value for {field}: ").strip()
            _set_front_matter_field(ticket_path, field, value)
            applied.append(f"{ticket_path}: set {field}")

        elif action == "add_sections":
            _add_missing_sections(ticket_path)
            applied.append(f"{ticket_path}: added missing sections")

        elif action == "normalize_created_at":
            _normalize_created_at(ticket_path)
            applied.append(f"{ticket_path}: normalized created_at")

        else:
            if non_interactive:
                raise RuntimeError(f"Unsupported repair action {action}")
    return applied


def _set_front_matter_field(ticket_path: Path, field: str, value: Any):
    fm, body = util.load_ticket(ticket_path)
    fm[field] = value
    util.write_ticket(ticket_path, fm, body)


def _add_missing_sections(ticket_path: Path):
    fm, body = util.load_ticket(ticket_path)
    sections = ["# Ticket", "## Description", "## Acceptance Criteria", "## Verification"]
    new_body = body
    for sec in sections:
        if sec not in new_body:
            new_body += f"\n{sec}\n(fill in)\n"
    util.write_ticket(ticket_path, fm, new_body)


def _normalize_created_at(ticket_path: Path):
    fm, body = util.load_ticket(ticket_path)
    val = fm.get("created_at")
    if not isinstance(val, str) or util.parse_iso(val) is None:
        fm["created_at"] = util.iso8601(util.now_utc())
        util.write_ticket(ticket_path, fm, body)
