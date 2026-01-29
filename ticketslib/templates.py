TICKETS_MD_TEMPLATE = """# Repo-Native Tickets

This repository uses a repo-native ticketing system designed for humans and agents.

## Overview
- Tickets live under `/.tickets/<ticket-id>/ticket.md`.
- Ticket history is stored in per-run JSONL logs under `/.tickets/<ticket-id>/logs/`.
- Use the `tickets` CLI as the integration surface for creating, validating, logging, and repairing tickets.

## Human workflow
- Create tickets with `tickets new --title "..."`.
- Update status with `tickets status` when helpful.
- Keep ticket definitions concise; use logs for work history.

## Agent workflow
Agents (including humans using agentic tools) must:
- Read `ticket.md` before starting work.
- Respect `assignment.mode` and `agent_limits`.
- Log each iteration with `tickets log --machine`.
- Include verification results (or explain why commands were not run).
- Stop when limits are reached and leave clear next steps.

## Validation
- Run `tickets validate` before and after changes.
- If issues are reported, use `tickets validate --issues` and `tickets repair`.
"""

AGENTS_EXAMPLE_TEMPLATE = """# Agent Instructions (Example)

1. Read `tickets.md` for workflow guidance.
2. Use the `tickets` CLI for all ticket operations:
   - `tickets validate --issues`
   - `tickets repair`
   - `tickets log --machine`
3. Respect `agent_limits` in ticket front matter or config.
4. Log a final summary and next steps before stopping.
"""

TICKET_TEMPLATE = """---
id: {ticket_id}
title: "{title}"
status: todo
created_at: {created_at}
---
# Ticket

## Description

## Acceptance Criteria
- [ ]

## Verification
- 
"""
