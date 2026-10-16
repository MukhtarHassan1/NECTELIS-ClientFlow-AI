"""Genuine offline HTTP-contract checks; NEVER claims a real provider connection."""
import json
import os
import base64
import hmac
import hashlib
from fastapi.testclient import TestClient
import pytest
from clientflow.api import app
from clientflow.connector_lab import run_ghl_scenario
from clientflow.channel_adapters import (normalize_vapi_report, normalize_twilio_sms,
    validate_twilio_signature, channel_contract_scenario, ChannelPayloadError)

@pytest.mark.parametrize('scenario', ['booking','replay','update','rate_limit','unavailable','unauthorized'])
def test_ghl_http_contract_scenarios(scenario):
    result=run_ghl_scenario(scenario)
    assert result['passed'],result
    assert not result['live_connected']
    assert all(x['path'].startswith(('/contacts/', '/calendars/', '/opportunities/')) for x in result['request_trace'])


def test_ghl_creates_and_books_with_real_connector_methods():
    r=run_ghl_scenario('booking')
    assert r['summary']['provider_requests']==5
    assert r['summary']['appointments']==1
    assert [x['path'] for x in r['request_trace']]==[
       '/contacts/upsert','/opportunities/upsert','/calendars/calendar_mock/free-slots',
       '/calendars/events/appointments','/opportunities/upsert']
    assert all(x['api_version']=='v3' for x in r['request_trace'])


def test_ghl_replay_no_extra_side_effects():
    r=run_ghl_scenario('replay')
    assert r['summary']['appointments']==1
    assert r['summary']['provider_requests']==5
    assert r['event_results'][1]['writes_skipped']


def test_ghl_update_does_not_duplicate_contact_opportunity():
    r=run_ghl_scenario('update')
    assert r['summary']['contacts']==1
    assert r['summary']['opportunities']==1


def test_ghl_auth_error_no_retry_loop():
    r=run_ghl_scenario('unauthorized')
    assert len(r['request_trace'])==1
    assert r['event_results'][0]['manual_review_required']


def test_ghl_rate_limit_tracks_retry():
    r=run_ghl_scenario('rate_limit')
    assert r['summary']['http_429']==1
    assert r['event_results'][0]['attempts']==2


@pytest.mark.parametrize('channel', ['vapi','twilio'])
def test_optional_channel_contracts(channel):
    result=channel_contract_scenario(channel)
    assert result['passed'] and result['live_connected'] is False


def test_vapi_rejects_tool_calls_because_incompatible_response_contract():
    with pytest.raises(ChannelPayloadError):
        normalize_vapi_report({'message':{'type':'tool-calls','call':{'id':'abc'}}},'home-services-demo')


def test_vapi_requires_stable_id():
    with pytest.raises(ChannelPayloadError):
        normalize_vapi_report({'message':{'type':'end-of-call-report','analysis':{'structuredData':{
            'first_name':'Taylor','email':'a@example.com','service':'plumbing'}}}},'home-services-demo')


def test_twilio_form_tamper_detection():
    url='https://example.com/receive';token='secret-token';form={'MessageSid':'SM1','From':'+15550102020','Body':'Hi'}
    computed=base64.b64encode(hmac.new(token.encode(),(url+''.join(k+form[k] for k in sorted(form))).encode(),hashlib.sha1).digest()).decode()
    assert validate_twilio_signature(url,form,computed,token)
    assert not validate_twilio_signature(url,{**form,'Body':'tampered'},computed,token)
    assert not validate_twilio_signature('http://example.com/receive',form,computed,token)
    event=normalize_twilio_sms(form,'home-services-demo')
    assert event.source=='twilio' and not event.lead.consent_to_contact


def test_lab_api_and_inventory():
    with TestClient(app) as client:
        inventory=client.get('/api/v1/integrations').json()
        assert inventory['live_provider_connected'] is False
        for provider, scenario in [('ghl','booking'),('vapi','inbound'),('twilio','inbound')]:
            r=client.post(f'/api/v1/integration-lab/{provider}/{scenario}')
            assert r.status_code==200 and r.json()['passed'] is True
        assert client.post('/api/v1/integration-lab/ghl/nonexistent').status_code==422


def test_inbound_provider_webhooks_default_disabled(monkeypatch):
    monkeypatch.delenv('ENABLE_PROVIDER_WEBHOOKS',raising=False)
    with TestClient(app) as client:
        assert client.post('/api/v1/channels/vapi/home-services-demo',json={}).status_code==503
        assert client.post('/api/v1/channels/twilio/home-services-demo',data={}).status_code==503


