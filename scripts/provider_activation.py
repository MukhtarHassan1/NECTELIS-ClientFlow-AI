"""Local operator CLI. No provider writes without explicit flags and allowlists."""
from __future__ import annotations
import argparse,os,json
from datetime import datetime
from clientflow.config import ROOT
from clientflow import db
from clientflow.ghl_connector import GHLSettings
from clientflow.live_bridge import authorized_ghl_test
from clientflow.twilio_gateway import TwilioSettings,TwilioGateway,save_dispatch

p=argparse.ArgumentParser()
p.add_argument('provider',choices=['ghl','twilio','vapi'])
p.add_argument('--execute',action='store_true',help='Explicitly enable one authorized provider write')
p.add_argument('--acknowledge',action='store_true',help='Confirm this is an owned/authorized test account')
p.add_argument('--email',default='')
p.add_argument('--to',default='')
p.add_argument('--name',default='NECTELIS Synthetic Contact')
p.add_argument('--event',default='')
p.add_argument('--slot',default='',help='Future ISO datetime with timezone offset')
a=p.parse_args()
if a.provider=='vapi':
 print(json.dumps({'configure':'Vapi assistant Server URL / server auth credential',
    'endpoint':'https://YOUR-PUBLIC-HTTPS-HOST/api/v1/channels/vapi/home-services-demo',
    'event':'end-of-call-report','header':'X-Vapi-Secret',
    'requires':['ENABLE_PROVIDER_WEBHOOKS=true','VAPI_WEBHOOK_SECRET','synthetic test contact identity','public HTTPS endpoint'],
    'note':'Tool-calls during a live call are a different protocol and not enabled in this release'},indent=2));exit()
if not (a.execute and a.acknowledge):
 print('READ-ONLY PREFLIGHT. No network request made. To test one authorized write, pass --execute --acknowledge.')
 if a.provider=='ghl':
  print(json.dumps({'required_env':['GHL_PRIVATE_INTEGRATION_TOKEN','GHL_LOCATION_ID','GHL_CALENDAR_ID','GHL_PIPELINE_ID','GHL_STAGE_QUALIFIED_ID','GHL_STAGE_BOOKED_ID','GHL_LIVE_TEST_WRITE_ENABLED','GHL_TEST_EMAIL_ALLOWLIST'],
  'set':{k:bool(os.getenv(k)) for k in ['GHL_PRIVATE_INTEGRATION_TOKEN','GHL_LOCATION_ID','GHL_CALENDAR_ID','GHL_PIPELINE_ID','GHL_STAGE_QUALIFIED_ID','GHL_STAGE_BOOKED_ID','GHL_TEST_EMAIL_ALLOWLIST']}},indent=2))
 else:print('Required: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER, TWILIO_STATUS_CALLBACK_URL, TWILIO_TEST_RECIPIENT_ALLOWLIST, TWILIO_LIVE_TEST_WRITE_ENABLED')
 exit()
if a.provider=='ghl':
 if os.getenv('GHL_LIVE_TEST_WRITE_ENABLED')!='YES':raise SystemExit('GHL live write switch must be YES')
 if not a.slot or not a.event:raise SystemExit('--slot and --event are mandatory')
 allow=set(x.strip().lower() for x in os.getenv('GHL_TEST_EMAIL_ALLOWLIST','').split(',') if x.strip())
 cfg=GHLSettings(os.getenv('GHL_PRIVATE_INTEGRATION_TOKEN',''),os.getenv('GHL_LOCATION_ID',''),
        os.getenv('GHL_CALENDAR_ID'),os.getenv('GHL_PIPELINE_ID'),os.getenv('GHL_STAGE_QUALIFIED_ID'),
        os.getenv('GHL_STAGE_BOOKED_ID'))
 db.connect_db()
 result=authorized_ghl_test(event_id=a.event,name=a.name,email=a.email.lower(),
    start=datetime.fromisoformat(a.slot),config=cfg,approved_emails=allow,write_enabled=True)
 print(json.dumps(result,indent=2))
else:
 if os.getenv('TWILIO_LIVE_TEST_WRITE_ENABLED')!='YES':raise SystemExit('Twilio live write switch must be YES')
 allow=set(x.strip() for x in os.getenv('TWILIO_TEST_RECIPIENT_ALLOWLIST','').split(',') if x.strip())
 if not a.event:raise SystemExit('One unique --event identifier required')
 if a.to not in allow:raise SystemExit('Recipient missing from explicit test allowlist')
 cfg=TwilioSettings(os.getenv('TWILIO_ACCOUNT_SID',''),os.getenv('TWILIO_AUTH_TOKEN',''),
    os.getenv('TWILIO_FROM_NUMBER',''),os.getenv('TWILIO_STATUS_CALLBACK_URL',''))
 db.connect_db()
 from sqlalchemy import select
 with db.session() as session:
  previous=session.scalar(select(db.ProviderJob).where(db.ProviderJob.provider=='twilio',
      db.ProviderJob.external_event_key==a.event))
  if previous:raise SystemExit('Already attempted: inspect provider delivery state and reconcile before retry')
  import hashlib
  reserve=db.ProviderJob(id=db.uid('pjob'),provider='twilio',external_event_key=a.event,
     fingerprint=hashlib.sha256(a.to.encode()).hexdigest(),state='started')
  session.add(reserve);session.commit()
 gateway=TwilioGateway(cfg)
 try:
  result=gateway.send_sms(to=a.to,body='NECTELIS authorized one-time synthetic integration test',
                      consent=True,approved_recipients=allow,allow_outbound=True)
  receipt=save_dispatch(job_id=a.event,message_sid=result['message_sid'],initial_status=result['status'])
  with db.session() as session:
   record=session.scalar(select(db.ProviderJob).where(db.ProviderJob.provider=='twilio',
        db.ProviderJob.external_event_key==a.event))
   record.state='completed';record.result_json=json.dumps(receipt);session.commit()
  print(json.dumps(receipt,indent=2))
 except Exception:
  with db.session() as session:
   record=session.scalar(select(db.ProviderJob).where(db.ProviderJob.provider=='twilio',
        db.ProviderJob.external_event_key==a.event))
   record.state='needs_reconciliation';session.commit()
  raise SystemExit('Dispatch did not confirm. Inspect Twilio Message logs before any further attempt.')
 finally:gateway.close()
