from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.models import Decision, GuardrailResult, TransactionRequest
from app.store import SQLiteStore

class PiggyBankGuardrail:
    """Policy engine; review decisions pause and never send funds."""
    def __init__(self, store: SQLiteStore, max_intent_deviation: Decimal=Decimal("1.25"), max_repeated_payments: int=3, velocity_window_minutes: int=60) -> None:
        if max_intent_deviation < 1 or max_repeated_payments < 1 or velocity_window_minutes < 1:
            raise ValueError("Guardrail limits must be positive and deviation >= 1")
        self.store=store; self.max_intent_deviation=max_intent_deviation
        self.max_repeated_payments=max_repeated_payments
        self.velocity_window=timedelta(minutes=velocity_window_minutes)
        self.trusted_recipients:set[str]=set(); self.blocked_recipients:set[str]=set()

    def evaluate(self, tx: TransactionRequest, now: datetime | None=None) -> GuardrailResult:
        checked=now or datetime.now(timezone.utc)
        if checked.tzinfo is None or checked.utcoffset() is None: raise ValueError("now must be timezone-aware")
        if tx.recipient in self.blocked_recipients:
            return GuardrailResult(decision=Decision.DENY,reasons=["Recipient is explicitly blocked."])
        reasons=[]
        if tx.recipient not in self.trusted_recipients: reasons.append("Recipient is not trusted; human approval is required.")
        ceiling=tx.intended_amount*self.max_intent_deviation
        if tx.amount>ceiling: reasons.append(f"Requested amount {tx.amount} {tx.asset} exceeds intent ceiling {ceiling} {tx.asset}.")
        cutoff=(checked-self.velocity_window).isoformat()
        recent=self.store.recent_matching_payments(tx.agent_id,tx.recipient,str(tx.amount),tx.asset,cutoff)
        if recent>=self.max_repeated_payments: reasons.append("Repeated-payment threshold reached within the velocity window.")
        if reasons: return GuardrailResult(decision=Decision.ASK_HUMAN,reasons=reasons,requires_human_approval=True)
        return GuardrailResult(decision=Decision.ALLOW,reasons=["All configured policy checks passed."])