def test_vapi_inbound_signed_secret_mock_only(tmp_path,monkeypatch):
    from clientflow import db as store
    monkeypatch.setenv('ENABLE_PROVIDER_WEBHOOKS','true')
    monkeypatch.setenv('VAPI_WEBHOOK_SECRET','test-secret')
    monkeypatch.setenv('DATABASE_URL',f'sqlite:///{tmp_path}/provider.sqlite3')
    payload={'message':{'type':'end-of-call-report','call':{'id':'signed-call-1'},
                        'analysis':{'structuredData':{'first_name':'Alex','email':'signed@example.com',
                          'service':'plumbing','consent_to_contact':False}}}}
    with TestClient(app) as client:
        assert client.post('/api/v1/channels/vapi/home-services-demo',json=payload).status_code==401
        headers={'X-ClientFlow-Provider-Secret':'test-secret'}
        x=client.post('/api/v1/channels/vapi/home-services-demo',json=payload,headers=headers)
        assert x.status_code==200,x.text
        assert x.json()['status']=='needs_review'
        twice=client.post('/api/v1/channels/vapi/home-services-demo',json=payload,headers=headers)
        assert twice.json()['duplicate_event'] is True
    # Avoid leaking a disposed test DB engine to other tests.
    store.connect_db()


def test_bounded_retry_respects_retry_after_and_caps():
    import httpx
    from clientflow.ghl_connector import GHLTestConnector,GHLSettings
    from clientflow.connector_lab import _bounded_contact_upsert
    seen=[];waits=[]
    def respond(req):
        seen.append(req)
        if len(seen)==1:return httpx.Response(429,json={'message':'rate limit'},headers={'Retry-After':'3'})
        return httpx.Response(200,json={'new':True,'contact':{'id':'demo-contact'}})
    conn=GHLTestConnector(GHLSettings('fake','demo'),httpx.MockTransport(respond))
    try:
        r, attempts=_bounded_contact_upsert(conn,email='taylor@example.com',name='Taylor',sleep=waits.append)
        assert attempts==2
        assert 3<=waits[0]<3.03
        assert r['contact']['id']=='demo-contact'
    finally:conn.close()


def test_replay_mutation_rejected_without_writes():
    r=run_ghl_scenario('replay_mutation')
    assert r['passed']
    assert r['event_results'][-1]['outcome']=='replay_conflict'
    assert r['summary']['provider_requests']==5


def test_lost_booking_response_quarantines_instead_of_retrying():
    r=run_ghl_scenario('timeout_after_write')
    assert r['passed'],r
    assert r['event_results'][0]['reconciliation_required']
    assert r['event_results'][0]['retry_appointment_automatically'] is False
    assert r['summary']['appointments']==1


def test_twilio_endpoint_requires_correct_canonical_path_and_signature(monkeypatch,tmp_path):
    from urllib.parse import urlencode
    from clientflow import db as store
    monkeypatch.setenv('DATABASE_URL', f'sqlite:///{tmp_path}/twilio-provider.sqlite3')
    monkeypatch.setenv('ENABLE_PROVIDER_WEBHOOKS','true')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN','synthetic-token')
    path='/api/v1/channels/twilio/home-services-demo'
    canonical='https://webhook.example.com'+path
    monkeypatch.setenv('TWILIO_PUBLIC_WEBHOOK_URL',canonical)
    form={'MessageSid':'SMtest-1001','From':'+15550103030','Body':'I need plumbing help'}
    digest=base64.b64encode(hmac.new(b'synthetic-token', (canonical+''.join(k+form[k] for k in sorted(form))).encode(),hashlib.sha1).digest()).decode()
    with TestClient(app) as client:
        no_sig=client.post(path,content=urlencode(form),headers={'Content-Type':'application/x-www-form-urlencoded'})
        assert no_sig.status_code==401
        good=client.post(path,content=urlencode(form),headers={'Content-Type':'application/x-www-form-urlencoded','X-Twilio-Signature':digest})
        assert good.status_code==200 and '<Response>' in good.text
        again=client.post(path,content=urlencode(form),headers={'Content-Type':'application/x-www-form-urlencoded','X-Twilio-Signature':digest})
        assert again.status_code==200
        monkeypatch.setenv('TWILIO_PUBLIC_WEBHOOK_URL', 'https://webhook.example.com/wrong')
        bad=client.post(path,content=urlencode(form),headers={'Content-Type':'application/x-www-form-urlencoded','X-Twilio-Signature':digest})
        assert bad.status_code==403
    store.connect_db()
