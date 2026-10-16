"""Explicit, isolated GHL smoke test. Read-only by default.

Never copy production credentials into the project; set them in local environment.
Writes require two deliberate flags and an allow-listed example.com email.
"""
import argparse
import os
from datetime import datetime, timedelta, timezone
from clientflow.config import ROOT  # loads local .env without printing secrets
from clientflow.ghl_connector import GHLSettings, GHLTestConnector

parser=argparse.ArgumentParser(description='Run strictly authorized GHL sub-account validation')
parser.add_argument('--write-test-contact',action='store_true',help='One synthetic test upsert; no bulk sends')
parser.add_argument('--acknowledge',action='store_true',help='Confirm the named location belongs to your authorized sandbox')
parser.add_argument('--test-email',default='',help='Must end in @example.com')
args=parser.parse_args()
config=GHLSettings(token=os.getenv('GHL_PRIVATE_INTEGRATION_TOKEN',''),
  location_id=os.getenv('GHL_LOCATION_ID',''),calendar_id=os.getenv('GHL_CALENDAR_ID'))
if not config.token or not config.location_id:
    raise SystemExit('Missing GHL_PRIVATE_INTEGRATION_TOKEN / GHL_LOCATION_ID; no request was sent')
if args.write_test_contact:
    if not args.acknowledge or not args.test_email.endswith('@example.com'):
        raise SystemExit('Write refused; --acknowledge and --test-email test@example.com are mandatory')
    if os.getenv('GHL_LIVE_TEST_WRITE_ENABLED','')!='YES':
        raise SystemExit('Write refused; set GHL_LIVE_TEST_WRITE_ENABLED=YES intentionally')
with_client=GHLTestConnector(config)
try:
    if not args.write_test_contact:
        print('Read-only validation: retrieving one-day free slots (requires GHL_CALENDAR_ID).')
        if not config.calendar_id: raise SystemExit('Set GHL_CALENDAR_ID for read-only check')
        begin=datetime.now(timezone.utc)+timedelta(days=1)
        print('Free slot date keys:',list(with_client.free_slots(begin,begin+timedelta(days=1),'America/New_York').keys()))
    else:
        result=with_client.upsert_contact(first_name='Nectelis Synthetic Test',email=args.test_email)
        print('Real GHL TEST contact ID:',result.get('contact',{}).get('id'))
        print('Created new:',result.get('new'))
finally:
    with_client.close()
