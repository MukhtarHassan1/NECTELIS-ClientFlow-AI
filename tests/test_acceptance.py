from __future__ import annotations
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import pytest
from clientflow import db as store
from sqlalchemy import select


def send(client,payload):
    response=client.post('/api/v1/leads',json=payload)
    assert response.status_code==200,response.text
    return response.json()


def count(client, key):return client.get('/api/v1/state').json()['stats'][key]

def test_CF_T01_new_lead_books_once(client,sample):
    r=send(client,sample)
    assert r['status']=='booked' and r['crm_action']=='created'
    assert r['appointment_id'] and r['opportunity_stage']=='Appointment Booked'
    assert r['notification_status']=='logged_only'
    assert r['follow_up_status']=='queued_for_human_review'
    assert count(client,'contacts')==1 and count(client,'bookings')==1


def test_CF_T02_existing_lead_updated(client,sample):
    first=send(client,sample)
    p=deepcopy(sample);p['event_id']='test-update-02';p['lead']['phone']='+15550101002';p['requested_slot']=None
    result=send(client,p)
    assert result['crm_action']=='updated' and result['contact_id']==first['contact_id']
    assert count(client,'contacts')==1


def test_CF_T03_replay_prevents_every_duplicate_action(client,sample):
    before=send(client,sample)
    counts=client.get('/api/v1/state').json()['stats']
    repeat=send(client,sample)
    assert repeat['duplicate_event'] is True and repeat['appointment_id']==before['appointment_id']
    assert client.get('/api/v1/state').json()['stats']==counts


def test_CF_T04_missing_required_service_422(client,sample):
    p=deepcopy(sample);p['lead'].pop('service')
    r=client.post('/api/v1/leads',json=p)
    assert r.status_code==422 and count(client,'contacts')==0


def test_CF_T05_no_consent_does_not_book(client,sample):
    p=deepcopy(sample);p['lead']['consent_to_contact']=False
    r=send(client,p)
    assert r['status']=='needs_review' and not r['appointment_id']
    assert r['notification_status']=='logged_only'
    trace=client.get('/api/v1/audit/'+p['event_id']).json()['timeline']
    assert any(a['step']=='external_communication' and a['outcome']=='suppressed' for a in trace)


def test_CF_T06_outside_hours_slot_rejected(client,sample):
    p=deepcopy(sample);p['requested_slot']='2030-10-16T01:00:00-04:00'
    r=send(client,p)
    assert r['status']=='slot_unavailable' and not r['appointment_id'] and count(client,'bookings')==0


def test_CF_T07_competing_same_slot_only_one_wins(client,sample):
    one=deepcopy(sample);two=deepcopy(sample);two['event_id']='cf-test-0002';two['lead']['email']='other@example.com';two['lead']['phone']='+15550101002'
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(send,client,item) for item in (one,two)]
        results=[f.result() for f in futures]
    assert sorted(x['status'] for x in results)==['booked','slot_unavailable']
    assert count(client,'bookings')==1


def test_CF_T08_retries_429_then_succeeds(client,sample):
    p=deepcopy(sample);p['simulate']={'crm':'429,200'}
    r=send(client,p)
    assert r['status']=='booked'
    log=client.get('/api/v1/audit/'+p['event_id']).json()['timeline']
    assert any(x['step']=='crm' and x['outcome']=='retry' for x in log)
    assert any(x['step']=='crm' and x['outcome']=='ok' and x['attempts']==2 for x in log)


def test_CF_T09_provider_401_stops_without_any_crm_write(client,sample):
    p=deepcopy(sample);p['simulate']={'crm':'401'}
    r=send(client,p)
    assert r['status']=='connector_failed' and not r['appointment_id']
    assert r['retryable'] is False and count(client,'contacts')==0
    log=client.get('/api/v1/audit/'+p['event_id']).json()['timeline']
    assert not any(x['step']=='crm' and x['outcome']=='retry' for x in log)


def test_CF_T10_calendar_timeout_failure_is_explicit(client,sample):
    p=deepcopy(sample);p['simulate']={'calendar':'504'}
    r=send(client,p)
    assert r['status']=='connector_failed' and count(client,'bookings')==0
    assert r['retryable'] is True


def test_CF_T11_notification_failure_keeps_booking(client,sample):
    p=deepcopy(sample);p['simulate']={'notification':'503'}
    r=send(client,p)
    assert r['status']=='booked' and r['notification_status']=='failed_logged'
    assert count(client,'bookings')==1


def test_CF_T12_second_industry_config_no_code_change(client,sample):
    p=deepcopy(sample);p['client_key']='real-estate-demo';p['lead']['service']='property_viewing'
    r=send(client,p)
    assert r['status']=='booked' and r['opportunity_stage']=='Viewing Scheduled'


