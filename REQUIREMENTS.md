# AI-Native Ticketing System — Requirements

## 0. Document Role

This `REQUIREMENTS.md` exists **only** to specify what Codex (or other coding agents) must implement in this repo.

All operational rules for humans and agents (how tickets are written, interpreted, and used day-to-day) MUST live in `TICKETS.md`.
`TICKETS.md` is the user-facing, repo-native “manual.” The tooling generated from this requirements doc MUST treat `TICKETS.md` as the canonical source of workflow guidance.

## 1. Purpose

Build a **repo-native ticketing system** that supports both:

- **Humans** working in normal development workflows.
- **Coding agents** (e.g., Codex Cloud) doing bounded, repeatable work with durable handoffs.
- **Humans using agentic coding tools** (Codex CLI, Claude Code, IDE integrations, etc.) who want the same “machine workflow” benefits: strict log structure, validation, iteration limits, and durable handoffs.

The **core intent** is to support coordination of **parallel agents**, including cases where multiple agents work on **different branches/versions of the same underlying issue**. The system must remain reliable under eventual-consistency workflows where the state of a ticket may have changed before a branch is merged back.

This system is **in-repo and offline-first**: it must not assume the agent sandbox has internet access. All durable state needed for coordination and handoff must live in repository files.

The system must make it easy to:

- Represent work as **tickets** stored in the repo.
- Give agents **clear scope**, **verification steps**, and **hard iteration limits** to prevent runaway behavior.
- Preserve **history** (work logs, decisions, file changes) alongside tickets (in repo-native artifacts) so future humans/agents can continue work safely.
- Support running **multiple agents in parallel** with minimal merge-conflict pain.

## 2. Problems This System Solves

### 2.1 Agent-related pain points

- Agents lose context between runs; they need a durable, repo-local memory.
- Agents can run long, churn, or loop; we need enforceable limits and required handoffs.
- Multiple agents working concurrently can produce conflicting changes; we need conventions that reduce conflicts.
- Agents often struggle to infer “done”; we need explicit acceptance criteria and verification steps.

### 2.2 Human-related pain points

- Humans need tickets that are readable and lightweight.
- Humans shouldn’t be forced to follow agent-centric workflows.
- Humans need an easy way to see current status, dependencies, and what happened previously.

### 2.3 Team / system pain points

- Work happens via eventual-consistency (PRs, delayed merges, async agents). The system must keep coordination and audit trails in-repo.
- The system should be compatible with GitHub workflows, and optionally integrable with GitHub Issues.

## 3. Goals and Non-Goals

### 3.1 Goals

- A clear, documented **ticket format**.
- Tools that:
  - create and validate tickets,
  - update ticket status,
  - append agent/human work logs in a consistent way,
  - list/filter tickets,
  - optionally visualize dependency graphs / compute critical path.
- Robust agent workflow support:
  - bounded iterations,
  - required iteration logging,
  - escalation rules when repeated attempts fail.
- A flexible, orchestration-agnostic foundation for coordinating parallel work without prescribing a specific harness, role model, or routing/ownership policy.
- A single repo-local integration surface (`tickets` CLI) that humans and agents can both use so that “machine workflow” behavior is consistent regardless of which external AI tool is used.

### 3.2 Non-Goals

- Not a full project-management suite.
- Not a mandatory replacement for GitHub Issues.
- Not a hosted web UI (may exist separately).
- No background daemons required for core functionality.
- Not a definition of how agent coordination is performed (claims/leases, arbitration, role behaviors, routing policies, etc.).

## 4. Definitions

- **Ticket**: a Markdown file representing a unit of work.
- **Agent iteration**: a single bounded attempt by an agent to make progress on a ticket.
- **Iteration limits**: enforceable constraints for agents (timebox, tool-call cap, max iterations, etc.).
- **Work log entry**: an append-only entry describing what was done in an iteration (agent) or work session (human).
- **Acceptance criteria**: explicit conditions that define “done.”
- **Verification steps**: commands or checks that confirm acceptance criteria.

## 5. Repository Layout

### 5.1 Required

- `TICKETS.md` — system overview and contributor/agent conventions.
- `/.tickets/` — directory containing one subdirectory per ticket.

