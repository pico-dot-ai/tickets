# Repo-Native Tickets

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
