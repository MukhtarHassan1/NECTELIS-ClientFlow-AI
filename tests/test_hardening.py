"""Regression checks added during Signal Room redesign."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import pytest


def test_changed_payload_cannot_reuse_event_id(client, sample):
    one = client.post('/api/v1/leads', json=sample)
    assert one.status_code == 200
    changed = deepcopy(sample)
    changed['lead']['message'] = 'Different text for the SAME source event ID'
    again = client.post('/api/v1/leads', json=changed)
    assert again.status_code == 409
    assert 'different' in again.json()['detail'].lower()
    assert client.get('/api/v1/state').json()['stats']['events'] == 1


def test_received_at_metadata_does_not_break_valid_replay(client, sample):
    first = client.post('/api/v1/leads', json=sample)
    replay = deepcopy(sample)
    replay['received_at'] = '2030-09-01T11:00:00Z'
    second = client.post('/api/v1/leads', json=replay)
    assert first.status_code == second.status_code == 200
    assert second.json()['duplicate_event'] is True


def test_cross_profile_audit_ids_require_scoping(client, sample):
    first = client.post('/api/v1/leads', json=sample)
    assert first.status_code == 200
    second = deepcopy(sample)
    second['client_key'] = 'real-estate-demo'
    second['lead']['service'] = 'property_viewing'
    another = client.post('/api/v1/leads', json=second)
    assert another.status_code == 200
    assert client.get('/api/v1/audit/'+sample['event_id']).status_code == 409
    a = client.get('/api/v1/audit/home-services-demo/'+sample['event_id']).json()
    b = client.get('/api/v1/audit/real-estate-demo/'+sample['event_id']).json()
    assert a['client_key']=='home-services-demo'
    assert b['client_key']=='real-estate-demo'
    assert a['result']['contact_id'] != b['result']['contact_id']


def test_past_slot_rejected_without_booking(client, sample):
    event = deepcopy(sample)
    event['requested_slot'] = (datetime.now(timezone.utc)-timedelta(days=5)).isoformat()
    r = client.post('/api/v1/leads', json=event)
    assert r.status_code == 200
    assert r.json()['status'] == 'slot_unavailable'
    assert client.get('/api/v1/state').json()['stats']['bookings']==0
    audit = client.get('/api/v1/audit/home-services-demo/'+event['event_id']).json()
    assert any('past' in a['detail'].lower() for a in audit['timeline'])


def test_local_browser_foreign_origin_cannot_reset(client, sample):
    client.post('/api/v1/leads', json=sample)
    remote = client.post('/api/v1/admin/reset', headers={'Origin':'https://evil.example'})
    assert remote.status_code==403
    assert client.get('/api/v1/state').json()['stats']['events']==1
    allowed = client.post('/api/v1/admin/reset', headers={'Origin':'http://testserver'})
    assert allowed.status_code==200


def test_unauthenticated_validation_failure_does_not_mutate_rejections(client,sample,monkeypatch):
    monkeypatch.setenv('WEBHOOK_API_KEY','required-key')
    malformed=deepcopy(sample)
    malformed['lead'].pop('service')
    assert client.post('/api/v1/leads',json=malformed).status_code==401
    monkeypatch.delenv('WEBHOOK_API_KEY')
    assert client.get('/api/v1/state').json()['stats']['rejections']==0


def test_public_profiles_have_no_secrets(client):
    r=client.get('/api/v1/profiles')
    assert r.status_code==200 and len(r.json())==2
    assert all('services' in p and 'timezone' in p for p in r.json())


def test_crm_error_before_contact_still_creates_operator_action(client,sample):
    item=deepcopy(sample);item['simulate']={'crm':'401'}
    result=client.post('/api/v1/leads',json=item).json()
    assert result['status']=='connector_failed'
    assert result['follow_up_status']=='queued_for_human_review'
    assert client.get('/api/v1/state').json()['stats']['followups']==1


def test_existing_future_appointment_not_downgraded_by_info_update(client,sample):
    first=client.post('/api/v1/leads',json=sample).json()
    assert first['status']=='booked'
    update=deepcopy(sample);update['event_id']='info-refresh';update['requested_slot']=None
    update['lead']['message']='Updated details, no new appointment'
    second=client.post('/api/v1/leads',json=update).json()
    assert second['status']=='qualified_no_booking_requested'
    assert second['opportunity_stage']=='Appointment Booked'
    assert client.get('/api/v1/state').json()['stats']['bookings']==1


def test_audit_safely_distinguishes_event_source_with_same_id(client,sample):
    first=client.post('/api/v1/leads',json=sample)
    assert first.status_code==200
    another=deepcopy(sample);another['source']='n8n';another['requested_slot']=None
    second=client.post('/api/v1/leads',json=another)
    assert second.status_code==200
    assert client.get('/api/v1/audit/home-services-demo/'+sample['event_id']).status_code==409
    one=client.get('/api/v1/audit/home-services-demo/website_form/'+sample['event_id']).json()
    two=client.get('/api/v1/audit/home-services-demo/n8n/'+sample['event_id']).json()
    assert one['source']=='website_form' and two['source']=='n8n'
    assert one['result']['audit_id']!=two['result']['audit_id']
