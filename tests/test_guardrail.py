from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.guardrail import PiggyBankGuardrail
from app.models import Decision, TransactionRequest
from app.store import SQLiteStore


def tx(**updates):
    values = dict(request_id="r1", authorization_id="auth-1", agent_id="agent",
        intent="buy item", intended_amount=Decimal("10"), amount=Decimal("10"),
        recipient="seller.testnet", asset="NEAR", network="testnet",
        created_at=datetime.now(timezone.utc))
    values.update(updates)
    return TransactionRequest(**values)


def authorize(store, **updates):
    values = dict(authorization_id="auth-1", agent_id="agent", recipient="seller.testnet",
        max_amount="10", asset="NEAR", network="testnet",
        expires_at=(datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),
        created_by="operator:test")
    values.update(updates)
    assert store.create_authorization(**values)


def test_trusted_normal_allowed(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    guardrail=PiggyBankGuardrail(store); guardrail.trusted_recipients.add("seller.testnet")
    assert guardrail.evaluate(tx()).decision == Decision.ALLOW


def test_unknown_recipient_requires_human(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    assert PiggyBankGuardrail(store).evaluate(tx()).decision == Decision.ASK_HUMAN


def test_blocked_recipient_denied(tmp_path):
    guardrail=PiggyBankGuardrail(SQLiteStore(str(tmp_path/"g.db")))
    guardrail.blocked_recipients.add("seller.testnet")
    assert guardrail.evaluate(tx()).decision == Decision.DENY


def test_amount_over_trusted_limit_is_denied(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    guardrail=PiggyBankGuardrail(store); guardrail.trusted_recipients.add("seller.testnet")
    assert guardrail.evaluate(tx(amount=Decimal("20"))).decision == Decision.DENY


def test_agent_cannot_inflate_its_own_intent(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    guardrail=PiggyBankGuardrail(store); guardrail.trusted_recipients.add("seller.testnet")
    proposal=tx(intended_amount=Decimal("10000"), amount=Decimal("1000"))
    assert guardrail.evaluate(proposal).decision == Decision.DENY


def test_recipient_substitution_is_denied(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    assert PiggyBankGuardrail(store).evaluate(tx(recipient="attacker.testnet")).decision == Decision.DENY


def test_agent_asset_and_network_must_match(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    guardrail=PiggyBankGuardrail(store)
    assert guardrail.evaluate(tx(agent_id="other-agent")).decision == Decision.DENY
    assert guardrail.evaluate(tx(asset="USDT")).decision == Decision.DENY
    assert guardrail.evaluate(tx(network="mainnet")).decision == Decision.DENY


def test_expired_and_revoked_authorizations_are_denied(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db"))
    authorize(store, expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat())
    assert PiggyBankGuardrail(store).evaluate(tx()).decision == Decision.DENY
    store2=SQLiteStore(str(tmp_path/"g2.db")); authorize(store2)
    assert store2.revoke_authorization("auth-1")
    assert PiggyBankGuardrail(store2).evaluate(tx()).decision == Decision.DENY


def test_consumed_authorization_cannot_be_reused(tmp_path):
    store=SQLiteStore(str(tmp_path/"g.db")); authorize(store)
    assert store.consume_authorization("auth-1")
    assert PiggyBankGuardrail(store).evaluate(tx()).decision == Decision.DENY