### 5.2 Recommended (optional)

- `/.tickets/index.json` — generated index for fast listing/filtering (do not hand-edit).
- `/.tickets/config.yml` — repository-local defaults for tooling (optional).

## 6. Ticket File Format

### 6.1 Storage

Each ticket is stored in its own directory:

- Ticket directory: `/.tickets/<ticket-id>/`
- Ticket definition file: `/.tickets/<ticket-id>/ticket.md`
- Run logs directory: `/.tickets/<ticket-id>/logs/`

Where `<ticket-id>` is a **UUIDv7** in lowercase (canonical string form).

Notes:
- The ticket definition filename is fixed: `ticket.md` within each ticket directory.
- Tooling MUST NOT validate that the directory name and front matter `id` match (convention only).


### 6.2 Structure

Ticket files MUST be:

- Markdown document with **YAML front matter** at the top.
- Followed by a Markdown body containing sections.

Front matter MUST start at the first line and be enclosed with `---` markers:

```md
---
id: 018f0f7b-3c7c-7b8d-9f7b-2f0f9a1e2c3d
title: "Short human-readable title"
status: todo
created_at: 2026-01-28T12:00:00Z
---
# Ticket
...
```

### 6.3 Timestamp rules

- `created_at` MUST be an ISO 8601 timestamp.
- Default timezone MUST be UTC (`Z`).
- There is **no** `updated_at` field. “Last updated” is derived from the most recent entry across the run logs (see §7.4 and §9).
- Tools MUST NOT rewrite timestamps inside prior log entries.

### 6.4 Required front matter fields

- `id` (UUIDv7 string)
- `title` (string)
- `status` (enum; see §6.6)
- `created_at` (timestamp)

### 6.5 Optional front matter fields

#### 6.5.1 Assignment and mode

```yaml
assignment:
  mode: mixed   # enum: human_only | agent_only | mixed
  owner: null   # string; e.g., "@alice" or "team:core" or "agent:codex"
```

Notes:
- `mode` controls who is allowed to work the ticket.
- `owner` is informational and used for listing/triage; tools MUST NOT assume `owner` is authoritative for access control.

#### 6.5.2 Priority and labels

```yaml
priority: medium   # enum: low | medium | high | critical
labels: ["bug", "docs"]
```

#### 6.5.3 Relationships

```yaml
dependencies: ["018f...","018e..."] # list of ticket IDs
blocks: []                          # list of ticket IDs this ticket blocks
related: []                         # list of ticket IDs
```

Rules and conventions:
- These three fields (`dependencies`, `blocks`, `related`) are the only relationship fields that SHOULD be written into ticket front matter in v1.
- Relationship fields are planning metadata and SHOULD be low-churn; frequent rewrites increase merge-conflict risk for parallel agents working on different branches.
- Other relationship views (e.g., reverse edges like “blocked_by”, parent/child rollups, duplicates, supersession) SHOULD be computed by tooling from these fields and/or from run log history, and SHOULD NOT be persisted in `ticket.md`.
- When an agent changes relationships, it SHOULD also write a run log entry explaining why (see §9), including any newly created ticket IDs (see `tickets_created` in §9.2).

#### 6.5.4 Human time estimates (hours)

Human estimates are OPTIONAL and advisory.

Format:

```yaml
estimates:
  human_hours: 4
```

Rules:
- When present, the value MUST be a number representing **hours**.

#### 6.5.5 Agent iteration limits

Agent limits are OPTIONAL overrides; repos may set defaults in config.

```yaml
agent_limits:
  iteration_timebox_minutes: 20
  max_iterations: 6
  max_tool_calls: 80
  checkpoint_every_minutes: 5
```

Rules:
- These limits are **hard** for agents (see §8).
- When present, all values MUST be positive integers.

#### 6.5.6 Verification defaults

```yaml
verification:
  commands:
    - "python -m pytest"
    - "ruff check ."
```

Tools SHOULD prefer ticket-specific verification commands over global defaults.

### 6.6 Status enum and transitions

Allowed `status` values:

- `todo`
- `doing`
- `blocked`
- `done`
- `canceled`

Allowed transitions (guideline; tools may warn on unusual transitions):

