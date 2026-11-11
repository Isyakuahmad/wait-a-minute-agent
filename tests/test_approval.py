from app.approval import N8NApprovalClient,transaction_fingerprint
class Response:
    def __init__(self,data): self.data=data
    def raise_for_status(self): pass
    def json(self): return self.data
class Session:
    def __init__(self,status): self.status=status
    def post(self,*a,**k): return Response({'request_id':'req-1','status':'PENDING'})
    def get(self,*a,**k): return Response(self.status)
def make(status): return N8NApprovalClient('https://n8n/submit','https://n8n/status','secret',1,0,Session(status))
def test_matching_approval():
    tx={'request_id':'req-1','amount':'2'}; fp=transaction_fingerprint(tx); assert make({'request_id':'req-1','fingerprint':fp,'decision':'APPROVE'}).request_human_approval(tx)=='APPROVE'
def test_tampered_fingerprint_denied():
    tx={'request_id':'req-1','amount':'2'}; assert make({'request_id':'req-1','fingerprint':'wrong','decision':'APPROVE'}).request_human_approval(tx)=='DENY'
def test_unknown_decision_denied():
    tx={'request_id':'req-1'}; fp=transaction_fingerprint(tx); assert make({'request_id':'req-1','fingerprint':fp,'decision':'MAYBE'}).request_human_approval(tx)=='DENY'
