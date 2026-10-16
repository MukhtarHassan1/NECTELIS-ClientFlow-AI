"""Fresh-input orchestration and webhook security regression tests."""
import os,base64,hmac,hashlib,json
from datetime import datetime,timedelta,timezone
import httpx,pytest
from sqlalchemy import select
from clientflow import db
from clientflow.twilio_gateway import (TwilioSettings,TwilioGateway,TwilioGatewayError,
    save_dispatch,apply_status_callback)
from clientflow.channel_adapters import normalize_vapi_report
from clientflow.ghl_connector import GHLSettings
from clientflow.live_bridge import authorized_ghl_test

@pytest.mark.parametrize('provider,scenarios',[
 ('ghl',['success','rate_limit','unavailable','unauthorized','timeout']),
 ('vapi',['success','duplicate','malformed']),
 ('twilio',['success','tamper','rate_limit','delivery_failed'])])
def test_dynamic_workbench_matrix(client,provider,scenarios):
    for scenario in scenarios:
        r=client.post('/api/v1/workbench/run',json={'provider':provider,'scenario':scenario,
                    'name':'Morgan Synth','phrase':'client-chooses-70819'})
        assert r.status_code==200,r.text
        assert r.json()['passed'],r.json()
        assert r.json()['actual_provider_calls']==0


def test_more_than_one_vapi_run_writes_distinct_bookings(client):
    for i in range(18):
        r=client.post('/api/v1/workbench/run',json={'provider':'vapi','scenario':'success',
                       'name':f'Morgan {i}','phrase':'fresh-context-77'})
        assert r.status_code==200 and r.json()['passed'],r.text
    s=client.get('/api/v1/state').json()
    assert s['stats']['bookings']==18


def test_random_provider_and_bad_contact_are_blocked(client):
    for provider in ('gohighlevel','https://evil.example','twilio/../../'):
        res=client.post('/api/v1/workbench/run',json={'provider':provider,'scenario':'success',
                   'name':'Morgan','phrase':'xyz-789'})
        assert res.status_code==422
    bad=client.post('/api/v1/workbench/run',json={'provider':'twilio','scenario':'success',
             'name':'<img src=x onerror=alert(1)>','phrase':'test'})
    assert bad.status_code==422


def _sign(url,params,token):
    return base64.b64encode(hmac.new(token.encode(),
        (url+''.join(k+params[k] for k in sorted(params))).encode(),hashlib.sha1).digest()).decode()


def test_twilio_real_status_endpoint_rejects_spoof_and_replays(client,monkeypatch):
    monkeypatch.setenv('ENABLE_PROVIDER_WEBHOOKS','true')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN','secret-example')
    url='https://demohost.example/api/v1/channels/twilio/status'
    monkeypatch.setenv('TWILIO_STATUS_CALLBACK_URL',url)
    sid='SM'+'2'*32
    save_dispatch(job_id='test-signed-callback',message_sid=sid,initial_status='queued')
    form={'MessageSid':sid,'MessageStatus':'delivered'}
    invalid=client.post('/api/v1/channels/twilio/status',data=form,headers={'X-Twilio-Signature':'invalid'})
    assert invalid.status_code==401
    signed=_sign(url,form,'secret-example')
    valid=client.post('/api/v1/channels/twilio/status',data=form,headers={'X-Twilio-Signature':signed})
    assert valid.status_code==200 and valid.json()['status']=='delivered'
    back={'MessageSid':sid,'MessageStatus':'queued'}
    again=client.post('/api/v1/channels/twilio/status',data=back,headers={'X-Twilio-Signature':_sign(url,back,'secret-example')})
    assert again.status_code==200 and again.json()['ignored_transition']
    with db.session() as s:
        assert s.scalar(select(db.Delivery).where(db.Delivery.message_sid==sid)).status=='delivered'