- `todo` -> `doing` | `canceled`
- `doing` -> `blocked` | `done` | `canceled`
- `blocked` -> `doing` | `canceled`
- `done` -> (no transitions; immutable unless explicitly reopened by human)
- `canceled` -> (no transitions; immutable unless explicitly reopened by human)

If reopening is required, set `status: doing` and add a run log entry explaining why.

## 7. Ticket Content and Logs

### 7.1 Ticket file content (`/.tickets/<id>/ticket.md`)

Ticket files MUST be Markdown documents with YAML front matter and a body.

The ticket body MUST include these sections (order is recommended but not required):

1. `# Ticket` header (or equivalent H1)
2. `## Description`
3. `## Acceptance Criteria`
4. `## Verification`

Notes:
- The text within sections is freeform except where specified below.
- The ticket file SHOULD remain relatively stable and human-readable.

### 7.2 Description

- What is being built/fixed, context, and scope.
- Include “out of scope” notes when helpful.

### 7.3 Acceptance Criteria

Acceptance criteria MUST be a list of checkable statements.

Example:

- [ ] New CLI command `tickets validate` exits 0 on valid tickets.
- [ ] Invalid `status` causes non-zero exit and helpful error message.
- [ ] A tooling-written log entry is produced after each agent iteration.

### 7.4 Run logs (append-only, per-run files)

Each ticket MUST store history in **run log files** under its ticket directory:

- Run logs directory: `/.tickets/<ticket-id>/logs/`
- Each agent/human “run” writes to its own file: `/.tickets/<ticket-id>/logs/<run_started>-<run_id>.jsonl`
- Each line is a single JSON object (JSON Lines / JSONL).

Rationale:
- Per-run log files are highly merge-friendly: concurrent runs write to different files, avoiding conflicts at EOF.
- The ticket definition (`ticket.md`) stays readable and stable; logs stay machine-appendable.

Rules:
- Tools MUST append new entries as new JSONL lines within a given run log file.
- Tools MUST NOT rewrite or delete existing log lines.
- Humans MAY add log lines manually, but tooling should make it easy via `tickets log`.
- “Last updated” for a ticket is derived from the newest `ts` across all run log entries.

Notes:
- `run_started` is the run start time (UTC). It exists as a stable hint for processing order (e.g., tools may process newer runs first by sorting filenames by `run_started`).
- To keep filenames cross-platform and lexicographically sortable, tools SHOULD emit `run_started` in ISO 8601 basic format, e.g., `20260129T184210.123Z`.


## 8. Agent vs Human Semantics

### 8.1 Humans

- Human time estimates are advisory and used for planning.
- Humans may work without adding log entries, but doing so is discouraged.
- If a human stops mid-work, they SHOULD append a short run log entry.

### 8.2 Agents

Agents MUST:

- Read the ticket file before starting work.
- Respect `assignment.mode` (do not work tickets marked `human_only`).
- Respect agent iteration limits:
  - If any limit is reached, the agent MUST stop and append a run log entry.
- Prefer small, reviewable changes and avoid unrelated refactors.

**Mandatory stop-and-handoff behavior (agent):**

When an agent stops (success or not), it MUST:

1. Ensure the repo is left in a reasonable state (no uncommitted secret material; avoid leaving tests intentionally broken unless unavoidable and clearly documented).
2. Append a run log entry with the required structure (§9).
3. If not complete, include a clear “Next steps” list.

### 8.4 Humans using agentic coding tools

Humans may choose to use an agentic coding tool (Codex CLI, Claude Code, IDE integrations, etc.) to work tickets. When they do, they SHOULD follow the same “machine workflow” conventions as autonomous agents so that the work is auditable, merge-friendly, and resumable by other humans/agents:

- Use `tickets validate` (or `tickets validate --issues` + `tickets repair`) as a gate before and after work.
- Use `tickets log --machine` for work logs produced via the tool so that entries are strictly structured and reliably parseable.
- Use `actor_type: agent` for these tool-driven runs, even if initiated by a human.
- Set `actor_id` to identify the tool and the human initiator (convention), e.g., `codex-cli (human:@alice)` or `cursor (human:@kevin)`.
- Respect `agent_limits` when present, or repo defaults, to keep work bounded and predictable.

