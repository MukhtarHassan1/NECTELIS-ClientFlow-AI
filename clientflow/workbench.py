"""Operator-driven integration exercises. These execute adapters, HTTP emulators and SQL.
All exercises accept fresh synthetic reviewer input. Live provider calls are impossible
from this module; credentials are not accepted from the browser.
"""
from __future__ import annotations
import base64, hashlib,hmac,re
from datetime import datetime,timezone,timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
import httpx
from pydantic import BaseModel,Field,field_validator
from . import db as store
from .channel_adapters import normalize_vapi_report,normalize_twilio_sms,validate_twilio_signature,ChannelPayloadError
from .service import process
from .provider_orchestrator import run_ghl_job
from .twilio_gateway import TwilioSettings,TwilioGateway,TwilioGatewayError,save_dispatch,apply_status_callback

class WorkbenchInput(BaseModel):
    provider:str
    scenario:str='success'
    client_key:str='home-services-demo'
    name:str=Field(min_length=2,max_length=60)
    phrase:str=Field(min_length=3,max_length=50)
    @field_validator('name','phrase')
    @classmethod
    def safe(cls,v):
        if not re.fullmatch(r'[a-zA-Z0-9 ._-]+',v):raise ValueError('Synthetic name and reference must contain basic printable characters')
        return v.strip()


def _slot(extra_days:int=0, slot_index:int=10):
    local=datetime.now(ZoneInfo('America/New_York'))+timedelta(days=12+extra_days)
    while local.weekday()>=5:local+=timedelta(days=1)
    return local.replace(hour=9+slot_index,minute=0,second=0,microsecond=0)

def _available_slot(reference:str):
    # A fresh local booking slot for the synthetic Vapi walkthrough; the engine
    # still performs its own conflict checks on write.
    from sqlalchemy import select
    base=int(reference[:5],16)%180
    lane=int(reference[5:10],16)%8
    with store.session() as session:
        occupied=set(session.scalars(select(store.Booking.start_at).where(
            store.Booking.client_key=='home-services-demo')).all())
    for offset in range(250):
        slot=_slot(base+offset,(lane+offset)%8)
        key=slot.astimezone(timezone.utc).isoformat(timespec='seconds')
        if key not in occupied:
            return slot
    raise ValueError('No available synthetic slot for the integration exercise')

def _signed(url,params,token):
    raw=url+''.join(k+params[k] for k in sorted(params))
    return base64.b64encode(hmac.new(token.encode(),raw.encode(),hashlib.sha1).digest()).decode()

def _public_result(provider,case,trace,checks, **details):
    return {'provider':provider,'scenario':case,'mode':'LOCAL / PROVIDER EMULATOR',
            'passed':all(checks.values()),'checks':checks,'trace':trace,
            'actual_provider_calls':0,'details':details}


