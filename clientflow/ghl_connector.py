"""GHL API adapter with an offline provider emulator and an isolated live-test CLI.

One user-controlled, explicit opt-in harness exists for authorized GHL test accounts.
No credential is distributed; no simulated API response is represented as live.
Provider schemas can change; inspect returned payloads and map real pipeline IDs before use.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
import httpx

BASE_URL = 'https://services.leadconnectorhq.com'

class GHLAPIError(RuntimeError):
    def __init__(self, status_code: int, retry_after: str | None = None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f'HighLevel API returned {status_code}')

@dataclass(frozen=True)
class GHLSettings:
    token: str
    location_id: str
    calendar_id: str | None = None
    pipeline_id: str | None = None
    stage_id: str | None = None
    booked_stage_id: str | None = None

class GHLTestConnector:
    def __init__(self, config: GHLSettings, transport: httpx.BaseTransport | None = None):
        self.config = config
        if not config.token or not config.location_id:
            raise ValueError('Test sub-account token and location ID are required')
        self.client = httpx.Client(base_url=BASE_URL,timeout=15.0,transport=transport)

    def _request(self, method: str, path: str, *, version='v3', **kwargs):
        headers = {'Authorization':f'Bearer {self.config.token}', 'Version':version,
                   'Accept':'application/json'}
        response=self.client.request(method,path,headers=headers,**kwargs)
        if response.is_error:
            raise GHLAPIError(response.status_code,response.headers.get('Retry-After'))
        return response.json()

    def upsert_contact(self, *, first_name:str, email:str|None=None, phone:str|None=None):
        if not email and not phone: raise ValueError('Email or phone is required')
        return self._request('POST','/contacts/upsert',json={
            'locationId':self.config.location_id,'firstName':first_name,
            'email':email,'phone':phone,'createNewIfDuplicateAllowed':False,
            'source':'NECTELIS Authorized Synthetic Test'})

    def free_slots(self, start: datetime, end: datetime, timezone_name: str):
        if not self.config.calendar_id: raise ValueError('GHL_CALENDAR_ID required')
        if end - start > timedelta(days=31): raise ValueError('GHL 31-day query limit')
        return self._request('GET',f'/calendars/{self.config.calendar_id}/free-slots',params={
            'startDate':int(start.timestamp()*1000),'endDate':int(end.timestamp()*1000),
            'timezone':timezone_name})

    def book_test_appointment(self, *, contact_id:str, start: datetime, end:datetime):
        if not self.config.calendar_id: raise ValueError('GHL_CALENDAR_ID required')
        # Must check free-slots immediately before calling; do not bypass availability validation.
        return self._request('POST','/calendars/events/appointments',version='v3',json={
            'calendarId':self.config.calendar_id,'locationId':self.config.location_id,
            'contactId':contact_id,'startTime':start.isoformat(),'endTime':end.isoformat(),
            'title':'NECTELIS synthetic validation', 'toNotify':False,
            'ignoreFreeSlotValidation':False, 'ignoreDateRange':False})

    def upsert_opportunity(self, *, contact_id: str, name: str, stage_id: str | None = None,
                           opportunity_id: str | None = None):
        if not self.config.pipeline_id or not (stage_id or self.config.stage_id):
            raise ValueError('GHL pipeline and stage IDs required')
        payload = {
            'locationId': self.config.location_id, 'pipelineId': self.config.pipeline_id,
            'pipelineStageId': stage_id or self.config.stage_id, 'contactId': contact_id,
            'name': name, 'status': 'open',
            'followers': [], 'isRemoveAllFollowers': False, 'followersActionType': 'add'
        }
        if opportunity_id:
            payload['id'] = opportunity_id
        return self._request('POST', '/opportunities/upsert', json=payload)

    def create_test_opportunity(self, *, contact_id: str, name: str):
        return self.upsert_opportunity(contact_id=contact_id, name=name)


    def close(self): self.client.close()
