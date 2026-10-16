from __future__ import annotations
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from . import db as store
from .config import ROOT, profiles, profile_for, demo_mode
from .schemas import LeadEvent
from .service import process, list_state, event_trace, ReplayConflict
from .connector_lab import run_ghl_scenario
from .proof_verify import verify_persisted_event
from .workbench import WorkbenchInput, run_workbench
from .twilio_gateway import apply_status_callback
from .channel_adapters import (
    channel_contract_scenario, normalize_vapi_report, normalize_twilio_sms,
    validate_twilio_signature, ChannelPayloadError
)
from secrets import compare_digest


def guard(key: str | None, expected: str, context: str):
    from secrets import compare_digest
    if expected and (not key or not compare_digest(key, expected)):
        raise HTTPException(status_code=401, detail=f'{context} API key required')

@asynccontextmanager
async def lifespan(app: FastAPI):
    if demo_mode() != 'mock':
        raise RuntimeError('Safety gate: only DEMO_MODE=mock supported by this verified release')
    store.connect_db()
    yield

app = FastAPI(title='NECTELIS / ClientFlow AI', version='1.0.0',
              description='Reproducible mock-only proof of lead-to-booking automation', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=str(ROOT / 'frontend')), name='static')

@app.exception_handler(RequestValidationError)
async def validation_rejection(request: Request, exc: RequestValidationError):
    # Persist only field paths and error categories, never user-supplied values.
    paths = [".".join(str(s) for s in error['loc']) + ':' + error['type'] for error in exc.errors()]
    event_id = 'unknown'
    try:
        body = await request.json()
        raw = body.get('event_id', '') if isinstance(body, dict) else ''
        if isinstance(raw, str) and raw.isascii() and len(raw) <= 120:
            event_id = raw or 'unknown'
    except Exception:
        pass
    if request.url.path == '/api/v1/leads':
        # Invalid unauthenticated requests must not write rejection records.
        try:
            guard(request.headers.get('x-clientflow-key'), os.getenv('WEBHOOK_API_KEY', ''), 'Webhook')
        except HTTPException:
            return JSONResponse(status_code=401, content={'detail':'Webhook API key required'})
        with store.session() as s:
            s.add(store.Rejection(id=store.uid('rej'), event_id=event_id,
                                  reason='; '.join(paths)[:240]))
            s.commit()
    return JSONResponse(status_code=422, content={'detail':'Lead payload failed validation',
                                                  'validation_errors': paths})

@app.get('/', include_in_schema=False)
def home():
    return FileResponse(ROOT / 'frontend' / 'index.html')

@app.get('/api/v1/health')
def health():
    return {'ok': True, 'connector_mode': 'MOCK / SYNTHETIC',
            'outbound_enabled': False, 'production_ready': False,
            'ai_mode': 'local_ollama_advisory' if os.getenv('OLLAMA_MODEL') else 'deterministic_rules_only'}

@app.get('/api/v1/profiles')
def profile_list():
    return [{'client_key':p.client_key,'company_name':p.company_name,'industry':p.industry,
             'timezone':p.timezone,'services':p.qualification.supported_services,
             'calendar':p.calendar.model_dump(), 'stages':p.pipeline.model_dump()} for p in profiles().values()]

@app.post('/api/v1/leads')
def lead_endpoint(event: LeadEvent, x_clientflow_key: str | None = Header(default=None)):
    guard(x_clientflow_key, os.getenv('WEBHOOK_API_KEY', ''), 'Webhook')
    try:
        profile_for(event.client_key)
    except KeyError:
        raise HTTPException(status_code=422, detail='Unknown client profile')
    if len(event.simulate) > 3 or any(k not in ('crm','calendar','notification') or len(v) > 35 for k,v in event.simulate.items()):
        raise HTTPException(status_code=422, detail='Invalid synthetic failure scenario')
    try:
        return process(event)
    except ReplayConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        if isinstance(exc, HTTPException): raise
        # Do not return stack traces or provider error messages to external callers.
        raise HTTPException(status_code=500, detail='Unexpected engine failure; inspect local operator logs') from exc

