# The Piggy Bank That Says Wait a Minute

Technical repository: wait-a-minute-agent. An intent-aware security guardrail for AI agents that propose NEAR transactions.

## Implemented on this branch

- Python transaction models and policy engine: ALLOW, ASK_HUMAN, DENY.
- SQLite persistence for approval requests, execution history and audit events.
- n8n approval client: submit once, poll status, verify request ID and transaction fingerprint, fail closed on errors/timeouts.
- Flask demo UI and JSON API.
- Tests for policy decisions, SQLite single-use approvals, fingerprint tampering and API behavior.
- Telegram/n8n setup guide: docs/N8N_TELEGRAM_SETUP.md.

## Architecture

User → AI proposal → Python Guardrail → ALLOW / DENY / ASK_HUMAN → n8n Webhook → Telegram human approval → n8n status endpoint → Python verifies request ID + fingerprint → APPROVED_PENDING_EXECUTION.

The NEAR MCP server is a future controlled execution adapter. It is not connected here. No wallet signing or fund transfer is enabled.

## Run locally

Python 3.11+:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    cp .env.example .env
    python app.py

Open http://127.0.0.1:5000. Without configured n8n endpoints, human-review requests fail closed to DENY.

Run tests with pytest -q.

## n8n setup

Follow docs/N8N_TELEGRAM_SETUP.md. Configure two authenticated production webhooks:

- POST /guardrail-approval — persist a PENDING request and immediately return HTTP 202.
- GET /guardrail-status?request_id=... — return PENDING, APPROVE or DENY with the original fingerprint.

Use Telegram's Send and Wait for Response node and restrict approval to the designated human approver.

## Environment variables

See .env.example. Never commit .env, Telegram tokens, n8n credentials, NEAR private keys or wallet secrets.

## Security boundaries and limitations

- Approval is bound to a SHA-256 fingerprint of canonical transaction JSON and consumed once in SQLite.
- Human approval does not execute a transfer. The API returns APPROVED_PENDING_EXECUTION and execution_enabled=false.
- Trusted/blocked recipient sets are currently in-memory configuration; persist and administer them before production.
- intended_amount is still supplied by the caller. Production must bind it to trusted/signed intent rather than trusting an AI-provided field.
- SQLite and the n8n Data Table are separate stores. Use HTTPS, strong shared credentials, restricted Telegram approvers and monitoring.
- NEAR MCP tools, wallet signing, replay-safe on-chain execution and attack simulations are not implemented yet.

## Roadmap

1. [x] Python guardrail engine and tests
2. [x] Initial SQLite persistence and audit events
3. [x] n8n approval client and Telegram workflow setup guide
4. [ ] NEAR MCP read-only integration, then restricted testnet execution
5. [ ] Attack simulations and adversarial security tests
6. [ ] Demo video

Hackathon prototype only; not a production wallet security product.
