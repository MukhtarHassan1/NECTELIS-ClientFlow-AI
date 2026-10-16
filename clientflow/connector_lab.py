"""Offline, executable HighLevel provider-contract lab.

It deliberately routes real GHL connector methods through httpx.MockTransport.
No GHL HTTP requests leave this machine. Unlike a static screenshot, all four
methods are executed and inspected, including negative paths and replay.
"""
from __future__ import annotations
import json
import time
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import httpx
from .ghl_connector import GHLTestConnector, GHLSettings, GHLAPIError

@dataclass
class DemoProvider:
    scenario: str = 'booking'
    contacts: dict = field(default_factory=dict)
    opportunities: dict = field(default_factory=dict)
    bookings: dict = field(default_factory=dict)
    traces: list = field(default_factory=list)
    crm_requests: int = 0
    attempts: int = 0
    def reply(self, req: httpx.Request) -> httpx.Response:
        method, path = req.method, req.url.path
        payload = json.loads(req.content) if req.content else {}
        entry = {'method':method,'path':path, 'api_version':req.headers.get('Version'),
                 'status':200,'operation':'', 'payload_fields':sorted(payload.keys()) if isinstance(payload,dict) else []}
        def response(code, content, operation):
            entry['status']=code
            entry['operation']=operation
            self.traces.append(entry)
            return httpx.Response(code,json=content,headers={'Retry-After':'2'} if code==429 else {})
        if req.headers.get('Authorization')!='Bearer offline-fake-token':
            return response(401, {'message':'Unauthorized'}, 'auth_rejected')
        if path == '/contacts/upsert' and method=='POST':
            self.crm_requests += 1
            if self.scenario=='rate_limit' and self.crm_requests==1:
                return response(429, {'message':'Rate limit'}, 'throttled')
            if self.scenario=='unauthorized':
                return response(401, {'message':'Unauthorized'}, 'permission_blocked')
            email=payload.get('email')
            if not email or not email.endswith('@example.com'):
                return response(422, {'message':'Synthetic identities only'}, 'input_rejected')
            contact=self.contacts.get(email)
            created=contact is None
            if created:
                contact={'id':'contact_mock_'+str(len(self.contacts)+1)}
            contact.update({'firstName':payload['firstName'], 'email':email})
            self.contacts[email]=contact
            return response(200, {'new':created,'contact':contact},'contact_created' if created else 'contact_updated')
        if path=='/opportunities/upsert' and method=='POST':
            cid=payload.get('contactId')
            if not cid or not payload.get('pipelineId') or not payload.get('pipelineStageId'):
                return response(422, {'message':'Missing pipeline identity'}, 'opportunity_rejected')
            existing=self.opportunities.get(cid)
            created=existing is None
            opportunity=existing or {'id':'opp_mock_'+str(len(self.opportunities)+1)}
            opportunity.update({'contactId':cid,'pipelineStageId':payload['pipelineStageId']})
            self.opportunities[cid]=opportunity
            return response(200,{'new':created,'opportunity':opportunity},'opportunity_created' if created else 'stage_updated')
        if path.endswith('/free-slots') and method=='GET':
            begin=datetime.fromtimestamp(int(req.url.params['startDate'])/1000,timezone.utc)
            day=begin.date().isoformat()
            free= [] if self.scenario=='unavailable' or self.bookings else [begin.isoformat()]
            return response(200,{day:{'slots':free}},'availability_checked')
        if path=='/calendars/events/appointments' and method=='POST':
            start=payload.get('startTime')
            if payload.get('ignoreFreeSlotValidation') or payload.get('toNotify'):
                return response(422,{'message':'Unsafe booking flags'},'safety_rejected')
            if self.scenario=='unavailable' or start in self.bookings or self.bookings:
                return response(409,{'message':'Slot unavailable'},'booking_conflict')
            booking={'id':'appt_mock_1', 'startTime':start,'contactId':payload['contactId']}
            self.bookings[start]=booking
            if self.scenario=='timeout_after_write':
                response(200, booking, 'appointment_committed_but_response_lost')
                raise httpx.ReadTimeout('Offline injected lost response AFTER provider commit')
            return response(200, booking, 'appointment_booked')
        return response(404,{'message':'Unknown endpoint'},'contract_mismatch')

def _is_offered(reply: dict, start: datetime) -> bool:
    target = start.astimezone(timezone.utc)
    for date_info in reply.values():
        for slot in date_info.get('slots',[]):
            try:
                if datetime.fromisoformat(slot.replace('Z','+00:00')).astimezone(timezone.utc)==target:
                    return True
            except (TypeError,ValueError):
                pass
    return False

def _bounded_contact_upsert(connector: GHLTestConnector, *, email: str, name: str, sleep=time.sleep):
    """Respect 429 Retry-After with capped retries. Only safe contact-upsert path is retried.

    Provider duplicate settings still require independent live validation.
    Never automatically retry uncertain appointment creation.
    """
    for attempt in range(1, 4):
        try:
            return connector.upsert_contact(first_name=name,email=email), attempt
        except GHLAPIError as exc:
            if exc.status_code not in (429,500,502,503,504) or attempt == 3:
                raise
            try: delay=float(exc.retry_after) if exc.retry_after else (2 ** (attempt - 1))
            except (ValueError,TypeError): delay=2 ** (attempt - 1)
            sleep(max(0,min(delay,30)) + random.uniform(0,.025))
    raise RuntimeError('Unexpected retry control flow')