### 8.3 Escalation rules

If an agent reaches `max_iterations` without completion, it MUST:

- Stop further attempts on the ticket.
- Append a run log entry recommending one of:
  - tightening acceptance criteria,
  - splitting into subtickets,
  - requesting human decision on ambiguous tradeoffs.

## 9. Run Log Entry Format (`logs/<run_started>-<run_id>.jsonl`)

Each run log line MUST be a single JSON object.

### 9.1 Required fields

- `ts` (string, ISO 8601 UTC timestamp, e.g., `2026-01-28T12:34:56Z`)
- `run_started` (string, ISO 8601 UTC timestamp; the run start time for the file this entry is in)
- `actor_type` (enum: `human` | `agent`)
- `actor_id` (string; freeform, e.g., `"@alice"`, `"Codex-Cloud"`)
- `summary` (string)

### 9.2 Optional structured fields (recommended)

- `changes`
  - `files` (array of strings)
  - `commits` (array of strings)
  - `prs` (array of strings)
- `verification`
  - `commands` (array of strings)
  - `results` (string)
- `created_from` (string; parent ticket ID (UUIDv7) when this ticket was created by splitting work)
- `tickets_created` (array of strings; ticket IDs created during this run)
- `context_carried_over` (array of strings; concise list of context items copied/adapted from a parent ticket so this ticket is executable in isolation)
- `decisions` (array of strings)
- `next_steps` (array of strings)
- `blockers` (array of strings)

### 9.3 Machine marker (tooling-written vs human-written)

To support stricter validation for entries written by official tooling, entries appended by `tickets` MUST include a machine marker:

- `written_by: "tickets"`, or
- `machine: true`

Human-authored entries SHOULD omit the marker.

Notes:
- “Tooling-written” includes any entry written via the `tickets` CLI with `--machine`, including runs initiated by humans using external agentic coding tools.

### 9.4 Example log entry (tooling-written)

```json
{
  "ts": "2026-01-28T12:34:56Z",
  "run_started": "20260128T123000.000Z",
  "actor_type": "agent",
  "actor_id": "Codex-Cloud",
  "summary": "Implemented validator for ticket front matter and enums.",
  "changes": {"files": ["scripts/tickets", ".tickets/018f.../ticket.md"], "commits": ["abc123"], "prs": []},
  "verification": {"commands": ["python -m pytest", "./scripts/tickets validate"], "results": "pass"},
  "decisions": ["Used YAML front matter to keep tickets human-editable."],
  "next_steps": ["Add run log writer.", "Add CI job to run tickets validate."],
  "blockers": [],
  "written_by": "tickets"
}
```

### 9.5 Rules

- Agents MUST produce at least one log entry at the end of each agent iteration (success or not).
- Agents MUST include verification information; if commands were not run, `verification.results` MUST explain why.
- Tools MUST append; tools MUST NOT rewrite prior entries.
- Within a given run log file, all entries MUST have the same `run_started`.
- For tooling-written entries, `run_started` SHOULD match the `run_started` component of the log filename.


## 10. Concurrency and Merge Conflict Minimization

The system MUST support multiple concurrent agents.

### 10.1 Primary strategy: per-run log files under ticket directories

- Each ticket’s append-only run logs live under `/.tickets/<ticket-id>/logs/` as multiple files, one per run.
- Agents and tooling should avoid rewriting the main ticket Markdown file during normal iterations; prefer run log entries for history.

Rationale:
- Parallel agents may be operating on different branches/versions; the system must be merge-friendly even when ticket metadata changes independently on multiple branches.
- “Truth” about progress is represented primarily as append-only log history plus lightweight ticket metadata, rather than a single mutable log file that is frequently edited.


### 10.2 Conflict resolution rules

If a merge conflict occurs in a run log (`.jsonl`) file (rare; should mostly occur only when two branches modify the same run log file):

- Keep all lines from both sides.
- Preserve original `ts`, `actor_type`, and `actor_id` fields.
- Do not rewrite history to “clean it up.”

### 10.3 Optional: lightweight “lease” claiming (not required)

If implemented later, it MUST:

- Be time-bound (auto-expire).
- Never block humans from taking over.
- Avoid central lock files that create bottlenecks.

