import os
from flask import Flask, jsonify, render_template, request
from pydantic import ValidationError

from app.approval import N8NApprovalClient, transaction_fingerprint
from app.guardrail import PiggyBankGuardrail
from app.models import Decision, TransactionRequest
from app.store import SQLiteStore


def create_app(test_config=None, approval_client=None, store=None):
    app=Flask(__name__)
    app.config.update(SECRET_KEY=os.getenv("FLASK_SECRET_KEY","dev-only-change-me"))
    if test_config:
        app.config.update(test_config)
    database=store or SQLiteStore(app.config.get("DATABASE_PATH",os.getenv("DATABASE_PATH","data/guardrail.db")))
    client=approval_client or N8NApprovalClient()
    engine=PiggyBankGuardrail(database)
    app.extensions["guardrail_store"]=database
    app.extensions["guardrail_engine"]=engine

    @app.get("/health")
    def health():
        return jsonify({"status":"ok","execution_enabled":False})

    @app.get("/")
    def home():
        return render_template("index.html")

    @app.post("/api/transactions/evaluate")
    def evaluate():
        try:
            tx=TransactionRequest.model_validate(request.get_json(force=True))
        except (ValidationError,TypeError,ValueError) as exc:
            return jsonify({"error":"invalid_transaction","details":str(exc)}),400
        result=engine.evaluate(tx)
        database.audit(tx.request_id,"GUARDRAIL_EVALUATED",{"decision":result.decision.value,"reasons":result.reasons})
        base={"request_id":tx.request_id,"decision":result.decision.value,"reasons":result.reasons,"execution_enabled":False}
        if result.decision==Decision.DENY:
            return jsonify(base),403

        if result.decision==Decision.ALLOW:
            if not database.consume_authorization(tx.authorization_id):
                return jsonify({"request_id":tx.request_id,"decision":"DENY","reason":"authorization_expired_revoked_or_replayed","execution_enabled":False}),403
            return jsonify(base),200

        transaction=tx.model_dump(mode="json")
        fingerprint=transaction_fingerprint(transaction)
        if not database.create_approval(tx.request_id,fingerprint,transaction):
            return jsonify({"request_id":tx.request_id,"decision":"DENY","reason":"duplicate_request_id","execution_enabled":False}),409
        database.audit(tx.request_id,"N8N_APPROVAL_SUBMITTED",{"fingerprint":fingerprint})
        decision=client.request_human_approval(transaction)
        if decision!="APPROVE":
            if decision=="DENY":
                database.set_approval_decision(tx.request_id,fingerprint,"DENY","n8n-verified")
            database.audit(tx.request_id,"APPROVAL_NOT_GRANTED",{"decision":decision})
            return jsonify({"request_id":tx.request_id,"decision":"DENY","execution_enabled":False}),403
        if not database.set_approval_decision(tx.request_id,fingerprint,"APPROVE","n8n-verified"):
            return jsonify({"request_id":tx.request_id,"decision":"DENY","reason":"approval_record_mismatch","execution_enabled":False}),403
        if not database.consume_approval(tx.request_id,fingerprint):
            return jsonify({"request_id":tx.request_id,"decision":"DENY","reason":"approval_invalid_or_replayed","execution_enabled":False}),403
        if not database.consume_authorization(tx.authorization_id):
            return jsonify({"request_id":tx.request_id,"decision":"DENY","reason":"authorization_expired_revoked_or_replayed","execution_enabled":False}),403
        database.audit(tx.request_id,"HUMAN_APPROVAL_VERIFIED",{"fingerprint":fingerprint})
        return jsonify({"request_id":tx.request_id,"decision":"APPROVED_PENDING_EXECUTION","execution_enabled":False,
                        "message":"Approval verified. No funds have been transferred."}),200

    @app.get("/api/audit")
    def audit():
        return jsonify(database.list_audit_events())

    return app
