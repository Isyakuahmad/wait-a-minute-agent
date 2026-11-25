from app.store import SQLiteStore


def test_approval_single_use_and_fingerprint_bound(tmp_path):
    s=SQLiteStore(str(tmp_path/"test.db")); tx={"request_id":"r1","recipient":"alice.testnet","amount":"2"}
    assert s.create_approval("r1","hash-1",tx); assert not s.create_approval("r1","hash-1",tx)
    assert s.set_approval_decision("r1","hash-1","APPROVE","telegram:123")
    assert not s.set_approval_decision("r1","hash-1","DENY","telegram:123")
    assert s.consume_approval("r1","hash-1"); assert not s.consume_approval("r1","hash-1")


def test_wrong_fingerprint_rejected(tmp_path):
    s=SQLiteStore(str(tmp_path/"test.db")); s.create_approval("r2","correct",{"request_id":"r2"})
    assert not s.set_approval_decision("r2","wrong","APPROVE")
    assert not s.consume_approval("r2","wrong")


def test_trusted_authorization_is_unique_revocable_and_single_use(tmp_path):
    from datetime import datetime, timedelta, timezone
    s=SQLiteStore(str(tmp_path/"test.db"))
    args=("auth-1","agent","alice.testnet","5","NEAR","testnet",
        (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),"operator")
    assert s.create_authorization(*args); assert not s.create_authorization(*args)
    assert s.get_authorization("auth-1")["max_amount"]=="5"
    assert s.consume_authorization("auth-1"); assert not s.consume_authorization("auth-1")


def test_revoked_authorization_cannot_be_consumed(tmp_path):
    from datetime import datetime, timedelta, timezone
    s=SQLiteStore(str(tmp_path/"test.db"))
    s.create_authorization("auth-2","agent","alice.testnet","5","NEAR","testnet",
        (datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),"operator")
    assert s.revoke_authorization("auth-2"); assert not s.consume_authorization("auth-2")


def test_audit_persists(tmp_path):
    s=SQLiteStore(str(tmp_path/"test.db")); s.audit("r3","TEST_EVENT",{"ok":True})
    assert s.list_audit_events()[0]["event_type"]=="TEST_EVENT"