### 10.4 Ticket splitting and subtickets (recommended pattern)

Agents may discover that a ticket should be broken down (or that parallel work would be safer) and split into multiple new tickets (“subtickets”).

Recommended pattern (merge-friendly):
- Create new tickets via `tickets new` for each subtask.
- Link tickets using only `related` (and `dependencies`/`blocks` only when there is a real ordering constraint).
- Record the split decision and the newly created ticket IDs in a run log entry on the original ticket (use `tickets_created` in §9.2).
- Ensure each newly created ticket is executable in isolation:
  - carry over the minimum required context into the new ticket’s `ticket.md` body (typically `## Description`, `## Acceptance Criteria`, and `## Verification`)
  - write an initial run log entry for the new ticket capturing the creation rationale and carried-over context (use `created_from` and `context_carried_over` in §9.2 when possible)
- Avoid patterns that require repeatedly editing the original ticket’s `ticket.md` to maintain an authoritative list of subtickets, since parallel agents may conflict when updating shared metadata.

## 11. Tooling to Implement (In-Repo)

The repo MUST include a CLI tool named `tickets` (or `./scripts/tickets`), with the following commands.

Integration requirement:
- External tools (agents, IDE integrations, human-invoked agentic coding tools) SHOULD treat the `tickets` CLI as the integration surface for creating, validating, logging, and repairing tickets, rather than inventing parallel formats.

### 11.1 `tickets init`

Creates:

- `TICKETS.md` (if missing, using a template)
- `AGENTS_EXAMPLE.md` (if missing, using a template) to bootstrap agentic use of this repo-native workflow
- `/.tickets/` directory (if missing)
- optional config file if chosen

Notes:
- `AGENTS_EXAMPLE.md` is intentionally not named `AGENTS.md` to avoid unexpected behavior when this framework is copied into other repos. Users MAY copy/rename it to `AGENTS.md` if their agent harness supports it.
- The `AGENTS_EXAMPLE.md` template SHOULD instruct agents (and humans using agentic coding tools) to read `TICKETS.md` first, then use the `tickets` CLI (`validate --issues`, `repair`, `log --machine`) while respecting `agent_limits`.

### 11.2 `tickets new`

Creates a new ticket:

- Generates UUIDv7 `id`.
- Creates directory `/.tickets/<id>/`.
- Creates `/.tickets/<id>/ticket.md` from the ticket template.
- Creates `/.tickets/<id>/logs/` directory.
- Sets `created_at` to now (UTC).
- Requires a title (`--title`).

### 11.3 `tickets validate`

Validates:

- all tickets under `/.tickets/`
- or a specific ticket path/id

Options:

- `--issues` outputs a complete machine-readable report of all validation issues found (errors and warnings), including a repair plan template that can be filled in and consumed by `tickets repair` to apply fixes non-interactively.

Validation MUST check:

- front matter presence and parseability
- required fields
- UUIDv7 format for `id` field (no directory/filename matching validation)
- timestamp format
- enums (status, priority, assignment.mode)
- required body sections exist (at least headers)
- relationship fields when present:
  - validate types and UUID format for `dependencies`, `blocks`, and `related`
  - treat other relationship-like keys as invalid (they should be derived by tooling, not persisted in `ticket.md`)
- Run log entries (`/.tickets/*/logs/*.jsonl`):
  - strict validation for entries with a machine marker (`written_by: "tickets"` or `machine: true`)
  - best-effort validation (warnings by default) for entries without a machine marker
  - validate `run_started` as an ISO 8601 UTC timestamp
  - validate that all entries in a given file share the same `run_started`
  - when feasible, validate that `run_started` matches the `<run_started>` prefix of the log filename (especially for tooling-written entries)
  - when present, validate `created_from` as a UUID string and `context_carried_over` as an array of strings

#### 11.3.1 `tickets validate --issues` output format

`tickets validate --issues` MUST write a single document to stdout (or a file if `--output <path>` is supported) in YAML or JSON. YAML is recommended as the default to allow humans to edit the repair template easily.

The output MUST:
- Include all issues found (do not stop at the first error).
- Be deterministic (stable ordering) for the same repository state.
- Include a `repairs` section that can be edited and then consumed by `tickets repair` to apply changes without interactive prompts.