def test_CF_T13_dry_run_zero_writes(client,sample,monkeypatch):
    monkeypatch.setenv('DRY_RUN','true')
    r=send(client,sample)
    assert r['status']=='dry_run' and r['writes']==0
    assert all(v==0 for v in client.get('/api/v1/state').json()['stats'].values())


def test_CF_T14_external_messaging_always_suppressed(client,sample,monkeypatch):
    # Even if a caller sets a dangerous outbound flag, no transport exists in mock mode.
    monkeypatch.setenv('LIVE_OUTBOUND_ENABLED','true')
    p=deepcopy(sample);p['lead']['email']='outside@example.org'
    r=send(client,p)
    assert r['status']=='booked' and r['notification_status']=='logged_only'
    assert set(x['channel'] for x in client.get('/api/v1/state').json()['notifications'])=={'local_test_log'}


def test_unrecognized_service_routes_to_review(client,sample):
    p=deepcopy(sample);p['lead']['service']='dentistry'
    r=send(client,p)
    assert r['status']=='needs_review' and r['qualification']['label']=='review'


def test_identity_conflict_flags_manual_review(client,sample):
    a=deepcopy(sample);a['requested_slot']=None;send(client,a)
    b=deepcopy(sample);b['event_id']='second-evt';b['lead']['email']='different@example.com';b['lead']['phone']='+15550101002';send(client,b)
    c=deepcopy(sample);c['event_id']='third-evt';c['lead']['phone']='+15550101002'
    result=send(client,c)
    assert result['status']=='needs_review' and count(client,'contacts')==2


def test_same_email_across_profiles_is_distinct(client,sample):
    a=send(client,sample)
    b=deepcopy(sample);b['client_key']='real-estate-demo';b['lead']['service']='property_viewing';b['event_id']='re-evt'
    r=send(client,b)
    assert r['crm_action']=='created' and r['contact_id']!=a['contact_id']


def test_invalid_phone_fails_validation(client,sample):
    p=deepcopy(sample);p['lead']['phone']='123'
    assert client.post('/api/v1/leads',json=p).status_code==422


def test_api_unknown_profile_returns_422(client,sample):
    p=deepcopy(sample);p['client_key']='bad-profile'
    assert client.post('/api/v1/leads',json=p).status_code==422


def test_authentication_guards(client,sample,monkeypatch):
    monkeypatch.setenv('WEBHOOK_API_KEY','only-secure-test-key')
    assert client.post('/api/v1/leads',json=sample).status_code==401
    assert client.post('/api/v1/leads',json=sample,headers={'X-Clientflow-Key':'only-secure-test-key'}).status_code==200
    monkeypatch.setenv('ADMIN_API_KEY','admin-only-secure-key')
    assert client.get('/api/v1/state').status_code==401
    assert client.get('/api/v1/state',headers={'X-Clientflow-Admin':'admin-only-secure-key'}).status_code==200


def test_reset_only_synthetic_tables(client,sample):
    send(client,sample)
    r=client.post('/api/v1/admin/reset')
    assert r.status_code==200
    assert all(v==0 for v in client.get('/api/v1/state').json()['stats'].values())


def test_trace_excludes_raw_email_and_message(client,sample):
    send(client,sample)
    raw=client.get('/api/v1/audit/'+sample['event_id']).text
    assert sample['lead']['email'] not in raw
    assert sample['lead']['message'] not in raw


def test_partial_hour_slot_overlap_is_blocked(client, sample):
    a=deepcopy(sample)
    first=send(client,a)
    second=deepcopy(sample)
    second['event_id']='overlap-evt'
    second['lead']['email']='overlap@example.com'
    second['lead']['phone']=None
    second['requested_slot']='2030-10-16T14:30:00-04:00'
    second_result=send(client,second)
    assert first['status']=='booked' and second_result['status']=='slot_unavailable'
    assert count(client,'bookings')==1


def test_CF_T10_mock_timeout_after_write_reconciles_without_duplicate(client,sample):
    p=deepcopy(sample)
    p['simulate']={'calendar':'timeout_after_create'}
    result=send(client,p)
    assert result['status']=='booked' and count(client,'bookings')==1
    log=client.get('/api/v1/audit/'+p['event_id']).json()['timeline']
    assert any(x['outcome']=='reconciled' for x in log)
    again=send(client,p)
    assert again['duplicate_event'] and count(client,'bookings')==1


def test_failed_calendar_sends_internal_review_not_a_second_booking(client,sample):
    p=deepcopy(sample);p['simulate']={'calendar':'401'}
    result=send(client,p)
    assert result['status']=='connector_failed' and result['follow_up_status']=='queued_for_human_review'
    assert count(client,'bookings')==0
    assert client.get('/api/v1/state').json()['contacts'][0]['stage']=='Needs Human Review'
