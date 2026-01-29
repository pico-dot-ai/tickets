import json
import os
import random
import re
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

UUID_V7_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-7[0-9a-f]{3}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

ISO_UTC_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")

BASIC_RUN_STARTED_REGEX = re.compile(
    r"^(\d{8}T\d{6}(?:\.\d{1,6})?Z)-([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$"
)


def generate_uuidv7() -> str:
    ts_ms = int(time.time() * 1000)
    rand_a = random.getrandbits(12)
    rand_b = random.getrandbits(62)
    value = (ts_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    return str(uuid.UUID(int=value))


def is_uuidv7(value: str) -> bool:
    if not UUID_V7_REGEX.match(value):
        return False
    try:
        parsed = uuid.UUID(value)
    except ValueError:
        return False
    return parsed.version == 7 and parsed.variant == uuid.RFC_4122


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso_utc(value: str) -> datetime | None:
    if not ISO_UTC_REGEX.match(value):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def parse_run_started_filename(filename: str) -> tuple[str, str] | None:
    match = BASIC_RUN_STARTED_REGEX.match(filename)
    if not match:
        return None
    return match.group(1), match.group(2)


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def write_text(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def append_jsonl(path: str, payload: dict[str, Any]) -> None:
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def unique_preserve(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


@dataclass
class Issue:
    issue_id: str
    severity: str
    code: str
    message: str
    ticket_path: str | None = None
    location: dict[str, Any] | None = None
    details: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.issue_id,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
        }
        if self.ticket_path is not None:
            payload["ticket_path"] = self.ticket_path
        if self.location:
            payload["location"] = self.location
        if self.details:
            payload["details"] = self.details
        return payload
