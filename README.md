# Wait a Minute Agent

**An intent-aware security guardrail for autonomous AI agents that request NEAR transactions.**

The guardrail evaluates proposed transactions before wallet execution. It checks whether the amount fits the purchase intent, whether the agent is repeating payments, and whether the recipient is trusted.

## Security decisions

- **ALLOW** — all configured checks pass.
- **REVIEW** — pause and request human authorization.
- **DENY** — an explicitly blocked recipient is rejected.

A review decision is not permission to execute. Human approval will be implemented as a separate, transaction-bound workflow.

## Current milestone: Python guardrail foundation

Implemented:
- Pydantic transaction and decision models
- Amount-versus-intent threshold
- Repeated-payment velocity check
- Trusted and blocked recipient checks
- Duplicate execution-record protection
- Automated unit tests
- GitHub Actions test workflow

## Run locally

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
pytest -v
```

## Important security boundaries

- The AI agent must not receive an unrestricted wallet private key.
- The intended amount in this first model is not yet cryptographically trusted. A later milestone must bind it to a human-approved or otherwise trusted purchase intent.
- This milestone records confirmed executions in memory only. SQLite persistence and atomic pending-payment reservations are required before production use; otherwise concurrent requests or restarts can undermine velocity enforcement.
- No NEAR transaction signing or transfer is enabled in this milestone.

## Roadmap

1. [x] Python guardrail engine and tests
2. [ ] SQLite persistence, pending approvals, and audit logs
3. [ ] Human approval dashboard and transaction-bound approvals
4. [ ] NEAR testnet integration behind the guardrail
5. [ ] Attack simulations and security tests
6. [ ] Hackathon demonstration video

## Project identity

Human-facing name: **The Piggy Bank That Says Wait a Minute**

Technical repository: **wait-a-minute-agent**
