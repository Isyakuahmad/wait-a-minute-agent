# n8n + Telegram human approval setup

This repository uses a two-workflow, fail-closed integration. Python submits once to Workflow A, receives an immediate 202/PENDING acknowledgement, then polls Workflow B. The Telegram decision is never sent directly to a blockchain tool.

## 1. Telegram credential

1. Create a bot with @BotFather and keep its token private.
2. Open the bot chat and press Start.
3. In n8n, create a Telegram API credential using the bot token.
4. Restrict approvals to your own Telegram account/user ID. Do not accept arbitrary chat members as approvers.

## 2. Shared n8n Data Table

Create a Data Table named approval_requests with columns:

- request_id (string; unique)
- fingerprint (string)
- transaction_json (string)
- decision (string: PENDING, APPROVE, DENY)
- created_at (string/date)
- decided_at (string/date)
- approver_id (string)

Do not overwrite an existing request ID. Treat duplicate IDs as an error.

## 3. Workflow A — Guardrail - Request Approval

Create these nodes in order:

1. Webhook — POST path guardrail-approval; Header Auth credential; response mode Using Respond to Webhook.
2. IF / validation — require body.request_id, body.fingerprint, body.transaction, and body.status == PENDING. Reject malformed requests. Configure Header Auth on the Webhook node.
3. Data Table — insert a row with request ID, fingerprint, JSON-stringified transaction, decision=PENDING, and timestamp. Use insert-only behavior; never update an existing request.
4. Respond to Webhook — HTTP 202, JSON body containing the exact request ID from the Webhook body and status PENDING. Example expression for request_id: {{ $('Webhook').first().json.body.request_id }}. This acknowledgement is not approval.
5. Telegram — Message → Send and Wait for Response → Approval response type with Approve and Disapprove. Use the designated approver chat ID. Include recipient, amount, asset, network, intent and request ID. Set a 240-second timeout.
6. IF — inspect the Telegram node output in a test execution and branch on its actual approval result field.
7. Data Table — update only the matching request ID where decision is still PENDING and fingerprint matches. Set decision to APPROVE or DENY, plus decided_at and approver_id. If no row matches, do not create a new row.

Telegram node output field names can vary by n8n version. Run one approval and one rejection test, then use the observed output field in the IF node. Restrict the Telegram approver to the expected user ID.

## 4. Workflow B — Guardrail - Check Status

1. Webhook — GET path guardrail-status; same Header Auth credential; response mode Using Respond to Webhook.
2. IF / validation — require query.request_id; reject missing IDs.
3. Data Table — retrieve the row whose request_id exactly equals the query parameter. Do not select a row using a caller-supplied fingerprint alone.
4. Respond to Webhook — return the stored request ID, fingerprint and decision. Example: {"request_id":"...","fingerprint":"...","decision":"PENDING"}. Return 404 for unknown IDs. Never synthesize APPROVE when a row is missing or malformed.

## 5. Configure Python

Set N8N_WEBHOOK_URL, N8N_STATUS_URL, and N8N_API_TOKEN in the runtime environment. Both Webhook nodes must use Header Auth with the same Authorization header value (Bearer followed by the token), matching the Python client. Use the Production URLs after both workflows are activated. Do not commit credentials or workflow exports containing secrets.

## 6. Test checklist

- POST receives HTTP 202 with the same request ID and PENDING.
- Telegram displays the exact transaction details.
- Approve produces APPROVE only for the matching ID and fingerprint.
- Disapprove produces DENY.
- Unknown ID returns 404; malformed payload returns 4xx.
- Timeout, n8n outage, invalid JSON, missing fingerprint and unexpected decision all fail closed in Python.
- A duplicate request ID cannot overwrite an earlier request.

## Security notes

The local SQLite database and the n8n Data Table are separate stores. Python trusts the authenticated n8n status endpoint only after checking request ID and recomputing the transaction fingerprint. For stronger deployment security, use HTTPS, rotate the shared token, limit webhook exposure, enforce Telegram approver identity, and add a signed decision callback or independently authenticated decision record. Human approval only authorizes the exact proposal; it does not execute a NEAR transfer. NEAR signing/MCP execution remains disabled in this milestone.
