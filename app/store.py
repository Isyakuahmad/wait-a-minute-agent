import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class SQLiteStore:
    """SQLite persistence for approvals, execution history and audit events."""
    def __init__(self, database_path: str = "data/guardrail.db") -> None:
        self.database_path = database_path
        if database_path != ":memory:":
            Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS approval_requests (
              request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
              transaction_json TEXT NOT NULL,
              decision TEXT NOT NULL CHECK(decision IN ('PENDING','APPROVE','DENY','EXPIRED')),
              created_at TEXT NOT NULL, decided_at TEXT, approver_id TEXT, consumed_at TEXT);
            CREATE TABLE IF NOT EXISTS audit_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, request_id TEXT NOT NULL,
              event_type TEXT NOT NULL, details_json TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS executed_payments (
              request_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, recipient TEXT NOT NULL,
              amount TEXT NOT NULL, asset TEXT NOT NULL, occurred_at TEXT NOT NULL);
            """)

    @staticmethod
    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def audit(self, request_id: str, event_type: str, details: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute("INSERT INTO audit_events(request_id,event_type,details_json,created_at) VALUES(?,?,?,?)",
                       (request_id,event_type,json.dumps(details,sort_keys=True),self.now()))

    def create_approval(self, request_id: str, fingerprint: str, transaction: dict) -> bool:
        try:
            with self.connect() as db:
                db.execute("INSERT INTO approval_requests(request_id,fingerprint,transaction_json,decision,created_at) VALUES(?,?,?,'PENDING',?)",
                           (request_id,fingerprint,json.dumps(transaction,sort_keys=True),self.now()))
            self.audit(request_id,"APPROVAL_REQUEST_CREATED",{"fingerprint":fingerprint})
            return True
        except sqlite3.IntegrityError:
            return False

    def get_approval(self, request_id: str) -> dict | None:
        with self.connect() as db:
            row=db.execute("SELECT * FROM approval_requests WHERE request_id=?",(request_id,)).fetchone()
            return dict(row) if row else None

    def set_approval_decision(self, request_id: str, fingerprint: str, decision: str, approver_id: str | None=None) -> bool:
        if decision not in {"APPROVE","DENY"}: return False
        with self.connect() as db:
            cur=db.execute("UPDATE approval_requests SET decision=?,decided_at=?,approver_id=? WHERE request_id=? AND fingerprint=? AND decision='PENDING' AND consumed_at IS NULL",
                           (decision,self.now(),approver_id,request_id,fingerprint))
        if cur.rowcount == 1:
            self.audit(request_id,"HUMAN_DECISION_RECORDED",{"decision":decision,"approver_id":approver_id})
            return True
        return False

    def consume_approval(self, request_id: str, fingerprint: str) -> bool:
        with self.connect() as db:
            cur=db.execute("UPDATE approval_requests SET consumed_at=? WHERE request_id=? AND fingerprint=? AND decision='APPROVE' AND consumed_at IS NULL",
                           (self.now(),request_id,fingerprint))
        if cur.rowcount == 1:
            self.audit(request_id,"APPROVAL_CONSUMED",{"fingerprint":fingerprint})
            return True
        return False

    def recent_matching_payments(self, agent_id: str, recipient: str, amount: str, asset: str, since: str) -> int:
        with self.connect() as db:
            row=db.execute("SELECT COUNT(*) AS n FROM executed_payments WHERE agent_id=? AND recipient=? AND amount=? AND asset=? AND occurred_at>=?",
                           (agent_id,recipient,amount,asset,since)).fetchone()
        return int(row["n"])

    def record_execution(self, tx: dict) -> bool:
        try:
            with self.connect() as db:
                db.execute("INSERT INTO executed_payments(request_id,agent_id,recipient,amount,asset,occurred_at) VALUES(?,?,?,?,?,?)",
                           (tx["request_id"],tx["agent_id"],tx["recipient"],str(tx["amount"]),tx["asset"],self.now()))
            self.audit(tx["request_id"],"EXECUTION_CONFIRMED",{"recipient":tx["recipient"],"amount":str(tx["amount"]),"asset":tx["asset"]})
            return True
        except sqlite3.IntegrityError:
            return False

    def list_audit_events(self, limit: int=100) -> list[dict]:
        with self.connect() as db:
            rows=db.execute("SELECT * FROM audit_events ORDER BY id DESC LIMIT ?",(limit,)).fetchall()
        return [dict(row) for row in rows]
