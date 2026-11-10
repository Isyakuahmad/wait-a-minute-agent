from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.guardrail import PiggyBankGuardrail
from app.models import Decision, TransactionRequest


NOW = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


def make_tx(amount: str = "12", recipient: str = "seller.testnet",
            request_id: str = "request-1") -> TransactionRequest:
    return TransactionRequest(
        request_id=request_id,
        agent_id="shopping-agent",
        intent="Buy a textbook",
        intended_amount=Decimal("15"),
        amount=Decimal(amount),
        recipient=recipient,
        asset="NEAR",
        created_at=NOW,
    )


def test_normal_trusted_payment_is_allowed():
    bank = PiggyBankGuardrail()
    bank.trusted_recipients.add("seller.testnet")

    result = bank.evaluate(make_tx(), now=NOW)

    assert result.decision == Decision.ALLOW
    assert result.requires_human_approval is False


def test_amount_above_intent_ceiling_requires_review():
    bank = PiggyBankGuardrail()
    bank.trusted_recipients.add("seller.testnet")

    result = bank.evaluate(make_tx("200"), now=NOW)

    assert result.decision == Decision.REVIEW
    assert result.requires_human_approval is True
    assert any("intent ceiling" in reason for reason in result.reasons)


def test_unknown_recipient_requires_review():
    bank = PiggyBankGuardrail()

    result = bank.evaluate(make_tx(), now=NOW)

    assert result.decision == Decision.REVIEW
    assert result.requires_human_approval is True


def test_blocked_recipient_is_denied_even_if_other_checks_pass():
    bank = PiggyBankGuardrail()
    bank.trusted_recipients.add("seller.testnet")
    bank.blocked_recipients.add("seller.testnet")

    result = bank.evaluate(make_tx(), now=NOW)

    assert result.decision == Decision.DENY
    assert result.requires_human_approval is False


def test_repeated_payments_trigger_velocity_review():
    bank = PiggyBankGuardrail(max_repeated_payments=3)
    bank.trusted_recipients.add("seller.testnet")
    tx = make_tx()

    for index in range(3):
        bank.record_execution(
            tx.model_copy(update={"request_id": f"prior-{index}"}),
            occurred_at=NOW - timedelta(minutes=index),
        )

    result = bank.evaluate(
        tx.model_copy(update={"request_id": "fourth-payment"}),
        now=NOW,
    )

    assert result.decision == Decision.REVIEW
    assert any("Repeated-payment threshold" in reason for reason in result.reasons)


def test_payments_outside_velocity_window_do_not_count():
    bank = PiggyBankGuardrail(max_repeated_payments=2)
    bank.trusted_recipients.add("seller.testnet")
    tx = make_tx()

    bank.record_execution(tx, occurred_at=NOW - timedelta(hours=2))
    bank.record_execution(
        tx.model_copy(update={"request_id": "prior-2"}),
        occurred_at=NOW - timedelta(hours=1, minutes=1),
    )

    result = bank.evaluate(
        tx.model_copy(update={"request_id": "new"}),
        now=NOW,
    )

    assert result.decision == Decision.ALLOW


def test_duplicate_execution_record_is_ignored():
    bank = PiggyBankGuardrail()
    tx = make_tx()

    bank.record_execution(tx, occurred_at=NOW)
    bank.record_execution(tx, occurred_at=NOW + timedelta(minutes=1))

    assert len(bank.history["shopping-agent"]) == 1
