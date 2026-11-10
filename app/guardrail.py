from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Decision, GuardrailResult, TransactionRequest


@dataclass(frozen=True)
class ExecutedPayment:
    request_id: str
    occurred_at: datetime
    recipient: str
    amount: Decimal
    asset: str


class PiggyBankGuardrail:
    """In-memory policy engine. Persistence and atomic reservations come next."""

    def __init__(
        self,
        max_intent_deviation: Decimal = Decimal("1.25"),
        max_repeated_payments: int = 3,
        velocity_window_minutes: int = 60,
    ) -> None:
        if max_intent_deviation < 1:
            raise ValueError("max_intent_deviation must be at least 1")
        if max_repeated_payments < 1:
            raise ValueError("max_repeated_payments must be at least 1")
        if velocity_window_minutes < 1:
            raise ValueError("velocity_window_minutes must be at least 1")

        self.max_intent_deviation = max_intent_deviation
        self.max_repeated_payments = max_repeated_payments
        self.velocity_window = timedelta(minutes=velocity_window_minutes)
        self.history: dict[str, list[ExecutedPayment]] = defaultdict(list)
        self.trusted_recipients: set[str] = set()
        self.blocked_recipients: set[str] = set()

    def check_amount(self, tx: TransactionRequest) -> tuple[bool, str | None]:
        # The intended amount must eventually come from a trusted, signed intent,
        # not from an untrusted agent-supplied field.
        ceiling = tx.intended_amount * self.max_intent_deviation
        if tx.amount > ceiling:
            return False, (
                f"Requested amount {tx.amount} {tx.asset} exceeds the "
                f"allowed intent ceiling of {ceiling} {tx.asset}."
            )
        return True, None

    def check_velocity(
        self, tx: TransactionRequest, now: datetime
    ) -> tuple[bool, str | None]:
        cutoff = now - self.velocity_window
        recent = [
            payment
            for payment in self.history[tx.agent_id]
            if payment.occurred_at >= cutoff
            and payment.recipient == tx.recipient
            and payment.amount == tx.amount
            and payment.asset == tx.asset
        ]
        if len(recent) >= self.max_repeated_payments:
            return False, (
                f"Repeated-payment threshold reached: "
                f"{len(recent)} matching payments within "
                f"{self.velocity_window}."
            )
        return True, None

    def check_recipient(
        self, tx: TransactionRequest
    ) -> tuple[bool | None, str | None]:
        if tx.recipient in self.blocked_recipients:
            return False, "Recipient is explicitly blocked."
        if tx.recipient not in self.trusted_recipients:
            return None, "Recipient is not trusted; human approval is required."
        return True, None

    def evaluate(
        self, tx: TransactionRequest, now: datetime | None = None
    ) -> GuardrailResult:
        checked_at = now or datetime.now(timezone.utc)
        if checked_at.tzinfo is None or checked_at.utcoffset() is None:
            raise ValueError("now must be timezone-aware")

        reasons: list[str] = []
        needs_review = False

        recipient_ok, recipient_reason = self.check_recipient(tx)
        if recipient_ok is False:
            return GuardrailResult(
                decision=Decision.DENY,
                reasons=[recipient_reason or "Recipient is blocked."],
            )

        amount_ok, amount_reason = self.check_amount(tx)
        velocity_ok, velocity_reason = self.check_velocity(tx, checked_at)

        if not amount_ok and amount_reason:
            reasons.append(amount_reason)
            needs_review = True
        if not velocity_ok and velocity_reason:
            reasons.append(velocity_reason)
            needs_review = True
        if recipient_ok is None and recipient_reason:
            reasons.append(recipient_reason)
            needs_review = True

        if needs_review:
            return GuardrailResult(
                decision=Decision.REVIEW,
                reasons=reasons,
                requires_human_approval=True,
            )

        return GuardrailResult(
            decision=Decision.ALLOW,
            reasons=["All configured policy checks passed."],
        )

    def record_execution(
        self, tx: TransactionRequest, occurred_at: datetime | None = None
    ) -> None:
        """Record a confirmed execution; duplicate request IDs are ignored."""
        existing_ids = {
            payment.request_id
            for payments in self.history.values()
            for payment in payments
        }
        if tx.request_id in existing_ids:
            return

        timestamp = occurred_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")

        self.history[tx.agent_id].append(
            ExecutedPayment(
                request_id=tx.request_id,
                occurred_at=timestamp,
                recipient=tx.recipient,
                amount=tx.amount,
                asset=tx.asset,
            )
        )
