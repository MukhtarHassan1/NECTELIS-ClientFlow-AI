# NECTELIS ClientFlow — Provider activation manual

**State of this release:** GHL, Vapi and Twilio modules have tested offline paths. There is no claim that a real vendor account was contacted. The browser Workbench is always local and never accepts provider keys. The optional provider activation CLI is separate and guarded.

## 0. Security and prerequisites

1. Use authorized vendor test accounts, never an unapproved client's production account.
2. Copy `.env.example` to `.env` in the extracted project directory. The `.env` is Git-ignored. **Do not paste real keys in chat, source control, or videos.**
3. For inbound webhooks, use a secured **public HTTPS** domain with an accurate external URL. Configure a reverse proxy or approved tunnel for testing; provider signatures must use the exact URL seen by Twilio, including any forwarded scheme/path/query.
4. Set `ENABLE_PROVIDER_WEBHOOKS=true` only after authentication and network restrictions are configured. `ADMIN_API_KEY` and `WEBHOOK_API_KEY` should also be long random values before exposing a server. The public demo dashboard is not authenticated; keep the demo UI private or put it behind access control. Never publish it to the open internet unchanged.
5. Actual contact data is disabled by default (`ALLOW_REAL_WEBHOOK_CONTACTS=NO`). Use synthetic contacts and allowed recipients. Audit local laws, SMS registration, opt-in, quiet hours, opt-out, retention and provider terms before production.
6. **Test each provider in an account you control**. Platform accounts may require verified billing, plans, phone numbers, messaging registration, calendar/user assignment, or OAuth scopes. A token alone does not complete those arrangements.

## 1. GoHighLevel: authorized synthetic test orchestration

Code: `clientflow/ghl_connector.py` (contacts, opportunities, free slots and appointments) + `clientflow/provider_orchestrator.py` (sequence and errors) + `clientflow/live_bridge.py` (durable event ledger and no automatic replay after uncertainty).

Official API: https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html and https://marketplace.gohighlevel.com/docs/ghl/opportunities/upsert-opportunity/ and https://marketplace.gohighlevel.com/docs/ghl/calendars/get-slots/ .

1. Obtain authorized **sub-account** access and a Private Integration Token with the minimum necessary contact, opportunity and calendar/event scopes.
2. Create the test pipeline and **two distinct stages** (qualified, booked) inside the sub-account. Create an active calendar with the assigned team member and available time slots. Check that **Allow Duplicate Contact** settings match the account's identity policy.
3. Set:

```env
GHL_PRIVATE_INTEGRATION_TOKEN=
GHL_LOCATION_ID=
GHL_CALENDAR_ID=
GHL_PIPELINE_ID=
GHL_STAGE_QUALIFIED_ID=
GHL_STAGE_BOOKED_ID=
GHL_TEST_EMAIL_ALLOWLIST=your-owned-synthetic-test@example.com
GHL_LIVE_TEST_WRITE_ENABLED=NO
```

4. Check only whether configuration fields are present; **no remote request**:

```powershell
.venv\Scripts\python.exe -m scripts.provider_activation ghl
```

5. After explicitly authorizing a real test write, set `GHL_LIVE_TEST_WRITE_ENABLED=YES`, then **once**:

```powershell
.venv\Scripts\python.exe -m scripts.provider_activation ghl --execute --acknowledge --event demo-ghl-001 --name "Synthetic Reviewer" --email your-owned-synthetic-test@example.com --slot 2027-03-10T14:00:00-04:00
```

Choose a **real available future slot** on the configured calendar; the date above is illustrative. If it has passed, select another. Use a fresh event ID only for an intentionally *new* test, not to retry an uncertain booking. The database stores an attempt before sending a write. A crash or timeout yields **reconciliation required** rather than attempting a second appointment. Inspect GHL Contacts, Opportunities and Calendar independently; confirm no unexpected notifications or workflows were triggered. Provider schema quirks, status values, calendar owner details and permission boundaries require these real tests.

**Not included:** native GHL workflow snapshot import or automatic multi-tenant OAuth onboarding. That is a different feature from direct REST API integration.

## 2. Vapi: inbound end-of-call report to CRM + booking

Code: `clientflow/channel_adapters.py` and `clientflow/api.py`.

Official docs: https://docs.vapi.ai/server-url and https://docs.vapi.ai/server-url/server-authentication .

1. Create a Vapi assistant and configure a structured output field mapping: `first_name`, `email` or E.164 `phone`, `service`, boolean `consent_to_contact`, and optionally timezone-aware ISO `requested_slot`.
2. Configure the assistant Server URL with the **end-of-call-report** event sent to:
   `https://YOUR-HTTPS-DOMAIN/api/v1/channels/vapi/home-services-demo`.
