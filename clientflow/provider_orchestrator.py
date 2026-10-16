"""One job, same GHL connector against emulator or authorized test account.

This is an isolated provider orchestration path, not a replacement for the
synthetic lead engine. An uncertain remote booking is NEVER retried blindly.
"""
from __future__ import annotations
from datetime import datetime,timedelta,timezone
from uuid import uuid4
import httpx
from .ghl_connector import GHLTestConnector,GHLSettings,GHLAPIError
from .connector_lab import DemoProvider,_is_offered,_bounded_contact_upsert


def run_ghl_job(*, name:str,email:str,start:datetime, settings:GHLSettings|None=None,
                transport:httpx.BaseTransport|None=None, scenario='booking') -> dict:
    """Exercise actual GHL HTTP methods with dynamic input and safe checks.
    In live mode caller must provide an authorized settings object AND explicitly
    handle consent and allowlisting; no automated live retry of uncertain writes.
    """
    if start.tzinfo is None or start<=datetime.now(timezone.utc):
        raise ValueError('Booking slot must be a future timezone-aware datetime')
    if not email or not name:raise ValueError('Name/email required')
    offline=settings is None
    if offline:
        if not email.endswith('@example.com'):
            raise ValueError('Offline demonstration only accepts example.com addresses')
        provider=DemoProvider(scenario=scenario)
        settings=GHLSettings('offline-fake-token','location_mock','calendar_mock','pipeline_mock','stage_qualified')
        transport=httpx.MockTransport(provider.reply)
    else:
        provider=None
    connector=GHLTestConnector(settings,transport=transport)
    trace=[]
    outcome='needs_review';contact_id=None;opportunity_id=None;appointment_id=None
    def _output():
        return {'provider':'GoHighLevel','mode':'OFFLINE_EMULATOR' if offline else 'AUTHORIZED_LIVE_TEST',
                'outcome':outcome,'contact_id':contact_id,'opportunity_id':opportunity_id,
                'appointment_id':appointment_id,'steps':trace,
                'http_trace':provider.traces if offline else [],'live_connected':not offline}

    try:
        contact,attempts=_bounded_contact_upsert(connector,email=email,name=name,sleep=lambda _:None if offline else __import__('time').sleep(_))
        contact_id=(contact.get('contact') or {}).get('id')
        if not contact_id: raise ValueError('GHL response missing contact.id')
        trace.append({'step':'contact_upsert','status':'ok','contact_id':contact_id,'attempts':attempts})
        opp=connector.upsert_opportunity(contact_id=contact_id,name='ClientFlow inquiry',stage_id=settings.stage_id)
        opportunity_id=(opp.get('opportunity') or {}).get('id')
        if not opportunity_id:raise ValueError('GHL response missing opportunity.id')
        trace.append({'step':'pipeline_qualified','status':'ok','opportunity_id':opportunity_id})
        if not offline and not settings.booked_stage_id:
            raise ValueError('GHL booked stage ID required for live test')
        finish=start+timedelta(minutes=30)
        free=connector.free_slots(start,finish,'UTC')
        allowed=_is_offered(free,start)
        trace.append({'step':'availability','status':'offered' if allowed else 'unavailable'})
        if allowed:
            try:
                booked=connector.book_test_appointment(contact_id=contact_id,start=start,end=finish)
                appointment_id=booked.get('id') or (booked.get('appointment') or {}).get('id')
                if not appointment_id:raise ValueError('Booking response missing appointment ID; reconcile remotely')
            except (httpx.TimeoutException,httpx.TransportError):
                trace.append({'step':'booking','status':'unknown_remote_outcome','reconciliation_required':True})
                outcome='reconcile_booking';return _output()
            trace.append({'step':'booking','status':'created','appointment_id':appointment_id})
            connector.upsert_opportunity(contact_id=contact_id,name='ClientFlow inquiry',
                                         stage_id='stage_booked' if offline else settings.booked_stage_id,
                                         opportunity_id=opportunity_id)
            trace.append({'step':'pipeline_booked','status':'updated'})
            outcome='booked'
        else:
            outcome='slot_unavailable'
        return _output()
    except GHLAPIError as error:
        outcome='provider_error';trace.append({'step':'provider','status':error.status_code,'manual_review':True})
        return _output()
    except (ValueError,httpx.TransportError) as error:
        outcome='needs_review';trace.append({'step':'provider','status':type(error).__name__,'manual_review':True})
        return _output()
    finally:connector.close()

