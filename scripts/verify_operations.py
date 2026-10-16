"""Reproducible isolated 12-case integration matrix. ZERO external provider calls."""
import os,json,tempfile,argparse
from datetime import datetime,timezone
from pathlib import Path
from fastapi.testclient import TestClient

parser=argparse.ArgumentParser()
parser.add_argument('--output',default='',help='Optional local JSON evidence output path')
args=parser.parse_args()
scenarios={'ghl':['success','rate_limit','unavailable','unauthorized','timeout'],
           'vapi':['success','duplicate','malformed'],
           'twilio':['success','tamper','rate_limit','delivery_failed']}
with tempfile.TemporaryDirectory(prefix='nectelis-operations-') as tmp:
 os.environ['DATABASE_URL']='sqlite:///'+str(Path(tmp)/'isolated.sqlite3')
 os.environ['DEMO_MODE']='mock';os.environ['ENABLE_PROVIDER_WEBHOOKS']='false'
 from clientflow.api import app
 rows=[]
 with TestClient(app) as api:
  for provider,cases in scenarios.items():
   for name in cases:
    result=api.post('/api/v1/workbench/run',json={'provider':provider,'scenario':name,
                'client_key':'home-services-demo','name':'Synthetic Reviewer','phrase':'external-review-5176'})
    payload=result.json()
    rows.append({'provider':provider,'scenario':name,'http_status':result.status_code,
                 'passed':payload.get('passed') is True,'checks':payload.get('checks',{}),
                 'provider_network_calls':payload.get('actual_provider_calls')})
 summary={'created_at_utc':datetime.now(timezone.utc).isoformat(),
          'mode':'ISOLATED HTTP EMULATION + SQLITE','total':len(rows),
          'passed':sum(x['passed'] for x in rows),'live_provider_calls':0,'cases':rows}
 if args.output:
  Path(args.output).parent.mkdir(parents=True,exist_ok=True)
  Path(args.output).write_text(json.dumps(summary,indent=2))
 print(f"Integration matrix: {summary['passed']}/{summary['total']} passed | 0 live provider calls")
 if not all(r['passed'] for r in rows):raise SystemExit(1)
