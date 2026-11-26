from datetime import datetime, timedelta, timezone

from app.operator_cli import main
from app.store import SQLiteStore


def run_cli(db_path, capsys, *args):
    result = main(["--db", str(db_path), *args])
    output = capsys.readouterr()
    return result, output.out, output.err


def test_operator_cli_create_list_revoke(tmp_path, capsys):
    db_path = tmp_path / "operator.db"

    result, out, err = run_cli(
        db_path, capsys, "create",
        "--authorization-id", "operator-auth-1",
        "--agent-id", "demo-agent",
        "--recipient", "seller.testnet",
        "--max-amount", "2.5",
        "--expires-in-minutes", "20",
    )
    assert result == 0
    assert "Created authorization operator-auth-1" in out
    assert not err

    result, out, err = run_cli(db_path, capsys, "list")
    assert result == 0
    assert "operator-auth-1" in out
    assert "ACTIVE" in out
    assert not err

    result, out, err = run_cli(db_path, capsys, "revoke", "operator-auth-1")
    assert result == 0
    assert "Revoked authorization" in out
    assert not err

    store = SQLiteStore(str(db_path))
    record = store.get_authorization("operator-auth-1")
    assert record["revoked_at"] is not None
    events = store.list_audit_events()
    assert any(event["event_type"] == "TRUSTED_INTENT_REVOKED" for event in events)


def test_operator_cli_rejects_duplicate_authorization_id(tmp_path, capsys):
    db_path = tmp_path / "operator.db"
    args = (
        "create", "--authorization-id", "same-id",
        "--agent-id", "demo-agent", "--recipient", "seller.testnet",
        "--max-amount", "1",
    )
    assert run_cli(db_path, capsys, *args)[0] == 0
    result, out, err = run_cli(db_path, capsys, *args)
    assert result == 1
    assert "already exists" in err


def test_operator_cli_rejects_nonpositive_amount(tmp_path, capsys):
    result, out, err = run_cli(
        tmp_path / "operator.db", capsys, "create",
        "--authorization-id", "bad-amount",
        "--agent-id", "demo-agent",
        "--recipient", "seller.testnet",
        "--max-amount", "0",
    )
    assert result == 2
    assert "positive" in err.lower()


def test_operator_cli_list_shows_consumed_status(tmp_path, capsys):
    db_path = tmp_path / "operator.db"
    store = SQLiteStore(str(db_path))
    store.create_authorization(
        authorization_id="used",
        agent_id="demo-agent",
        recipient="seller.testnet",
        max_amount="1",
        asset="NEAR",
        network="testnet",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        created_by="operator:test",
    )
    assert store.consume_authorization("used")

    result, out, err = run_cli(db_path, capsys, "list")
    assert result == 0
    assert "CONSUMED" in out
    assert not err


def test_operator_cli_cannot_revoke_consumed_authorization(tmp_path, capsys):
    db_path = tmp_path / "operator.db"
    store = SQLiteStore(str(db_path))
    store.create_authorization(
        authorization_id="used",
        agent_id="demo-agent",
        recipient="seller.testnet",
        max_amount="1",
        asset="NEAR",
        network="testnet",
        expires_at=(datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        created_by="operator:test",
    )
    store.consume_authorization("used")

    result, out, err = run_cli(db_path, capsys, "revoke", "used")
    assert result == 1
    assert "already consumed" in err
