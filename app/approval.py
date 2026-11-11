import hashlib, json, os, time
from typing import Any
import requests

def transaction_fingerprint(transaction: dict[str, Any]) -> str:
    canonical=json.dumps(transaction,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

class N8NApprovalClient:
    """Submit once, poll status, verify exact request/fingerprint; fail closed."""
    def __init__(self, webhook_url=None, status_url=None, api_token=None, timeout_seconds=None, poll_interval=None, session=None):
        self.webhook_url=webhook_url or os.getenv("N8N_WEBHOOK_URL")
        self.status_url=status_url or os.getenv("N8N_STATUS_URL")
        self.api_token=api_token or os.getenv("N8N_API_TOKEN")
        self.timeout_seconds=int(timeout_seconds or os.getenv("N8N_TIMEOUT_SECONDS","300"))
        self.poll_interval=int(poll_interval or os.getenv("N8N_POLL_INTERVAL_SECONDS","3"))
        self.session=session or requests.Session()

    def request_human_approval(self, transaction: dict[str,Any]) -> str:
        if not self.webhook_url or not self.status_url or not self.api_token: return "DENY"
        request_id=transaction.get("request_id"); fingerprint=transaction_fingerprint(transaction)
        headers={"Authorization":f"Bearer {self.api_token}","Content-Type":"application/json"}
        try:
            response=self.session.post(self.webhook_url,json={"request_id":request_id,"transaction":transaction,"fingerprint":fingerprint,"status":"PENDING"},headers=headers,timeout=10)
            response.raise_for_status(); ack=response.json()
            if ack.get("request_id")!=request_id or ack.get("status")!="PENDING": return "DENY"
            deadline=time.monotonic()+self.timeout_seconds
            while time.monotonic()<deadline:
                result=self.session.get(self.status_url,params={"request_id":request_id},headers=headers,timeout=10)
                result.raise_for_status(); data=result.json()
                if data.get("request_id")!=request_id or data.get("fingerprint")!=fingerprint: return "DENY"
                decision=data.get("decision")
                if decision in {"APPROVE","DENY"}: return decision
                if decision!="PENDING": return "DENY"
                time.sleep(self.poll_interval)
        except (requests.RequestException,ValueError,TypeError,KeyError): return "DENY"
        return "DENY"
