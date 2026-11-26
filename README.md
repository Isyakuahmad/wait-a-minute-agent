# The Piggy Bank That Says Wait a Minute

Technical repository: wait-a-minute-agent. An intent-aware security guardrail for AI agents that propose NEAR transactions.

## Implemented on this branch

- Python transaction models and policy engine: ALLOW, ASK_HUMAN, DENY.
- SQLite persistence for trusted spending authorizations, approval requests and audit events.
- Independently stored authorization limits bound to agent, recipient, asset, network and expiry.
- Single-use, revocable authorizations; amount/recipient/agent/network substitution and replay are rejected.
- n8n approval client verifies request ID and transaction fingerprint and fails closed on errors/timeouts.
- Flask demo UI and JSON API.
- Tests for authorization enforcement, replay prevention, fingerprint tampering and API behavior.
- Telegram/n8n setup guide: docs/N8N_TELEGRAM_SETUP.md.

## Architecture

Trusted operator authorization → AI transaction proposal → Python Guardrail → ALLOW / DENY / ASK_HUMAN → n8n human approval → fingerprint verification → APPROVED_PENDING_EXECUTION.

The agent supplies an authorization ID but cannot create or enlarge the authorization through the transaction API. The authorization is created through the trusted local/operator store interface, separately from agent input. The intended_amount field is informational only and never determines spending authority.

The NEAR MCP server is a future controlled execution adapter. It is not connected here. No wallet signing or fund transfer is enabled.

## Run locally

Python 3.11+:

    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    cp .env.example .env
    python run.py

Open http://127.0.0.1:5000. Without configured n8n endpoints, human-review requests fail closed to DENY.

Run tests with pytest -q.

## Trusted operator authorization CLI

Create and manage spending authorizations from the trusted operator's local terminal.
This CLI is deliberately separate from the agent-facing transaction API; do not expose
it as a web endpoint or run it in an untrusted environment with database access.

Create a one-time authorization (defaults to NEAR on testnet, expiring in 15 minutes):

    python -m app.operator_cli --db data/guardrail.db create \
      --authorization-id auth-001 \
      --agent-id demo-agent \
      --recipient seller.testnet \
      --max-amount 2.5

Set a longer expiry or different asset/network explicitly:

    python -m app.operator_cli --db data/guardrail.db create \
      --authorization-id auth-002 \
      --agent-id demo-agent \
      --recipient buyer.testnet \
      --max-amount 5 \
      --asset NEAR \
      --network testnet \
      --expires-in-minutes 30 \
      --created-by operator:local

List records and their status (ACTIVE, EXPIRED, REVOKED or CONSUMED):

    python -m app.operator_cli --db data/guardrail.db list

Revoke an unused authorization:

    python -m app.operator_cli --db data/guardrail.db revoke auth-001

The CLI uses the existing SQLiteStore methods, so creation and revocation are recorded
in the audit log. IDs are unique; use a fresh ID for every intended payment.
A successful authorization is single-use. An agent cannot create, expand, or revoke
authorizations through its transaction request.


## n8n setup

Follow docs/N8N_TELEGRAM_SETUP.md. Configure authenticated endpoints to submit an approval request and return PENDING, APPROVE or DENY with the original fingerprint. Restrict Telegram approval to the designated human approver.

## Environment variables

See .env.example. Never commit .env, Telegram tokens, n8n credentials, NEAR private keys or wallet secrets.

## Security boundaries and limitations

- Spending authority is loaded from SQLite; caller-supplied intended_amount is descriptive only.
- Authorizations are bound to agent, exact recipient, asset, network, maximum amount and expiry.
- Authorizations are revocable and consumed once using conditional SQLite updates.
- Human approval is fingerprint-bound and consumed once. It does not execute a transfer.
- The API returns APPROVED_PENDING_EXECUTION and execution_enabled=false; no funds are transferred.
- Runtime trusted/blocked recipient sets remain in-memory configuration.
- The trusted authorization creation method is an operator-side library interface, not yet a separately authenticated admin UI/CLI. Protect database access and the operator environment.
- NEAR MCP tools, wallet signing, on-chain execution and attack simulations are not implemented yet.

Hackathon prototype only; not a production wallet security product.
