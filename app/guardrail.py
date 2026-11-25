from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.models import Decision, GuardrailResult, TransactionRequest
from app.store import SQLiteStore


class PiggyBankGuardrail:
    """Policy engine. Spending limits come from independently stored authorizations."""
    def __init__(self, store: SQLiteStore, max_repeated_payments: int=3,
                 velocity_window_minutes: int=60) -> None:
        if max_repeated_payments < 1 or velocity_window_minutes < 1:
            raise ValueError("Guardrail limits must be positive")
        self.store=store
        self.max_repeated_payments=max_repeated_payments
        self.velocity_window=timedelta(minutes=velocity_window_minutes)
        self.trusted_recipients:set[str]=set()
        self.blocked_recipients:set[str]=set()

    def evaluate(self, tx: TransactionRequest, now: datetime | None=None) -> GuardrailResult:
        checked=now or datetime.now(timezone.utc)
        if checked.tzinfo is None or checked.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        if tx.recipient in self.blocked_recipients:
            return GuardrailResult(decision=Decision.DENY,reasons=["Recipient is explicitly blocked."])

        authorization=self.store.get_authorization(tx.authorization_id)
        if authorization is None:
            return GuardrailResult(decision=Decision.DENY,reasons=["Trusted authorization does not exist."])
        if authorization["revoked_at"] is not None:
            return GuardrailResult(decision=Decision.DENY,reasons=["Trusted authorization has been revoked."])
        if authorization["consumed_at"] is not None:
            return GuardrailResult(decision=Decision.DENY,reasons=["Trusted authorization has already been used."])
        expires=datetime.fromisoformat(authorization["expires_at"])
        if expires <= checked:
            return GuardrailResult(decision=Decision.DENY,reasons=["Trusted authorization has expired."])
        if (authorization["agent_id"] != tx.agent_id or authorization["recipient"] != tx.recipient
                or authorization["asset"] != tx.asset or authorization["network"] != tx.network):
            return GuardrailResult(decision=Decision.DENY,reasons=["Transaction does not match its trusted authorization."])
        ceiling=Decimal(authorization["max_amount"])
        if tx.amount > ceiling:
            return GuardrailResult(decision=Decision.DENY,reasons=[f"Requested amount {tx.amount} {tx.asset} exceeds independently authorized maximum {ceiling} {tx.asset}."])

        reasons=[]
        if tx.recipient not in self.trusted_recipients:
            reasons.append("Recipient is not on the runtime trusted-recipient list; human approval is required.")
        cutoff=(checked-self.velocity_window).isoformat()
        recent=self.store.recent_matching_payments(tx.agent_id,tx.recipient,str(tx.amount),tx.asset,cutoff)
        if recent>=self.max_repeated_payments:
            reasons.append("Repeated-payment threshold reached within the velocity window.")
        if reasons:
            return GuardrailResult(decision=Decision.ASK_HUMAN,reasons=reasons,requires_human_approval=True)
        return GuardrailResult(decision=Decision.ALLOW,reasons=["Trusted authorization and configured policy checks passed."])
