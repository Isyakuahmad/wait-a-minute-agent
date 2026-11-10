# Wait a Minute Agent

An intent-aware security guardrail for autonomous AI agents that request NEAR transactions.

The guardrail evaluates transaction requests before any wallet execution using amount, velocity, and recipient policies. Risky requests are paused for human approval; explicitly blocked recipients are denied.

## Project status

Early development. The first milestone is a tested Python policy engine. NEAR wallet execution is intentionally not enabled yet.

## Security principle

The AI agent must never receive unrestricted access to the wallet signing key. All transactions must pass through the guardrail enforcement boundary.

## Planned milestones

1. Python guardrail engine and tests
2. SQLite persistence and audit trail
3. Human approval interface
4. NEAR testnet integration
5. Attack simulations and demo