def run_workbench(payload:WorkbenchInput)->dict:
    from .config import profile_for
    profile=profile_for(payload.client_key)
    if profile.industry!='home_services':
        # This exercise uses home-services booking slots and services; use ordinary Test studio for other profiles.
        raise ValueError('Integration workbench currently uses the home-services demonstration profile')
    ref=uuid4().hex[:12]
    email=f'engineering.{ref}@example.com'
    if payload.provider=='ghl':
        cases={'success':'booking','rate_limit':'rate_limit','unavailable':'unavailable','unauthorized':'unauthorized',
               'timeout':'timeout_after_write'}
        if payload.scenario not in cases:raise ValueError('Unknown GHL scenario')
        result=run_ghl_job(name=payload.name,email=email,start=_slot(),scenario=cases[payload.scenario])
        expects={'success':'booked','rate_limit':'booked','unavailable':'slot_unavailable',
                 'unauthorized':'provider_error','timeout':'reconcile_booking'}
        trace=result['http_trace']
        checks={'Real Python connector methods executed':len(trace)>0,
                'Provider response matches expected safe outcome':result['outcome']==expects[payload.scenario],
                'Authorization never exposed':not any('Authorization' in str(t) for t in trace),
                'No external network requests':result['live_connected'] is False}
        return _public_result('GoHighLevel',payload.scenario,trace,checks,
            processing=result['steps'],outcome=result['outcome'],contact_id=result['contact_id'],
            opportunity_id=result['opportunity_id'],appointment_id=result['appointment_id'],
            reference=payload.phrase)
    if payload.provider=='vapi':
        if payload.scenario not in ('success','duplicate','malformed'):raise ValueError('Unknown Vapi scenario')
        call='vapi-'+ref
        structured={'first_name':payload.name,'email':email,'service':'plumbing',
                    'consent_to_contact':True,'requested_slot':_available_slot(ref).isoformat()}
        message={'message':{'type':'end-of-call-report','call':{'id':call},
                            'analysis':{'structuredData':structured}}}
        if payload.scenario=='malformed':
            message['message']['call'].pop('id')
            try:normalize_vapi_report(message,payload.client_key)
            except ChannelPayloadError:
                return _public_result('Vapi','malformed',[{'operation':'validate incoming Vapi report','http_status':422}],
                    {'Malformed call identity is rejected':True,'No CRM write attempted':True},reference=payload.phrase)
            return _public_result('Vapi','malformed',[],{'Malformed event is rejected':False})
        event=normalize_vapi_report(message,payload.client_key)
        first=process(event)
        replay=process(event) if payload.scenario=='duplicate' else None
        trace=[{'operation':'Vapi end-of-call-report','status':'accepted','call_id':call},
               {'operation':'Structured extraction','status':'validated','service':event.lead.service},
               {'operation':'FastAPI lead engine → SQLite CRM','status':first['status'],'contact_id':first.get('contact_id')},
               {'operation':'Calendar availability → appointment','status':first['status'],'appointment_id':first.get('appointment_id')}]
        if replay is not None:trace.append({'operation':'repeat call.id','status':'ignored','duplicate':replay.get('duplicate_event')})
        checks={'Provider report mapped into typed lead contract':event.source=='vapi',
                'Real local contact and appointment created':first.get('status')=='booked' and bool(first.get('appointment_id')),
                'Duplicate call id does not create new appointment':replay is None or (replay.get('duplicate_event')==True and replay.get('appointment_id')==first.get('appointment_id'))}
        return _public_result('Vapi',payload.scenario,trace,checks,event_id=event.event_id,
                              outcome=first['status'],contact_id=first.get('contact_id'),
                              appointment_id=first.get('appointment_id'),reference=payload.phrase)
    if payload.provider=='twilio':
        if payload.scenario not in ('success','tamper','rate_limit','delivery_failed'):
            raise ValueError('Unknown Twilio scenario')
        token='demo-only-twilio-auth'
        inbound_url='https://webhooks.example.com/api/v1/channels/twilio/home-services-demo'
        callback_url='https://webhooks.example.com/api/v1/channels/twilio/status'
        params={'MessageSid':'SM'+ref.ljust(32,'0'), 'From':'+15550102020',
                'To':'+15550102021','Body':'Synthetic inquiry '+payload.phrase}
        sig=_signed(inbound_url,params,token)
        verified=validate_twilio_signature(inbound_url,params,sig,token)
        altered={**params,'Body':params['Body']+' altered'}
        tamper_blocked=not validate_twilio_signature(inbound_url,altered,sig,token)
        if payload.scenario=='tamper':
            return _public_result('Twilio','tamper',[{'operation':'X-Twilio-Signature check','status':'401 invalid signature'}],
                     {'Original signature valid':verified,'Changed body rejected':tamper_blocked},reference=payload.phrase)
        event=normalize_twilio_sms(params,payload.client_key)
        intake=process(event)
        replay=process(event)
        requests=[]
        def emulator(req:httpx.Request)->httpx.Response:
            requests.append({'method':req.method,'path':req.url.path,'content_type':req.headers.get('content-type'),
                             'basic_auth_present':req.headers.get('Authorization','').startswith('Basic ')})
            if payload.scenario=='rate_limit':return httpx.Response(429,json={'code':20429,'message':'Rate limit'})
            return httpx.Response(201,json={'sid':'SM'+ref.ljust(32,'1'),'status':'queued'})
        settings=TwilioSettings('AC'+'1'*32,token,'+15550102021',callback_url)
        gateway=TwilioGateway(settings,httpx.MockTransport(emulator))
        trace=[{'operation':'Twilio inbound signature validated','status':'accepted'},
               {'operation':'Twilio SMS → CRM lead','status':intake['status'],'contact_id':intake.get('contact_id')},
               {'operation':'Replay MessageSid','status':'ignored' if replay.get('duplicate_event') else 'unexpected'}]
        dispatched=None;callback=None;rejected_error=None
        try:
            dispatched=gateway.send_sms(to='+15550102020',body='Your synthetic inquiry is queued',
              consent=True,approved_recipients={'+15550102020'},allow_outbound=True)
            save_dispatch(job_id='test-'+ref,message_sid=dispatched['message_sid'],initial_status=dispatched['status'])
            form={'MessageSid':dispatched['message_sid'],
                  'MessageStatus':'undelivered' if payload.scenario=='delivery_failed' else 'delivered',
                  'ErrorCode':'30007' if payload.scenario=='delivery_failed' else ''}
            callback=apply_status_callback(url=callback_url,data=form,
                signature=_signed(callback_url,form,token),token=token)
            trace.append({'operation':'Signed Twilio delivery callback','status':callback['status'],
                          'message_sid':callback['message_sid']})
        except TwilioGatewayError as err:
            rejected_error=err.status
            trace.append({'operation':'Outbound REST POST','status':err.status,'action':'stopped_no_blind_retry'})
        finally:gateway.close()
        trace.extend(requests)
        checks={'Original inbound signature valid; tamper blocked':verified and tamper_blocked,
                'Inbound SMS processed and replay deduplicated':intake.get('status')=='needs_review' and replay.get('duplicate_event')==True,
                'Actual Twilio REST client exercised':len(requests)==1 and requests[0]['basic_auth_present'],
                'Provider outcome safely handled': (rejected_error==429 and dispatched is None) if payload.scenario=='rate_limit' else (
                    dispatched is not None and callback is not None and callback['status']==('undelivered' if payload.scenario=='delivery_failed' else 'delivered'))}
        return _public_result('Twilio',payload.scenario,trace,checks,
            inbound_event_id=event.event_id,contact_id=intake.get('contact_id'),
            outbound=dispatched,status_callback=callback,reference=payload.phrase)
    raise ValueError('Unknown provider')