Minimum schema:

```yaml
schema_version: 1
generated_at: "2026-01-29T00:00:00Z"
tool: "tickets"
targets:
  - "/.tickets/..." # ids or paths that were validated
issues:
  - id: "I0001"
    severity: "error"   # error | warning
    code: "TICKET_FRONT_MATTER_INVALID"
    message: "YAML front matter could not be parsed."
    ticket_path: "/.tickets/<id>/ticket.md"
    location: {line: 1, column: 1} # optional
    details: {}                    # optional structured details
repairs:
  - id: "R0001"
    enabled: false
    safe: false
    issue_ids: ["I0001"]
    action: "set_front_matter_field"
    ticket_path: "/.tickets/<id>/ticket.md"
    params:
      field: "id"
      value: null                  # fill in, OR set generate_uuidv7: true
      generate_uuidv7: false
      update_references: null      # true/false required if changing id
```

Rules:
- `issues[*].severity: error` items correspond to problems that make the ticket invalid; warnings are informational unless the repo chooses to gate on them.
- `repairs[*]` entries MUST include all fields needed for non-interactive application, using `null` placeholders where a human or another tool must supply a value.
- `repairs[*].enabled` controls whether the repair is applied by `tickets repair`.
- If a repair requires a choice, the template MUST include explicit parameters to select a strategy (e.g., `generate_uuidv7`, `update_references`), so `tickets repair` can run in `--non-interactive` mode without prompting.

Exit codes:

- `0` success
- `1` validation errors
- `2` tooling/IO errors

### 11.4 `tickets status`

Updates ticket status:

- updates `status` in front matter
- does NOT update any `updated_at` field (none exists)
- optionally writes a one-line run log file under `/.tickets/<id>/logs/` describing the status change (`--log`, generates a new `run_id` and `run_started` unless `--run-id` is provided)

### 11.5 `tickets log`

Writes a log entry to a run log file under `/.tickets/<id>/logs/`:

- `--ticket <id|path>`
- `--actor-type human|agent`
- `--actor-id "<string>"`
- `--summary "<text>"` (or accept stdin)
- optional structured fields (changes, verification, created_from, tickets_created, context_carried_over, decisions, next_steps, blockers)
- `--machine` (when present, the tool MUST include a machine marker such as `written_by: "tickets"`)

The command MUST write exactly one JSON object as one new JSONL line.

If `--run-id` is provided, the tool MUST append to `logs/<run_started>-<run_id>.jsonl` for that run (creating it if missing). If `run_started` is not otherwise known, the tool SHOULD locate an existing file matching `*-<run_id>.jsonl`; if no file exists, it MUST choose a new `run_started` (UTC) for the created file.
If `--run-id` is omitted, the tool MUST create a new `run_id` and `run_started` (UTC) and write to `logs/<run_started>-<run_id>.jsonl`.

### 11.6 `tickets list`

Lists tickets with filters:

- status
- priority
- assignment mode
- owner
- label
- text search over title/description

Output:

- human-readable table by default
- `--json` outputs machine-readable JSON

### 11.7 `tickets repair`

Repairs common structural issues in tickets to make them valid (or closer to valid) for both humans and agents.

Goals:
- Provide an automated path to fix safe, mechanical issues (timestamps, missing sections, minor schema problems).
- Provide an interactive workflow for ambiguous or potentially disruptive changes (e.g., changing a ticket `id`).

Inputs:
- `--ticket <id|path>` (repair one ticket), or
- `--all` (repair all tickets under `/.tickets/`)

Modes:
- Default mode SHOULD be non-interactive and only apply “safe” repairs.
- `--interactive` enables prompting for decisions when multiple repair strategies exist or when a change could affect other tickets.
- `--non-interactive` forces failure (non-zero) if any repair requires a decision.
- `--issues-file <path>` consumes the output of `tickets validate --issues` and applies any `repairs[*]` where `enabled: true`. In `--non-interactive` mode, the tool MUST fail if any enabled repair has unresolved required placeholders (e.g., `null` values) or missing decision parameters.

