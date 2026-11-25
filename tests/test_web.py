from datetime import datetime, timedelta, timezone

from app.web import create_app
from app.store import SQLiteStore


class Approve:
    def request_human_approval(self, tx):
        return "APPROVE"


class Deny:
    def request_human_approval(self, tx):
        return "DENY"


def payload():
    return {"request_id":"web-1","authorization_id":"auth-1","agent_id":"agent",
        "intent":"buy item","intended_amount":"10","amount":"20",
        "recipient":"unknown.testnet","asset":"NEAR","network":"testnet"}


def setup_store(path):
    store=SQLiteStore(str(path))
    store.create_authorization("auth-1","agent","unknown.testnet","20","NEAR","testnet",
        (datetime.now(timezone.utc)+timedelta(minutes=15)).isoformat(),"operator:test")
    return store


def test_approval_is_not_execution(tmp_path):
    store=setup_store(tmp_path/"w.db"); app=create_app({"TESTING":True},Approve(),store)
    r=app.test_client().post("/api/transactions/evaluate",json=payload())
    assert r.status_code==200 and r.json["decision"]=="APPROVED_PENDING_EXECUTION"
    assert r.json["execution_enabled"] is False
    assert store.get_authorization("auth-1")["consumed_at"] is not None


def test_denial_fails_closed(tmp_path):
    store=setup_store(tmp_path/"w.db"); app=create_app({"TESTING":True},Deny(),store)
    r=app.test_client().post("/api/transactions/evaluate",json=payload())
    assert r.status_code==403 and r.json["decision"]=="DENY"
    assert store.get_authorization("auth-1")["consumed_at"] is None


def test_missing_authorization_fails_closed(tmp_path):
    app=create_app({"TESTING":True},Approve(),SQLiteStore(str(tmp_path/"w.db")))
    r=app.test_client().post("/api/transactions/evaluate",json=payload())
    assert r.status_code==403 and r.json["decision"]=="DENY"


def test_allow_consumes_authorization_once(tmp_path):
    store=setup_store(tmp_path/"w.db"); app=create_app({"TESTING":True},store=store)
    client=app.test_client(); data=payload(); data["amount"]="10"
    first=client.post("/api/transactions/evaluate",json=data)
    assert first.status_code==200 and first.json["decision"]=="ALLOW"
    data["request_id"]="web-2"
    second=client.post("/api/transactions/evaluate",json=data)
    assert second.status_code==403 and second.json["decision"]=="DENY"


def test_health(tmp_path):
    app=create_app({"TESTING":True},store=SQLiteStore(str(tmp_path/"h.db")))
    assert app.test_client().get("/health").json["execution_enabled"] is False
