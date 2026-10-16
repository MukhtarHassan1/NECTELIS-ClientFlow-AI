"""Run an end-to-end synthetic proof, print evidence, no external API calls."""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from clientflow.db import connect_db
from clientflow.schemas import LeadEvent
from clientflow.service import process, event_trace

connect_db()
local=datetime.now(ZoneInfo('America/New_York'))+timedelta(days=3)
while local.weekday()>=5: local+=timedelta(days=1)
local=local.replace(hour=11,minute=0,second=0,microsecond=0)
key='walkthrough-'+uuid.uuid4().hex[:8]
base={'event_id':key, 'source':'demo_ui','client_key':'home-services-demo',
      'lead':{'first_name':'Alex','email':key+'@example.com', 'service':'plumbing',
              'message':'Please help with a leaking pipe','consent_to_contact':True},
      'requested_slot':local.isoformat()}
for label, ev in [('NEW BOOKING',base),('EXACT REPLAY',base),('CONTACT UPDATE',{
    **base,'event_id':key+'-updated','lead':{**base['lead'],'phone':'+15550101007'}, 'requested_slot':None}),
    ('429 -> SUCCESS',{**base,'event_id':key+'-retry','lead':{**base['lead'],'email':'retry'+key+'@example.com'},
                       'requested_slot':None, 'simulate':{'crm':'429,200'}})]:
    result=process(LeadEvent.model_validate(ev))
    print('\n'+label, '\n'+json.dumps(result,indent=2))
    print('AUDIT STEPS:',[x['step'] for x in event_trace(ev['event_id'])['timeline']])