Safe repairs (MUST be non-interactive):
- Add missing required body section headers (`# Ticket`, `## Description`, `## Acceptance Criteria`, `## Verification`) with placeholder content when absent.
- Normalize `created_at` to an ISO 8601 UTC timestamp when parseable.
- Normalize enum casing/format when unambiguous (e.g., `TODO` -> `todo`).
- Normalize relationship field types when unambiguous:
  - convert a single string to a 1-item list for `dependencies`/`blocks`/`related`
  - drop empty-string entries

Potentially disruptive repairs (MUST require explicit confirmation in `--interactive` mode; MUST fail in `--non-interactive` mode):
- Fix or replace a missing/invalid `id`:
  - MAY generate a new UUIDv7 for the ticket
  - if other tickets reference the old ID, the tool MUST offer to update references across `/.tickets/**/ticket.md`
  - the tool SHOULD NOT rewrite existing log lines to change historical IDs

Logging and safety:
- `tickets repair` MUST NOT rewrite or delete existing JSONL log lines.
- When `tickets repair` modifies any files, it SHOULD append a tooling-written run log entry describing what was repaired and why.

Exit codes:
- `0` no changes needed, or repairs applied successfully
- `1` unrepairable validation errors remain
- `2` tooling/IO errors

### 11.8 Optional: `tickets graph`

If implemented:

- outputs dependency graph (DOT/JSON)
- computes critical path using `estimates.human_hours` when present
## 12. Configuration (Optional)

If `/.tickets/config.yml` exists, it MAY define defaults:

- default agent limits
- default verification commands
- template paths

Ticket-local settings MUST override config defaults.

## 13. GitHub Integration (Optional)

Optional but recommended:

### 13.1 GitHub Action: validate tickets on PR

- Runs `tickets validate` on PRs that touch `TICKETS.md` or `/.tickets/**`.
- Fails CI on validation errors.

### 13.2 GitHub Issues compatibility

Document mapping suggestions (no sync required initially):

- Issue title <-> `title`
- Issue state <-> `status`
- Labels <-> `labels`
- Body <-> `Description + Acceptance Criteria + run logs (latest summary)`

## 14. Security and Safety Constraints

Tooling MUST:

- Avoid writing secrets into tickets or logs.
- Avoid collecting environment dumps.
- Keep logs concise and focused on engineering context.

Agent guidance (documented in `TICKETS.md`):

- Prefer minimal diffs.
- Avoid mass formatting or refactors unless required by ticket.
- Do not modify unrelated files.

## 15. Implementation Constraints

- The system MUST be implementable with **repo-local code** (no required hosted services).
- Tooling MUST run on macOS and Linux (Windows support is desirable).
- Choose one implementation language and document it in the repo (recommended: Python 3.11+).
- Dependencies SHOULD be minimal. If YAML parsing requires a library, list it explicitly and provide installation instructions.
- Provide unit tests for parsing and validation.

## 16. Acceptance Tests for the System

The implementation MUST include tests that verify:

- `tickets init` creates required structure.
- `tickets new` produces a valid ticket that passes `tickets validate`.
- `tickets validate` rejects invalid UUID/timestamps/enums/missing sections.
- `tickets repair` fixes safe mechanical issues (e.g., missing required sections, parseable timestamp normalization) and leaves a ticket passing `tickets validate` when repairable.
- `tickets log` appends a well-formed run log entry deterministically.
- Merge-conflict scenario guidance is documented (tests may simulate two log appends).

## 17. Deliverables

Codex implementation must produce:

- `TICKETS.md` template content (system overview + agent/human conventions), including guidance for humans who choose to use agentic coding tools to follow the “machine workflow” conventions in §8.4.
- `AGENTS_EXAMPLE.md` template content that bootstraps agent harnesses to read `TICKETS.md` and use the `tickets` CLI.
- Ticket template content (or embedded template in CLI).
- CLI tool with commands in §11.
- Validation + tests in §16.
- Optional: GitHub Action in §13.

## 18. Open Questions (to resolve later)

- Should `tickets graph` be required for v1, or deferred?
- Do we want a generated `/.tickets/index.json` in v1, or rely on `tickets list` only?
- Should status transitions be enforced strictly (hard error) or as warnings?
