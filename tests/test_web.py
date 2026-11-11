from app.web import create_app
from app.store import SQLiteStore
class Approve:
    def request_human_approval(self,tx): return 'APPROVE'
class Deny:
    def request_human_approval(self,tx): return 'DENY'
def payload(): return {'request_id':'web-1','agent_id':'agent','intent':'buy item','intended_amount':'10','amount':'20','recipient':'unknown.testnet','asset':'NEAR','network':'testnet'}
def test_approval_is_not_execution(tmp_path):
    app=create_app({'TESTING':True},Approve(),SQLiteStore(str(tmp_path/'w.db'))); r=app.test_client().post('/api/transactions/evaluate',json=payload())
    assert r.status_code==200 and r.json['decision']=='APPROVED_PENDING_EXECUTION' and r.json['execution_enabled'] is False
def test_denial_fails_closed(tmp_path):
    app=create_app({'TESTING':True},Deny(),SQLiteStore(str(tmp_path/'w.db'))); r=app.test_client().post('/api/transactions/evaluate',json=payload())
    assert r.status_code==403 and r.json['decision']=='DENY'
def test_health(tmp_path):
    app=create_app({'TESTING':True},store=SQLiteStore(str(tmp_path/'h.db'))); assert app.test_client().get('/health').json['execution_enabled'] is False