3. Configure a Vapi Server Authentication credential with a secret delivered as `X-Vapi-Secret`; set the same value as `VAPI_WEBHOOK_SECRET` in `.env`. Depending on Vapi account configuration, headers can differ: inspect an authorized webhook request and adjust your Vapi credential setup to match.
4. Set `ENABLE_PROVIDER_WEBHOOKS=true`; run with a synthetic contact before permitting anything else. The local engine handles existing contacts, replay by `call.id`, qualification and optional booking when slot and consent permit it.
5. A Vapi **tool-calls** event (real-time booking *during* the call) needs a tool-specific synchronous response contract and is **not implemented** in this edition. The tested path is end-of-call processing. Calls and telephony numbers are configured inside Vapi separately, and Vapi may incur usage charges.
6. The Vapi webhook currently writes to the **local CRM**, not directly to an authenticated GHL account. Deploying a combined Vapi → real GHL flow requires authorized GHL routing and cross-provider reconciliation testing.

Inspect Vapi webhook logs and local event ledger for one accepted report, one repeated `call.id`, and one malformed report. Never infer SMS/calling consent from a recorded call without explicit validation.

## 3. Twilio: inbound SMS, outbound REST, delivery lifecycle

Code: `clientflow/channel_adapters.py`, `clientflow/twilio_gateway.py`, `clientflow/api.py`, `scripts/provider_activation.py`.

Official docs: https://www.twilio.com/docs/usage/webhooks/webhooks-security , https://www.twilio.com/docs/messaging/api/message-resource and https://www.twilio.com/docs/messaging/guides/outbound-message-status-in-status-callbacks .

1. Get authorized Twilio Account SID, Auth Token and a sender capable of sending the intended SMS. Depending on destination country, messaging service setup, sender registration, restrictions, approval and charges may apply.
2. Set in `.env`:

```env
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
TWILIO_PUBLIC_WEBHOOK_URL=https://YOUR-HTTPS-DOMAIN/api/v1/channels/twilio/home-services-demo
TWILIO_STATUS_CALLBACK_URL=https://YOUR-HTTPS-DOMAIN/api/v1/channels/twilio/status
TWILIO_TEST_RECIPIENT_ALLOWLIST=YOUR-OWN-TEST-PHONE-IN-E164
TWILIO_LIVE_TEST_WRITE_ENABLED=NO
ENABLE_PROVIDER_WEBHOOKS=false
```

3. Configure the Twilio number Messaging webhook URL for HTTP POST to `TWILIO_PUBLIC_WEBHOOK_URL`, validate the actual `X-Twilio-Signature`, and inspect a test webhook's receipt and replay. The incoming SMS becomes **manual review**, not automatic consent or an appointment.
4. After obtaining test-recipient consent, enabling inbound webhook settings and validating sender restrictions, explicitly set `TWILIO_LIVE_TEST_WRITE_ENABLED=YES`. This operator-only command can send exactly one allowlisted SMS:

```powershell
.venv\Scripts\python.exe -m scripts.provider_activation twilio --execute --acknowledge --event demo-sms-001 --to YOUR-OWN-TEST-PHONE-IN-E164
```

5. Check Twilio's Message logs for the SID and delivery events. Signed status POSTs to `/api/v1/channels/twilio/status` update a persistent delivery row. Callbacks are verified *before* database updates; later queued/sent events cannot overwrite terminal delivery failures.
6. Never blindly retry an ambiguous `Messages.json` POST; the service may have accepted it even if your connection timed out. The CLI reserves the attempt before contacting Twilio, and requires manual reconciliation after an unknown outcome.
7. **Voice:** Twilio-to-Vapi telephone routing/SIP trunks and live voice call behavior are not verified or automatically configured here. Vapi end-of-call lead intake is the supported voice-agent data path; don't describe that as a complete Twilio SIP/calling deployment.

## 4. n8n

`n8n/ClientFlow_AI_Lead_Orchestration.json` is an exported workflow; it is **not evidence of a successful import or credential authentication**. Import it into an authorized workspace, configure the backend webhook URL and test the success/duplicate/error routes before citing n8n execution as verified.

## 5. Production-readiness gate

This is a **local demonstration and guarded test-account integration kit**, not a turnkey production multi-client system. Production needs authenticated dashboard access, persistent managed DB, backups, concurrency scaling, secret rotation, retries and dead-letter monitoring, compliant messaging consent/opt-out, provider-specific timeout reconciliation, role-based access, monitoring/alerts, webhook replay protection, privacy retention and hands-on live certification. Never expose the default localhost application directly to the public internet.

## 6. Optional Vapi → GHL test-account bridge

The Vapi webhook handler can optionally call the **same authorized GHL test bridge** after processing the local lead. This is deliberately off by default. It requires an authorized real GHL account, provider setup above, and the allowlisted synthetic contact identity. Set:

```env
ENABLE_GHL_WEBHOOK_BRIDGE=true
GHL_LIVE_TEST_WRITE_ENABLED=YES
GHL_TEST_EMAIL_ALLOWLIST=your-owned-synthetic-test@example.com
```

The workflow is: authenticated Vapi end-of-call report → schema/consent validation → local event ledger and booking → durable GHL test job → contact upsert → qualified opportunity → availability check → appointment and stage update (or safe review). The GHL job ledger prevents silent replays after uncertain outcomes; **this entire cross-provider live path is untested** until your vendor accounts are available. A real remote conflict can cause local and GHL booking states to differ; reconcile both rather than assuming distributed atomicity. This is a test-account integration path, not a transactional production multi-platform guarantee.