@app.get('/api/v1/state')
def state(x_clientflow_admin: str | None = Header(default=None)):
    guard(x_clientflow_admin, os.getenv('ADMIN_API_KEY', ''), 'Admin')
    return list_state()

@app.get('/api/v1/audit/{client_key}/{source}/{event_id}')
def fully_scoped_audit(client_key: str, source: str, event_id: str, x_clientflow_admin: str | None = Header(default=None)):
    guard(x_clientflow_admin, os.getenv('ADMIN_API_KEY', ''), 'Admin')
    result = event_trace(event_id, client_key=client_key, source=source)
    if not result: raise HTTPException(status_code=404, detail='Event not found for this profile/source')
    return result

@app.get('/api/v1/audit/{client_key}/{event_id}')
def scoped_audit(client_key: str, event_id: str, x_clientflow_admin: str | None = Header(default=None)):
    guard(x_clientflow_admin, os.getenv('ADMIN_API_KEY', ''), 'Admin')
    try:
        result = event_trace(event_id, client_key=client_key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result: raise HTTPException(status_code=404, detail='Event not found in this profile')
    return result

@app.get('/api/v1/audit/{event_id}')
def audit(event_id: str, x_clientflow_admin: str | None = Header(default=None)):
    guard(x_clientflow_admin, os.getenv('ADMIN_API_KEY', ''), 'Admin')
    try:
        result = event_trace(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result: raise HTTPException(status_code=404, detail='Event not found')
    return result

@app.get('/api/v1/proof/verify/{client_key}/{source}/{event_id}')
def proof_verify(client_key: str, source: str, event_id: str,
                 x_clientflow_admin: str | None = Header(default=None)):
    # Same access boundary as the state/audit endpoints; read-only SQL evidence.
    guard(x_clientflow_admin, os.getenv('ADMIN_API_KEY', ''), 'Admin')
    result = verify_persisted_event(client_key, source, event_id)
    if result is None:
        raise HTTPException(status_code=404, detail='No such persisted event')
    return result

@app.get('/api/v1/integrations')
def integration_inventory():
    # Inventory is a public, non-secret status display. Credentials are never returned.
    return {
        'environment':'LOCAL / SYNTHETIC', 'live_provider_connected':False,
        'providers':[
          {'id':'ghl','name':'GoHighLevel','level':'OFFLINE CONTRACT EXECUTED',
           'capabilities':['Contact upsert','Opportunity upsert','Free-slot check','Appointment create'],
           'live_status':'REQUIRES AUTHORIZED GHL TEST'},
          {'id':'vapi','name':'Vapi','level':'PAYLOAD ADAPTER VALIDATED',
           'capabilities':['End-of-call structuredData normalization','Replay-safe call ID'],
           'live_status':'NO ACTUAL VOICE CALL TESTED'},
          {'id':'twilio','name':'Twilio','level':'SIGNATURE + INBOUND ADAPTER TESTED',
           'capabilities':['Classic form webhook verification','SMS-to-review intake'],
           'live_status':'NO REAL SMS OR PHONE NUMBER TESTED'},
          {'id':'n8n','name':'n8n','level':'EXPORT CREATED',
           'capabilities':['Lead orchestration workflow export'],
           'live_status':'WORKSPACE IMPORT NOT VERIFIED'}]}

@app.post('/api/v1/integration-lab/{provider}/{scenario}')
def integration_lab(provider: str, scenario: str):
    # A deliberate localhost-only lab; no supplied URLs, tokens or third-party network requests.
    if provider=='ghl':
        try: return run_ghl_scenario(scenario)
        except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc
    if provider in ('vapi','twilio') and scenario=='inbound':
        return channel_contract_scenario(provider)
    raise HTTPException(status_code=404,detail='No such offline contract test')

@app.post('/api/v1/workbench/run')
def workbench_run(body: WorkbenchInput):
    # Inputs select scenarios only, never remote domains, secrets, or destinations.
    try: return run_workbench(body)
    except (ValueError, KeyError, ChannelPayloadError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

def _provider_webhook_enabled() -> bool:
    return os.getenv('ENABLE_PROVIDER_WEBHOOKS','false').lower()=='true'

@app.post('/api/v1/channels/vapi/{client_key}')
async def vapi_inbound(client_key: str, request: Request, x_clientflow_provider_secret: str | None = Header(None), x_vapi_secret: str | None = Header(None)):
    if not _provider_webhook_enabled():
        raise HTTPException(status_code=503,detail='Provider ingestion disabled by default')
    secret=os.getenv('VAPI_WEBHOOK_SECRET','')
    if not secret or not (x_vapi_secret or x_clientflow_provider_secret) or not compare_digest(x_vapi_secret or x_clientflow_provider_secret,secret):
        raise HTTPException(status_code=401,detail='Invalid provider authentication')
    if int(request.headers.get('content-length','0') or '0')>32_768:
        raise HTTPException(status_code=413,detail='Webhook payload too large')
    try:
        profile_for(client_key)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail='Unknown profile') from exc
    try:
        event=normalize_vapi_report(await request.json(),client_key)
        if event.lead.email and not event.lead.email.endswith('@example.com') and os.getenv('ALLOW_REAL_WEBHOOK_CONTACTS')!='YES':
            raise ChannelPayloadError('Real contact ingestion needs explicit approval')
        # Validate integration authorization before modifying local state.
        if (os.getenv('ENABLE_GHL_WEBHOOK_BRIDGE','false').lower()=='true'
                and os.getenv('GHL_LIVE_TEST_WRITE_ENABLED')!='YES'):
            raise HTTPException(status_code=503,detail='GHL bridge requires explicitly approved write mode')
        local_result=process(event)
        # Explicit provider-side test bridge; never activated in the default UI.
        if os.getenv('ENABLE_GHL_WEBHOOK_BRIDGE','false').lower()=='true':
            if not event.lead.email or not event.requested_slot or not event.lead.consent_to_contact:
                return {**local_result,'ghl_bridge':{'outcome':'review','reason':'Confirmed identity, consent and slot required'}}
            from .ghl_connector import GHLSettings
            from .live_bridge import authorized_ghl_test
            cfg=GHLSettings(os.getenv('GHL_PRIVATE_INTEGRATION_TOKEN',''),
                os.getenv('GHL_LOCATION_ID',''),os.getenv('GHL_CALENDAR_ID'),
                os.getenv('GHL_PIPELINE_ID'),os.getenv('GHL_STAGE_QUALIFIED_ID'),
                os.getenv('GHL_STAGE_BOOKED_ID'))
            allow={x.strip().lower() for x in os.getenv('GHL_TEST_EMAIL_ALLOWLIST','').split(',') if x.strip()}
            try:
                bridge=authorized_ghl_test(event_id=event.event_id,name=event.lead.first_name,
                  email=event.lead.email,start=event.requested_slot,config=cfg,
                  approved_emails=allow,write_enabled=True)
            except (ValueError,PermissionError) as exc:
                return {**local_result,'ghl_bridge':{'outcome':'configuration_review','reason':str(exc)}}
            return {**local_result,'ghl_bridge':bridge}
        return local_result
    except ChannelPayloadError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    except ReplayConflict as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc

@app.post('/api/v1/channels/twilio/status')
async def twilio_delivery_status(request: Request, x_twilio_signature: str | None = Header(None)):
    if not _provider_webhook_enabled():
        raise HTTPException(status_code=503, detail='Provider ingestion disabled')
    token=os.getenv('TWILIO_AUTH_TOKEN','')
    canonical=os.getenv('TWILIO_STATUS_CALLBACK_URL','')
    if not token or not canonical:raise HTTPException(status_code=503,detail='Callback authentication not configured')
    if int(request.headers.get('content-length','0') or '0')>8192:
        raise HTTPException(status_code=413,detail='Oversized request')
    from urllib.parse import parse_qs,urlsplit
    if urlsplit(canonical).path!=request.url.path:
        raise HTTPException(status_code=403,detail='Unexpected callback URL')
    try:
        raw=(await request.body()).decode('utf-8')
        params={k:v[0] for k,v in parse_qs(raw,keep_blank_values=True).items()}
        return apply_status_callback(url=canonical,data=params,signature=x_twilio_signature or '',token=token)
    except PermissionError as exc: raise HTTPException(status_code=401,detail=str(exc)) from exc
    except LookupError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
    except ValueError as exc: raise HTTPException(status_code=422,detail=str(exc)) from exc

@app.post('/api/v1/channels/twilio/{client_key}')
async def twilio_inbound(client_key: str, request: Request, x_twilio_signature: str | None = Header(None)):
    if not _provider_webhook_enabled():
        raise HTTPException(status_code=503,detail='Provider ingestion disabled by default')
    token=os.getenv('TWILIO_AUTH_TOKEN','')
    canonical=os.getenv('TWILIO_PUBLIC_WEBHOOK_URL','')
    if not token or not canonical:
        raise HTTPException(status_code=503,detail='Twilio signing configuration incomplete')
    if int(request.headers.get('content-length','0') or '0')>8_192:
        raise HTTPException(status_code=413,detail='Webhook payload too large')
    from urllib.parse import parse_qs
    raw=(await request.body()).decode('utf-8')
    params={k:v[0] for k,v in parse_qs(raw,keep_blank_values=True).items()}
    from urllib.parse import urlsplit
    if urlsplit(canonical).path != request.url.path:
        raise HTTPException(status_code=403,detail='Configured Twilio webhook URL does not match this endpoint')
    if not validate_twilio_signature(canonical,params,x_twilio_signature or '',token):
        raise HTTPException(status_code=401,detail='Twilio signature invalid')
    try:
        profile_for(client_key)
    except KeyError as exc:
        raise HTTPException(status_code=404,detail='Unknown profile') from exc
    try:
        event=normalize_twilio_sms(params,client_key)
        process(event)  # No response body exposing lead information to telephony caller
    except ChannelPayloadError as exc:
        raise HTTPException(status_code=422,detail=str(exc)) from exc
    except ReplayConflict as exc:
        raise HTTPException(status_code=409,detail=str(exc)) from exc
    return Response(content='<Response></Response>',media_type='application/xml')

@app.post('/api/v1/admin/reset')
def reset(request: Request, x_clientflow_admin: str | None = Header(default=None)):
    guard(x_clientflow_admin, os.getenv('ADMIN_API_KEY', ''), 'Admin')
    # A hostile webpage must not reset an unauthenticated localhost demonstration.
    # CLI requests without Origin remain supported; browsers must be same-origin.
    from urllib.parse import urlsplit
    origin = request.headers.get('origin')
    if origin:
        parsed = urlsplit(origin)
        if not (parsed.scheme == request.url.scheme and parsed.netloc == request.headers.get('host')):
            raise HTTPException(status_code=403, detail='Cross-origin reset refused')
    with store.engine.begin() as conn:
        # Delete dependent records first; resets *only* the local synthetic database.
        for table in (store.Notification.__table__, store.FollowUp.__table__,
                      store.Audit.__table__, store.Rejection.__table__, store.Delivery.__table__, store.Booking.__table__,
                      store.Event.__table__, store.Contact.__table__):
            conn.execute(table.delete())
    return {'status':'synthetic_demo_reset','contacts':0,'events':0,'bookings':0}
