"""Generate fresh, reproducible OFFLINE provider test evidence. No network access required."""
from pathlib import Path
from datetime import datetime, timezone
import json
from clientflow.connector_lab import run_ghl_scenario
from clientflow.channel_adapters import channel_contract_scenario


def build_report():
    tests=[run_ghl_scenario(x) for x in (
        'booking','replay','update','rate_limit','unavailable','unauthorized',
        'replay_mutation','timeout_after_write')]
    tests.extend(channel_contract_scenario(x) for x in ('vapi','twilio'))
    return {'generated_at':datetime.now(timezone.utc).isoformat(),
            'environment':'OFFLINE MOCKTRANSPORT — NO LIVE PROVIDERS',
            'tests_run':len(tests),'passed':sum(x['passed'] for x in tests),
            'live_provider_calls':0,'results':tests}

if __name__=='__main__':
    report=build_report()
    target=Path('evidence/provider-contract-report-latest.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n')
    print(f"{report['passed']}/{report['tests_run']} offline provider contract tests passed.")
    print('Live provider calls:',report['live_provider_calls'])
    print('Saved',target)
    if report['passed']!=report['tests_run']:
        raise SystemExit(1)
