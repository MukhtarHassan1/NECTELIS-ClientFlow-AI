"""Provider-specific inbound normalization and signature checks.

This release never initiates a Vapi phone call or sends Twilio SMS. An inbound
webhook can be processed only with explicit operator configuration; the default
server denies all such requests. Use synthetic, permitted fixtures in demos.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
from datetime import datetime
from typing import Mapping
from .schemas import LeadEvent

class ChannelPayloadError(ValueError):
    pass


def normalize_vapi_report(payload: dict, client_key: str) -> LeadEvent:
    """Normalize an end-of-call-report with explicitly configured structuredData.

    Not a voice simulation: Vapi itself is external. This only maps the event it
    would send into ClientFlow's lead contract; no transcript inference is used.
    """
    msg = payload.get('message', {})
    if not isinstance(msg, dict) or msg.get('type') != 'end-of-call-report':
        raise ChannelPayloadError('Only end-of-call-report is supported; tool-calls need a separate response protocol')
    call=msg.get('call') or {}
    cid=call.get('id')
    if not isinstance(cid,str) or not cid or len(cid)>100:
        raise ChannelPayloadError('Vapi call.id required for replay-safe identity')
    analysis=msg.get('analysis') or call.get('analysis') or {}
    data=analysis.get('structuredData') or {}
    if not isinstance(data,dict):
        raise ChannelPayloadError('structuredData must be an object')
    phone=(call.get('customer') or {}).get('number') or None
    try:
        return LeadEvent.model_validate({
            'source':'vapi','event_id':'vapi:'+cid,'client_key':client_key,
            'lead':{
                'first_name':data.get('first_name') or data.get('firstName') or 'Voice inquiry',
                'email':data.get('email'), 'phone':data.get('phone') or phone,
                'service':data.get('service') or 'unclassified_voice_inquiry',
                'message':'Structured voice intake; no transcript stored',
                'consent_to_contact':data.get('consent_to_contact') is True
            },'requested_slot':data.get('requested_slot')
        })
    except Exception as exc:
        raise ChannelPayloadError('Vapi intake missing required structured fields or valid contact identity') from exc


def normalize_twilio_sms(form: Mapping[str,str], client_key: str) -> LeadEvent:
    """Ingest inbound SMS as a human-review inquiry; no consent inferred from receipt."""
    message_sid=form.get('MessageSid')
    phone=form.get('From')
    if not message_sid or not phone or len(message_sid)>100:
        raise ChannelPayloadError('Twilio MessageSid and From are required')
    try:
        return LeadEvent.model_validate({
            'event_id':'sms:'+message_sid,'source':'twilio', 'client_key':client_key,
            'lead':{'first_name':'SMS inquiry','phone':phone,
                    'service':'unclassified_sms_inquiry','message':'Inbound SMS received; content withheld from logs',
                    'consent_to_contact':False}, 'requested_slot':None
        })
    except Exception as exc:
        raise ChannelPayloadError('Invalid Twilio sender identity') from exc


def validate_twilio_signature(url: str, params: Mapping[str,str], signature: str, token: str) -> bool:
    """Twilio classic form POST HMAC-SHA1 validator.

    Twilio recommends its official RequestValidator SDK in production, notably
    for all parameters, proxy URL canonicalization, JSON, and edge cases.
    This function intentionally accepts the classic form request only.
    """
    if not token or not signature or not url.startswith('https://'):
        return False
    signed=url+''.join(key+params[key] for key in sorted(params))
    expected=base64.b64encode(hmac.new(token.encode(),signed.encode(),hashlib.sha1).digest()).decode()
    return hmac.compare_digest(expected,signature)


def channel_contract_scenario(channel: str) -> dict:
    if channel=='vapi':
        event=normalize_vapi_report({
            'message':{'type':'end-of-call-report','call':{'id':'demo-voice-001'},
                'analysis':{'structuredData':{'first_name':'Taylor','email':'taylor@example.com',
                      'service':'air_conditioner_repair','consent_to_contact':True}}}},'home-services-demo')
        return {'provider':'Vapi','mode':'OFFLINE PAYLOAD VALIDATION','live_connected':False,
          'passed':event.source=='vapi' and event.lead.service=='air_conditioner_repair',
          'steps':[{'operation':'end-of-call-report','status':'accepted'},
                   {'operation':'structuredData → LeadEvent','status':'validated'},
                   {'operation':'Replay key from call.id','status':'derived'},
                   {'operation':'Missing transcript inference','status':'deliberately avoided'}],
          'normalized':{'source':event.source,'event_id':event.event_id,'service':event.lead.service,
                        'consent_to_contact':event.lead.consent_to_contact},
          'scope':'No voice call placed. Local fixture normalized using the Vapi event contract.'}
    if channel=='twilio':
        form={'MessageSid':'SMoffline0001','From':'+15550102020','Body':'I need repair help'}
        token='offline-fake-token'; url='https://example.com/api/v1/channels/twilio'
        signed=url+''.join(k+form[k] for k in sorted(form))
        signature=base64.b64encode(hmac.new(token.encode(),signed.encode(),hashlib.sha1).digest()).decode()
        accepted=validate_twilio_signature(url,form,signature,token)
        rejected=not validate_twilio_signature(url,{**form,'Body':'tampered'},signature,token)
        event=normalize_twilio_sms(form,'home-services-demo')
        return {'provider':'Twilio','mode':'OFFLINE SIGNATURE + PAYLOAD TEST','live_connected':False,
          'passed':accepted and rejected and event.source=='twilio' and not event.lead.consent_to_contact,
          'steps':[{'operation':'Valid signed inbound SMS','status':'accepted' if accepted else 'failed'},
                   {'operation':'Tampered request signature','status':'rejected' if rejected else 'failed'},
                   {'operation':'MessageSid → idempotency key','status':'derived'},
                   {'operation':'Unknown service → manual review','status':'safe default'}],
          'normalized':{'source':event.source,'event_id':event.event_id,
                        'service':event.lead.service,'consent_to_contact':False},
          'scope':'No Twilio account, real SMS, phone number, or paid telephony involved.'}
    raise ChannelPayloadError('Unknown channel')
