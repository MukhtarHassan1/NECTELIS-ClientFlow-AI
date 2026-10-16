"""Proof must be earned by SQL readbacks, not predeclared in the UI."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from clientflow import db
from sqlalchemy import select


def test_empty_proof_cannot_pass(client):
    assert client.get('/api/v1/proof/verify/home-services-demo/demo_ui/does-not-exist').status_code == 404


def test_actual_local_booking_replays_and_can_be_verified(client, sample):
    data = deepcopy(sample)
    data['event_id'] = 'unpredictable-demo-challenge-7641'
    data['source'] = 'demo_ui'
    data['lead']['first_name'] = 'Taylor Witness'
    data['lead']['email'] = 'newrandom7641@example.com'
    data['lead']['phone'] = None
    data['requested_slot'] = (datetime.now(timezone.utc) + timedelta(days=20)).replace(
        hour=15,minute=0,second=0,microsecond=0).isoformat()
    # Avoid weekend flakiness by allowing either a persisted booked or unavailable record;
    # the readback must still describe what was actually stored.
    first = client.post('/api/v1/leads',json=data)
    assert first.status_code == 200
    second = client.post('/api/v1/leads',json=data)
    assert second.status_code == 200
    assert second.json()['duplicate_event'] is True
    proof = client.get('/api/v1/proof/verify/home-services-demo/demo_ui/'+data['event_id'])
    assert proof.status_code == 200
    result = proof.json()
    assert result['passed'] is True, result
    assert all(result['checks'].values())
    assert result['stored']['first_name'] == 'Taylor Witness'
    assert result['stored']['booking_rows_for_event'] == (1 if first.json()['status']=='booked' else 0)
    assert result['external_provider_called'] is False
    mutated = deepcopy(data)
    mutated['lead']['first_name']='Changed Witness'
    assert client.post('/api/v1/leads',json=mutated).status_code == 409
    assert client.get('/api/v1/state').json()['stats']['events'] == 1


def test_verifier_detects_corrupt_linkage(client, sample):
    data=deepcopy(sample)
    data['source']='demo_ui'
    assert client.post('/api/v1/leads',json=data).status_code==200
    with db.session() as sess:
        event = sess.scalar(select(db.Event).where(db.Event.external_event_id==data['event_id']))
        event.contact_id='missing-contact-id'
        sess.commit()
    result=client.get('/api/v1/proof/verify/home-services-demo/demo_ui/'+data['event_id']).json()
    assert result['passed'] is False
    assert result['checks']['contact_record_is_linked'] is False


def test_readback_respects_admin_key(client, sample, monkeypatch):
    client.post('/api/v1/leads',json=sample)
    monkeypatch.setenv('ADMIN_API_KEY','secret')
    url='/api/v1/proof/verify/home-services-demo/website_form/'+sample['event_id']
    assert client.get(url).status_code==401
    assert client.get(url,headers={'x-clientflow-admin':'secret'}).status_code==200
