"""Independent, zero-subscription acceptance check against actual app + temporary SQLite.

Runs in isolation: does not use (or overwrite) the presenter's current local
clientflow_demo.sqlite3. Provides reproducible evidence outside the browser.
"""
from __future__ import annotations
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo
from fastapi.testclient import TestClient


def main():
    with tempfile.TemporaryDirectory(prefix='nectelis-proof-') as tmp:
        os.environ['DATABASE_URL'] = 'sqlite:///'+str(Path(tmp)/'actual.sqlite3')
        os.environ['DEMO_MODE'] = 'mock'
        os.environ['DRY_RUN'] = 'false'
        # Remove optional locally configured admin/webhook keys from isolated checks.
        os.environ.pop('ADMIN_API_KEY', None)
        os.environ.pop('WEBHOOK_API_KEY', None)
        from clientflow.api import app
        from clientflow import db
        # Choose an Eastern Time weekday at 11AM 2+ weeks from now.
        target = datetime.now(ZoneInfo('America/New_York'))+timedelta(days=16)
        while target.weekday()>=5:
            target+=timedelta(days=1)
        target=target.replace(hour=11,minute=0,second=0,microsecond=0)
        eid='witness-'+uuid4().hex[:14]
        request={'event_id':eid,'source':'demo_ui','client_key':'home-services-demo',
                 'lead':{'first_name':'Independent Witness','email':'check-'+eid+'@example.com',
                         'service':'plumbing','message':'synthetic QA', 'consent_to_contact':True},
                 'requested_slot':target.isoformat()}
        with TestClient(app) as client:
            before=client.get('/api/v1/state').json()['stats']
            first=client.post('/api/v1/leads',json=request)
            replay=client.post('/api/v1/leads',json=request)
            proof=client.get('/api/v1/proof/verify/home-services-demo/demo_ui/'+eid)
            after=client.get('/api/v1/state').json()['stats']
            changed={**request,'lead':{**request['lead'],'first_name':'Changed Witness'}}
            mutation=client.post('/api/v1/leads',json=changed)
            validations={
              'HTTP 200 created a booked event': first.status_code==200 and first.json()['status']=='booked',
              'Exact replay caused zero additional side effects': replay.status_code==200 and replay.json()['duplicate_event'] is True,
              'Read-only SQL verifier passed': proof.status_code==200 and proof.json()['passed'] is True,
              'One event created': after['events']-before['events']==1,
              'One contact created': after['contacts']-before['contacts']==1,
              'One appointment created': after['bookings']-before['bookings']==1,
              'Modified replay rejected': mutation.status_code==409,
            }
            evidence={'mode':'LOCAL / SQLITE / SYNTHETIC','real_ghl_connected':False,
                'run_id':eid,'timestamp_utc':datetime.now(timezone.utc).isoformat(),
                'http_statuses':{'first':first.status_code,'replay':replay.status_code,
                                  'readback':proof.status_code,'mutated_replay':mutation.status_code},
                'actual_storage_deltas':{k:after[k]-before[k] for k in ('events','contacts','bookings')},
                'db_checks':proof.json().get('checks') if proof.status_code==200 else {},
                'checks':validations,'passed':all(validations.values()),
                'scope':'Actual FastAPI test requests & isolated SQLite writes. No GHL/Vapi/Twilio live connection.'}
            print(json.dumps(evidence,indent=2))
            outfile=Path('evidence/independent-local-proof-latest.json')
            outfile.parent.mkdir(exist_ok=True)
            outfile.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8')
            # Cleanup globally held engine so Windows can delete the temporary database.
            if db.engine is not None: db.engine.dispose()
            return 0 if evidence['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
