# Implementation Plan for Repo-Native AI Ticketing System

## 0. Principles
- Keep everything repo-local and offline-first.
- Favor merge-friendly artifacts (per-run JSONL logs, minimal churn in `ticket.md`).
- Make the `tickets` CLI the single integration surface for humans, agents, and agentic tools.

## 1. Bootstrap & Templates
1.1 Implement `tickets init`:
  - Create `tickets.md` from template.
  - Create `/.tickets/` and optional `config.yml`.
  - Create `AGENTS_EXAMPLE.md` from template (with instructions to read `tickets.md`, use CLI, respect `agent_limits`).
1.2 Provide ticket template (front matter + required sections) embedded or as file.
1.3 Provide `tickets.md` template content (human + agent conventions, machine workflow guidance).

## 2. Data Model & Parsing
2.1 Ticket parser:
  - YAML front matter (required/optional fields, enums, UUIDv7 validation, ISO8601 timestamps).
  - Body section presence (`# Ticket`, `## Description`, `## Acceptance Criteria`, `## Verification`).
2.2 Log parser:
  - JSONL per run; filename `<run_started>-<run_id>.jsonl`.
  - Required fields: `ts`, `run_started`, `actor_type`, `actor_id`, `summary`, machine marker rules.
  - Optional structured fields incl. `tickets_created`, `created_from`, `context_carried_over`, etc.
2.3 Validation helpers for relationship fields and agent_limits, verification commands, etc.

## 3. CLI Implementation (`tickets`)
3.1 `tickets init`
  - Idempotent creation of templates/dirs.
3.2 `tickets new`
  - Generate UUIDv7 id, `created_at` now (UTC), create ticket dir, `ticket.md`, `logs/`.
3.3 `tickets validate`
  - Validate one/all tickets; strict vs best-effort for logs.
  - `--issues`: produce machine-readable report with `issues` + editable `repairs` plan.
  - Exit codes 0/1/2.
3.4 `tickets status`
  - Update status, optional log (`--log`, new run by default).
3.5 `tickets log`
  - Append one JSON object to specified/auto run file; support `--machine`, structured fields, `--run-id`, `--run-started`.
3.6 `tickets list`
  - Filter by status/priority/assignment/owner/labels/text; output table or `--json`.
3.7 `tickets repair`
  - Safe auto-fixes; interactive/disruptive fixes gated.
  - Accept `--issues-file` produced by `validate --issues`; honor `enabled` repairs, fail if unresolved placeholders in non-interactive mode.
3.8 Optional `tickets graph` (defer unless time).

## 4. UUIDv7, Time, and File Naming
4.1 Use a UUIDv7 library or implement generator; ensure lowercase.
4.2 Timestamps: ISO8601 UTC (`Z`); `run_started` in filename uses ISO basic (`YYYYMMDDTHHMMSS.mmmZ`).
4.3 Enforce consistent serialization/parsing across commands.

## 5. Repair & Issues Workflow
5.1 Define issue codes/severities; map validators to issue objects.
5.2 Generate repair plan entries with explicit params (`generate_uuidv7`, `update_references`, etc.).
5.3 Implement safe repairs (add headers, normalize enums, timestamps, relationship list coercion).
5.4 Implement disruptive repairs with confirmation or prefilled decisions from `--issues-file`.

## 6. Logging Behavior & Merge Safety
6.1 Always append; never rewrite/delete log lines.
6.2 Enforce same `run_started` within a file; optionally check filename match.
6.3 Machine marker required for tooling-written entries; humans optional.
6.4 Provide guidance for human-invoked agentic tools (use `--machine`, `actor_type: agent`, `actor_id` convention).

## 7. Configuration
7.1 Optional `/.tickets/config.yml` for defaults (agent_limits, verification commands, templates).
7.2 Ticket-local values override config.

## 8. Tests
8.1 Unit tests for parsers/validators (tickets, logs, relationships, UUID/timestamp).
8.2 CLI tests:
  - `init` creates structure.
  - `new` creates valid ticket passing `validate`.
  - `validate` rejects bad UUID/timestamps/enums/missing sections.
  - `log` appends well-formed entry deterministically.
  - `repair` fixes safe issues and yields valid tickets.
  - Merge-conflict guidance (simulate two log appends) if feasible.
8.3 (Optional) snapshot/CLI golden tests for `--issues` output.

## 9. Tooling & Packaging
9.1 Choose language (likely Python 3.11+); minimal deps (PyYAML, uuidv7 lib, rich/tabulate for output).
9.2 Provide entrypoint script `./scripts/tickets` (CLI).
9.3 Ensure cross-platform paths and no network dependency.

## 10. Docs & Samples
10.1 Fill `tickets.md` template with human/agent guidance and machine workflow tips.
10.2 Provide example ticket in `/.tickets/` (optional) and sample logs.
10.3 Document `AGENTS_EXAMPLE.md` template content.
10.4 README points to REQUIREMENTS and quickstart (`tickets init`).

## 11. CI / Quality (optional but recommended)
11.1 Add formatting/lint targets if lightweight (ruff/black) without over-scoping.
11.2 Add GitHub Action for `tickets validate` on PRs touching tickets files (if time).

## 12. Rollout Steps
12.1 Implement core library (parsing/validation).
12.2 Implement CLI commands incrementally (init → new → validate → log/status → list → repair).
12.3 Add templates (`tickets.md`, ticket template, AGENTS_EXAMPLE.md).
12.4 Write tests; iterate until green.
12.5 Final docs pass (README, inline CLI help).
