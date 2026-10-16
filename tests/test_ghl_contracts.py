from datetime import datetime, timezone, timedelta
import json
import httpx
import pytest
from clientflow.ghl_connector import GHLSettings,GHLTestConnector,GHLAPIError


def test_authorized_ghl_contact_contract_shape_offline():
    seen=[]
    def respond(req):
        seen.append(req)
        return httpx.Response(200,json={'new':True,'contact':{'id':'synthetic-id'}})
    c=GHLTestConnector(GHLSettings(token='fake-placeholder',location_id='mock-location'),
                       transport=httpx.MockTransport(respond))
    x=c.upsert_contact(first_name='Alex',email='alex@example.com')
    assert x['contact']['id']=='synthetic-id'
    assert seen[0].url.path=='/contacts/upsert'
    assert json.loads(seen[0].content)['createNewIfDuplicateAllowed'] is False
    assert seen[0].headers['Version']=='v3'
    c.close()


def test_ghl_free_slots_request_is_read_only():
    seen=[]
    def respond(req):
        seen.append(req)
        return httpx.Response(200,json={'2030-10-16':{'slots':[]}})
    c=GHLTestConnector(GHLSettings('fake','mock-location',calendar_id='mock-calendar'),httpx.MockTransport(respond))
    start=datetime(2030,10,16,tzinfo=timezone.utc)
    c.free_slots(start,start+timedelta(days=1),'America/New_York')
    assert seen[0].method=='GET' and seen[0].url.path.endswith('/free-slots')
    assert 'startDate' in seen[0].url.params
    c.close()


def test_ghl_booking_disables_native_notification_and_force_skip():
    seen=[]
    def respond(req):
        seen.append(req)
        return httpx.Response(200,json={'id':'mock-appointment'})
    c=GHLTestConnector(GHLSettings('fake','mock-location',calendar_id='mock-calendar'),httpx.MockTransport(respond))
    start=datetime(2030,10,16,tzinfo=timezone.utc)
    c.book_test_appointment(contact_id='mock-contact',start=start,end=start+timedelta(hours=1))
    payload=json.loads(seen[0].content)
    assert payload['toNotify'] is False and payload['ignoreFreeSlotValidation'] is False
    assert seen[0].headers['Version']=='v3'
    c.close()


def test_ghl_401_classified_no_retry():
    c=GHLTestConnector(GHLSettings('fake','mock-location'),httpx.MockTransport(lambda req:httpx.Response(401,json={})))
    with pytest.raises(GHLAPIError) as e:c.upsert_contact(first_name='Alex',email='alex@example.com')
    assert e.value.status_code==401
    c.close()