def run_ghl_scenario(scenario: str) -> dict:
    if scenario not in ('booking','replay','replay_mutation','update','rate_limit','unavailable','unauthorized','timeout_after_write'):
        raise ValueError('Unknown offline GHL test')
    provider=DemoProvider(scenario=scenario)
    config=GHLSettings('offline-fake-token','location_mock','calendar_mock','pipeline_mock','stage_qualified')
    connector=GHLTestConnector(config,httpx.MockTransport(provider.reply))
    start=(datetime.now(timezone.utc)+timedelta(days=14)).replace(hour=14,minute=0,second=0,microsecond=0)
    end=start+timedelta(minutes=30)
    ledger={}
    events=[]
    def execute(eid: str, email: str, name: str='Taylor') -> dict:
        if eid in ledger:
            old=ledger[eid]
            if old['identity'] != (email,name):
                return {'event':eid,'outcome':'replay_conflict','writes_skipped':True,
                        'reason':'Same provider event ID with changed identity requires review'}
            return {'event':eid,'outcome':'duplicate_ignored','contact_id':old['contact_id'],
                    'appointment_id':old['appointment_id'],'writes_skipped':True}
        attempts=0
        try:
            # Simulated clock: record attempts but never sleep during an offline presentation.
            contact, attempts=_bounded_contact_upsert(connector,email=email,name=name,sleep=lambda _: None)
            cid=contact['contact']['id']
            opportunity=connector.upsert_opportunity(contact_id=cid,name='Synthetic service inquiry',stage_id='stage_qualified')
            oid=opportunity['opportunity']['id']
            slots=connector.free_slots(start,end,'UTC')
            if not _is_offered(slots,start):
                result={'event':eid,'outcome':'unavailable','contact_id':cid,'opportunity_id':oid,
                        'appointment_id':None,'attempts':attempts}
            else:
                booking=connector.book_test_appointment(contact_id=cid,start=start,end=end)
                connector.upsert_opportunity(contact_id=cid,name='Synthetic service inquiry',
                                             stage_id='stage_booked',opportunity_id=oid)
                result={'event':eid,'outcome':'booked','contact_id':cid,'opportunity_id':oid,
                        'appointment_id':booking['id'],'attempts':attempts}
            ledger[eid]={**result,'identity':(email,name)}
            return result
        except httpx.TransportError:
            # A remote appointment might have committed. Never blindly create it again.
            return {'event':eid,'outcome':'ambiguous_booking','reconciliation_required':True,
                    'manual_review_required':True, 'retry_appointment_automatically':False}
        except GHLAPIError as exc:
            return {'event':eid,'outcome':'connector_blocked','http_status':exc.status_code,
                    'retryable':exc.status_code in (429,500,502,503,504), 'attempts':attempts,
                    'manual_review_required':True}
    try:
        first=execute('external-1001','taylor@example.com')
        events.append(first)
        if scenario=='replay': events.append(execute('external-1001','taylor@example.com'))
        if scenario=='replay_mutation': events.append(execute('external-1001','changed@example.com'))
        if scenario=='update': events.append(execute('external-1002','taylor@example.com','Taylor Updated'))
        expected={'booking':['booked'], 'replay':['booked','duplicate_ignored'],
                  'replay_mutation':['booked','replay_conflict'],
                  'timeout_after_write':['ambiguous_booking'],
                  'update':['booked','unavailable'], 'rate_limit':['booked'],
                  'unavailable':['unavailable'], 'unauthorized':['connector_blocked']}
        passed=[x['outcome'] for x in events]==expected[scenario]
        if scenario=='update': passed=passed and len(provider.contacts)==1 and len(provider.opportunities)==1
        if scenario in ('replay','replay_mutation'): passed=passed and len(provider.bookings)==1 and len(provider.contacts)==1
        if scenario=='timeout_after_write': passed=passed and len(provider.bookings)==1 and sum(x['path']=='/calendars/events/appointments' for x in provider.traces)==1
        if scenario=='rate_limit': passed=passed and provider.crm_requests==2
        summary={'contacts':len(provider.contacts),'opportunities':len(provider.opportunities),
                 'appointments':len(provider.bookings),'provider_requests':len(provider.traces),
                 'http_429':sum(x['status']==429 for x in provider.traces)}
        return {'provider':'GoHighLevel','scenario':scenario, 'mode':'OFFLINE CONTRACT EMULATION',
                'live_connected':False,'passed':passed,'summary':summary,'event_results':events,
                'request_trace':provider.traces,
                'scope':'Real connector methods run against controlled httpx.MockTransport; no GHL account or external network request.',
                'live_validation_required':['Account/permissions','Actual contact duplicate settings','Pipeline-stage IDs',
                     'Calendar availability and notification behavior','Remote reconciliation on ambiguous timeouts']}
    finally:
        connector.close()
