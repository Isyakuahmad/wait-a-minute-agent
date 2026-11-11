from datetime import datetime,timezone
from decimal import Decimal
from app.guardrail import PiggyBankGuardrail
from app.models import Decision,TransactionRequest
from app.store import SQLiteStore

def tx(**updates):
    v=dict(request_id='r1',agent_id='agent',intent='buy item',intended_amount=Decimal('10'),amount=Decimal('10'),recipient='seller.testnet',asset='NEAR',network='testnet',created_at=datetime.now(timezone.utc)); v.update(updates); return TransactionRequest(**v)

def test_trusted_normal_allowed(tmp_path):
    s=SQLiteStore(str(tmp_path/'g.db')); g=PiggyBankGuardrail(s); g.trusted_recipients.add('seller.testnet'); assert g.evaluate(tx()).decision==Decision.ALLOW

def test_unknown_recipient_requires_human(tmp_path):
    assert PiggyBankGuardrail(SQLiteStore(str(tmp_path/'g.db'))).evaluate(tx()).decision==Decision.ASK_HUMAN

def test_blocked_recipient_denied(tmp_path):
    g=PiggyBankGuardrail(SQLiteStore(str(tmp_path/'g.db'))); g.blocked_recipients.add('seller.testnet'); assert g.evaluate(tx()).decision==Decision.DENY

def test_amount_over_intent_requires_human(tmp_path):
    g=PiggyBankGuardrail(SQLiteStore(str(tmp_path/'g.db'))); g.trusted_recipients.add('seller.testnet'); assert g.evaluate(tx(amount=Decimal('20'))).decision==Decision.ASK_HUMAN
