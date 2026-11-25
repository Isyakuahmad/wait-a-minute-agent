from datetime import datetime, timezone
from decimal import Decimal

from app.guardrail import PiggyBankGuardrail
from app.models import Decision, TransactionRequest
from app.store import SQLiteStore


def tx(**updates):
    values = dict(
        request_id="r1",
        agent_id="agent",
        intent="buy item",
        intended_amount=Decimal("10"),
        amount=Decimal("10"),
        recipient="seller.testnet",
        asset="NEAR",
        network="testnet",
        created_at=datetime.now(timezone.utc),
    )
    values.update(updates)
    return TransactionRequest(**values)


def test_trusted_normal_allowed(tmp_path):
    store = SQLiteStore(str(tmp_path / "g.db"))
    guardrail = PiggyBankGuardrail(store)
    guardrail.trusted_recipients.add("seller.testnet")

    assert guardrail.evaluate(tx()).decision == Decision.ALLOW


def test_unknown_recipient_requires_human(tmp_path):
    guardrail = PiggyBankGuardrail(SQLiteStore(str(tmp_path / "g.db")))

    assert guardrail.evaluate(tx()).decision == Decision.ASK_HUMAN


def test_blocked_recipient_denied(tmp_path):
    guardrail = PiggyBankGuardrail(SQLiteStore(str(tmp_path / "g.db")))
    guardrail.blocked_recipients.add("seller.testnet")

    assert guardrail.evaluate(tx()).decision == Decision.DENY


def test_amount_over_intent_requires_human(tmp_path):
    guardrail = PiggyBankGuardrail(SQLiteStore(str(tmp_path / "g.db")))
    guardrail.trusted_recipients.add("seller.testnet")

    assert guardrail.evaluate(tx(amount=Decimal("20"))).decision == Decision.ASK_HUMAN


def test_agent_cannot_inflate_its_own_intent(tmp_path):
    store = SQLiteStore(str(tmp_path / "guardrail.db"))
    guardrail = PiggyBankGuardrail(store)
    guardrail.trusted_recipients.add("seller.testnet")

    proposal = tx(
        intended_amount=Decimal("10"),
        amount=Decimal("1000"),
    )

    result = guardrail.evaluate(proposal)

    assert result.decision != Decision.ALLOW
