import json
import os
import subprocess
import sys
from pathlib import Path


def run_cmd(tmp_path, *args):
    cmd = [sys.executable, "-m", "ticketslib.cli", *args]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    return subprocess.run(cmd, cwd=tmp_path, check=False, capture_output=True, text=True, env=env)


def test_init_and_new_and_validate(tmp_path):
    result = run_cmd(tmp_path, "init")
    assert result.returncode == 0
    assert (tmp_path / "tickets.md").exists()
    assert (tmp_path / "AGENTS_EXAMPLE.md").exists()
    assert (tmp_path / ".tickets").exists()

    result = run_cmd(tmp_path, "new", "--title", "Test ticket")
    assert result.returncode == 0

    result = run_cmd(tmp_path, "validate")
    assert result.returncode == 0


def test_validate_rejects_invalid_status(tmp_path):
    run_cmd(tmp_path, "init")
    run_cmd(tmp_path, "new", "--title", "Bad status")

    ticket_dir = next((tmp_path / ".tickets").iterdir())
    ticket_path = ticket_dir / "ticket.md"
    content = ticket_path.read_text(encoding="utf-8")
    ticket_path.write_text(content.replace("status: todo", "status: INVALID"), encoding="utf-8")

    result = run_cmd(tmp_path, "validate", "--issues")
    assert result.returncode == 1
    payload = json.loads(run_cmd(tmp_path, "validate", "--issues", "--format", "json").stdout)
    assert any(issue["code"] == "TICKET_STATUS_INVALID" for issue in payload["issues"])


def test_log_appends_entry(tmp_path):
    run_cmd(tmp_path, "init")
    run_cmd(tmp_path, "new", "--title", "Log me")

    ticket_dir = next((tmp_path / ".tickets").iterdir())
    ticket_id = ticket_dir.name

    result = run_cmd(
        tmp_path,
        "log",
        "--ticket",
        ticket_id,
        "--actor-type",
        "agent",
        "--actor-id",
        "Codex",
        "--summary",
        "Did work",
        "--machine",
    )
    assert result.returncode == 0

    logs_dir = ticket_dir / "logs"
    log_files = list(logs_dir.glob("*.jsonl"))
    assert log_files
    lines = log_files[0].read_text(encoding="utf-8").strip().splitlines()
    assert lines
    data = json.loads(lines[-1])
    assert data["summary"] == "Did work"
    assert data["written_by"] == "tickets"


def test_repair_adds_missing_sections(tmp_path):
    run_cmd(tmp_path, "init")
    run_cmd(tmp_path, "new", "--title", "Repair me")

    ticket_dir = next((tmp_path / ".tickets").iterdir())
    ticket_path = ticket_dir / "ticket.md"
    content = ticket_path.read_text(encoding="utf-8")
    ticket_path.write_text(content.replace("## Verification", "## Verify"), encoding="utf-8")

    result = run_cmd(tmp_path, "repair", "--ticket", str(ticket_path))
    assert result.returncode == 0
    repaired = ticket_path.read_text(encoding="utf-8")
    assert "## Verification" in repaired