def test_twilio_outbound_guard_and_real_http_transport():
    sid='AC'+'3'*32
    reqs=[]
    def mock(req):
        reqs.append(req)
        assert req.url.path==f'/2010-04-01/Accounts/{sid}/Messages.json'
        assert req.headers['Authorization'].startswith('Basic ')
        data=req.content.decode()
        assert 'StatusCallback=' in data and 'To=' in data and 'From=' in data
        return httpx.Response(201,json={'sid':'SM'+'4'*32,'status':'queued'})
    cfg=TwilioSettings(sid,'demo-token','+15550000111','https://callback.example/status')
    gateway=TwilioGateway(cfg,httpx.MockTransport(mock))
    with pytest.raises(PermissionError):
        gateway.send_sms(to='+15550000222',body='Hello',consent=False,approved_recipients={'+15550000222'},allow_outbound=True)
    with pytest.raises(PermissionError):
        gateway.send_sms(to='+15550000222',body='Hello',consent=True,approved_recipients=set(),allow_outbound=True)
    assert not reqs
    reply=gateway.send_sms(to='+15550000222',body='Hello',consent=True,approved_recipients={'+15550000222'},allow_outbound=True)
    assert reply['status']=='queued' and len(reqs)==1
    gateway.close()


def test_vapi_structured_data_under_call_analysis():
    event=normalize_vapi_report({'message':{'type':'end-of-call-report',
       'call':{'id':'voice-100','analysis':{'structuredData':{'first_name':'Alex',
              'email':'alex@example.com','service':'plumbing','consent_to_contact':True}}}}},'home-services-demo')
    assert event.lead.service=='plumbing'


def test_ghl_live_gate_rejects_without_writing(client,monkeypatch):
    cfg=GHLSettings('offline-test-token','loc','cal','pipeline','qualified','booked')
    with pytest.raises(PermissionError):
        authorized_ghl_test(event_id='job100',name='Alex',email='test@example.com',
                 start=datetime.now(timezone.utc)+timedelta(days=7),config=cfg,
                 approved_emails={'test@example.com'},write_enabled=False)
    with db.session() as s:
        assert s.scalar(select(db.ProviderJob)) is None


def test_ghl_started_live_job_is_not_retried(client,monkeypatch):
    cfg=GHLSettings('test-token','loc','cal','pipe','qualified','booked')
    called=[]
    def fake(**kwargs):
        called.append(1)
        return {'outcome':'reconcile_booking','contact_id':'test'}
    monkeypatch.setattr('clientflow.live_bridge.run_ghl_job',fake)
    args={'event_id':'unique-123','name':'Alex','email':'alex@example.com',
          'start':datetime.now(timezone.utc)+timedelta(days=7),'config':cfg,
          'approved_emails':{'alex@example.com'},'write_enabled':True}
    first=authorized_ghl_test(**args)
    second=authorized_ghl_test(**args)
    assert first['outcome']=='reconcile_booking' and second['outcome']=='requires_remote_reconciliation'
    assert len(called)==1


def test_vapi_webhook_auth_and_local_booking(client,monkeypatch):
    monkeypatch.setenv('ENABLE_PROVIDER_WEBHOOKS','true')
    monkeypatch.setenv('VAPI_WEBHOOK_SECRET','synthetic-secret')
    body={'message':{'type':'end-of-call-report','call':{'id':'authorized-test-call-1003'},
          'analysis':{'structuredData':{'first_name':'Synthetic','email':'vapi-incoming@example.com',
              'service':'plumbing','consent_to_contact':True}}}}
    url='/api/v1/channels/vapi/home-services-demo'
    rejected=client.post(url,json=body)
    assert rejected.status_code==401
    received=client.post(url,json=body,headers={'X-Vapi-Secret':'synthetic-secret'})
    assert received.status_code==200,received.text
    assert received.json()['status']=='qualified_no_booking_requested'
    repeat=client.post(url,json=body,headers={'X-Vapi-Secret':'synthetic-secret'})
    assert repeat.json()['duplicate_event'] is True


def test_vapi_to_ghl_requires_approval(client,monkeypatch):
    monkeypatch.setenv('ENABLE_PROVIDER_WEBHOOKS','true')
    monkeypatch.setenv('VAPI_WEBHOOK_SECRET','demo-secret')
    monkeypatch.setenv('ENABLE_GHL_WEBHOOK_BRIDGE','true')
    monkeypatch.setenv('GHL_LIVE_TEST_WRITE_ENABLED','NO')
    body={'message':{'type':'end-of-call-report','call':{'id':'bridge-call-1003'},
          'analysis':{'structuredData':{'first_name':'Synthetic','email':'bridge@example.com',
              'service':'plumbing','consent_to_contact':True}}}}
    blocked=client.post('/api/v1/channels/vapi/home-services-demo',json=body,
                        headers={'X-Vapi-Secret':'demo-secret'})
    assert blocked.status_code==503
