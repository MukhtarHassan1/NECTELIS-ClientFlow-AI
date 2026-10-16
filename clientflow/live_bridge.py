"""Explicitly opted-in GHL test orchestration with durable replay control.

No live calls can happen without real credentials, a per-address allowlist,
and an explicit write switch. Interrupted remote work remains blocked until an
operator reconciles source of truth. Not a zero-configuration production flow.
"""
from __future__ import annotations
import json,hashlib
from datetime import datetime
from sqlalchemy import select
from . import db as store
from .ghl_connector import GHLSettings
from .provider_orchestrator import run_ghl_job


def authorized_ghl_test(*,event_id:str,name:str,email:str,start:datetime,config:GHLSettings,
                        approved_emails:set[str],write_enabled:bool=False):
    if not write_enabled or not email.endswith('@example.com') or email not in approved_emails:
        raise PermissionError('GHL live test requires explicit write approval and allowlisted synthetic email')
    if not all([config.token,config.location_id,config.calendar_id,config.pipeline_id,
                config.stage_id,config.booked_stage_id]):
        raise ValueError('Token, location, calendar, pipeline, qualified and booked stage IDs required')
    fingerprint=hashlib.sha256(json.dumps({'name':name,'email':email,'slot':start.isoformat()},sort_keys=True).encode()).hexdigest()
    with store.session() as session:
        old=session.scalar(select(store.ProviderJob).where(store.ProviderJob.provider=='ghl',
                                                              store.ProviderJob.external_event_key==event_id))
        if old:
            if old.fingerprint!=fingerprint:raise ValueError('Event identity reused with different input')
            if old.state=='completed':return {'duplicate':True,**json.loads(old.result_json)}
            return {'duplicate':True,'outcome':'requires_remote_reconciliation','state':old.state}
        job=store.ProviderJob(id=store.uid('pjob'),provider='ghl',external_event_key=event_id,
                                fingerprint=fingerprint,state='started')
        session.add(job);session.commit()
    # Pessimistic: started is committed before the first remote write. An interrupted
    # process cannot silently replay a possibly committed appointment.
    try:
        result=run_ghl_job(name=name,email=email,start=start,settings=config)
    except Exception:
        result={'outcome':'requires_remote_reconciliation','error':'Connector interrupted; inspect provider state'}
    with store.session() as session:
        job=session.scalar(select(store.ProviderJob).where(store.ProviderJob.provider=='ghl',
                                                           store.ProviderJob.external_event_key==event_id))
        job.state='completed' if result['outcome'] in ('booked','slot_unavailable') else 'needs_reconciliation'
        job.result_json=json.dumps(result)
        session.commit()
    return {'duplicate':False,**result}
