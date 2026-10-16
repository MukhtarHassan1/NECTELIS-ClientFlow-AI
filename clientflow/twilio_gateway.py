"""Twilio SMS REST / status-callback boundary.

No network by default. Live dispatch must be explicitly authorized, to an
allowlisted opted-in destination, with a configured HTTPS callback URL.
HTTP timeouts after POST are ambiguous: we deliberately DO NOT auto-retry sends.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hmac
import httpx
from sqlalchemy import select
from . import db as store
from .channel_adapters import validate_twilio_signature

TWILIO_BASE='https://api.twilio.com'
TERMINAL={'delivered','undelivered','failed','canceled','read'}
KNOWN={'accepted','queued','sending','sent','delivered','undelivered','failed','canceled','read','scheduled'}

class TwilioGatewayError(RuntimeError):
    def __init__(self, status:int):
        super().__init__(f'Twilio API HTTP {status}'); self.status=status

@dataclass(frozen=True)
class TwilioSettings:
    account_sid:str
    auth_token:str
    from_number:str
    callback_url:str

class TwilioGateway:
    def __init__(self, settings:TwilioSettings, transport:httpx.BaseTransport|None=None):
        if not all([settings.account_sid,settings.auth_token,settings.from_number]):
            raise ValueError('Twilio Account SID, auth token, and sender required')
        if not (settings.account_sid.startswith('AC') and len(settings.account_sid) == 34):
            raise ValueError('Twilio Account SID must be AC followed by 32 characters')
        self.settings=settings
        self.client=httpx.Client(base_url=TWILIO_BASE,transport=transport,timeout=12)

    def send_sms(self, *, to:str, body:str, consent:bool, approved_recipients:set[str],
                 allow_outbound:bool=False) -> dict:
        if not allow_outbound or not consent or to not in approved_recipients:
            raise PermissionError('Outbound requires authorization, consent and allowlisted recipient')
        if not (body and len(body)<=320):
            raise ValueError('Message must be 1–320 characters')
        if not (self.settings.callback_url.startswith('https://') and 'localhost' not in self.settings.callback_url):
            raise ValueError('HTTPS status callback URL required')
        response=self.client.post(f'/2010-04-01/Accounts/{self.settings.account_sid}/Messages.json',
            auth=(self.settings.account_sid,self.settings.auth_token),
            data={'To':to,'From':self.settings.from_number,'Body':body,
                  'StatusCallback':self.settings.callback_url})
        if response.is_error:
            raise TwilioGatewayError(response.status_code)
        payload=response.json()
        if not payload.get('sid','').startswith('SM'):
            raise ValueError('Provider did not return valid Message SID')
        return {'message_sid':payload['sid'],'status':payload.get('status','queued')}

    def close(self): self.client.close()


def save_dispatch(*, job_id:str, message_sid:str, initial_status:str, channel='twilio') -> dict:
    """Durable message ID and state; no phone number or message body in SQL."""
    with store.session() as session:
        previous=session.scalar(select(store.Delivery).where(store.Delivery.job_id==job_id))
        if previous:
            if previous.message_sid != message_sid: raise ValueError('Conflicting job identity')
            return {'job_id':job_id,'message_sid':previous.message_sid,'status':previous.status,'duplicate':True}
        session.add(store.Delivery(id=store.uid('dlv'),job_id=job_id,message_sid=message_sid,
                                   status=initial_status,channel=channel))
        session.commit()
    return {'job_id':job_id,'message_sid':message_sid,'status':initial_status,'duplicate':False}


def apply_status_callback(*, url:str, data:dict[str,str], signature:str, token:str)->dict:
    """Verify *before* any read/write; never regress terminal statuses."""
    if not validate_twilio_signature(url,data,signature,token):
        raise PermissionError('Invalid Twilio status callback signature')
    sid=data.get('MessageSid','')
    status=(data.get('MessageStatus') or data.get('SmsStatus') or '').lower()
    if not sid.startswith('SM') or status not in KNOWN:
        raise ValueError('Unknown MessageSid or delivery state')
    with store.session() as session:
        record=session.scalar(select(store.Delivery).where(store.Delivery.message_sid==sid))
        if not record: raise LookupError('Unknown outbound message SID')
        former=record.status
        if former in TERMINAL and status!=former:
            return {'message_sid':sid,'status':former,'ignored_transition':True}
        # Do not move backwards from 'sent' to 'queued' due to out-of-order callbacks.
        ordering={'accepted':0,'scheduled':0,'queued':1,'sending':2,'sent':3}
        if status in ordering and ordering.get(former,-1)>ordering[status]:
            return {'message_sid':sid,'status':former,'ignored_transition':True}
        record.status=status
        record.error_code=(data.get('ErrorCode') or '')[:16] or None
        record.updated_at=store.now()
        session.commit()
        return {'message_sid':sid,'previous':former,'status':status,'ignored_transition':False}
