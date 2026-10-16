"""Create a narrowly targeted, truthful proof brief from the same reusable build."""
from __future__ import annotations
from pathlib import Path
import argparse

PROOFS={
 'ghl':('CRM contact and opportunity upsert plus availability-aware booking',
        'GHL HTTP connector methods and their fail/replay behavior were executed against an offline emulator; real GHL sub-account validation is pending.',
        'How does your location configure contact duplicate matching and what are your pipeline/calendar IDs?',
        'GoHighLevel Connector Observatory / GHL booking + replay'),
 'n8n':('webhook intake, validation, status routing and audit history',
        'The engine runs locally; a sanitized n8n workflow export exists but has not been imported and tested in a live workspace.',
        'Which event source and error-retry behavior should trigger the first workflow?',
        'Signal Room / replay + 429; n8n workflow JSON'),
 'ai-voice':('structured voice-intake payload normalization and consent-aware booking handoff',
        'Vapi end-of-call payload mapping is offline-tested; no actual phone call or live assistant tool invocation has been verified.',
        'Do you need live booking during a call, or intake handoff at end of call?',
        'Connector Observatory / Vapi inbound; Signal Room / qualification'),
 'twilio':('signed inbound-message validation, idempotency and safe human review',
        'Twilio classic SMS webhook signature validation is offline-tested; no real Twilio delivery or outbound messaging was tested.',
        'Which channels and consent/quiet-hours rules apply to your account?',
        'Connector Observatory / Twilio inbound; Signal Room / consent gate'),
 'api':('FastAPI webhook contracts, replay safety, data normalization and failure isolation',
        'Local API, database, and provider emulation have automated evidence; third-party service deployment remains separate.',
        'What is the authoritative identifier and expected retry behavior for the source events?',
        'Signal Room / evidence trail; Connector Observatory / 429 + ambiguous timeout'),
 'backend':('persistent processing, identity resolution, conflict-aware scheduling and audit trails',
        'Backend automated tests cover local reliability rules; scalability and production security are not certified.',
        'What data store, peak load and recovery-time requirements do you have?',
        'Signal Room / execution ledger; pytest results')
}

parser=argparse.ArgumentParser(description='Generate honest NECTELIS evidence snippet for a job type')
parser.add_argument('--job',choices=sorted(PROOFS),required=True)
parser.add_argument('--industry',default='home services',help='Relevant industry for the job')
parser.add_argument('--job-title',default='automation implementation',help='Client job title/context')
args=parser.parse_args()
value, boundary, question, evidence=PROOFS[args.job]
text=f'''# NECTELIS — Job-specific proof brief

**Target request:** {args.job_title}
**Industry context:** {args.industry}
**Proof:** ClientFlow AI — The Signal Room

## Relevant demonstrated engineering

We developed a configurable lead-processing system that demonstrates **{value}**. For a {args.industry} implementation, we would map your actual data fields, permissions, business rules and failure policies before connecting third-party accounts.

**Evidence to show:** {evidence}. The underlying core uses synthetic local test data; provider-specific contract evidence is not evidence of a real account being connected.

**Verified vs. pending:** {boundary}

## First scoped deliverable

Review the client's authorization and source/destination contracts, configure one real end-to-end path in an approved test environment, test normal and failure cases, then hand over an audit-backed video and runbook. Do not promise this step is already deployed.

**Smart scoping question:** {question}

## Before sending

- Replace this generic job title and industry with the actual listing details.
- Link only screenshots or recorded sequences the agency can reproduce.
- Describe team contributions accurately; do not invent customer outcomes, metrics, or live provider validation.
- Do not include private credentials, webhook URLs or real contact data.
'''
out=Path('portfolio/generated')
out.mkdir(parents=True,exist_ok=True)
filename=out/(args.job.replace('-','_')+'-proof-brief.md')
filename.write_text(text,encoding='utf-8')
print(filename)
