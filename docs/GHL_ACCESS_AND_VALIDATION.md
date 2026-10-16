# Authorized GHL test-account integration plan

## Current status

**GHL HTTP adapter plus a five-operation offline execution path are built and contract-tested using `httpx.MockTransport`; no live GHL account was accessed or verified.** The live adapter is deliberately isolated from `DEMO_MODE=mock`. Do not claim native GHL workflows, real CRM records, live appointment confirmations or production deployment.

## Human-only setup

1. Obtain explicit written permission to test on a dedicated, nonproduction GHL **sub-account**. Do not reuse any customer's production account or share tokens in chat.
2. Configure a **private integration token or OAuth access** with least-privilege scopes for the exact tested operations (contact write, calendar read, calendar event write, opportunity write). Use the correct sub-account ID and access type. Check permission changes against current GHL documentation.
3. Copy `.env.example` to `.env` and set `GHL_PRIVATE_INTEGRATION_TOKEN`, `GHL_LOCATION_ID`, `GHL_CALENDAR_ID`, `GHL_PIPELINE_ID`, `GHL_STAGE_BOOKED_ID` in your private environment. Do not commit `.env`.
4. Use `python scripts/ghl_live_check.py` for a read-only free-slots smoke test. Inspect the response. It sends no writes.
5. Only after review, run `GHL_LIVE_TEST_WRITE_ENABLED=YES python scripts/ghl_live_check.py --write-test-contact --acknowledge --test-email example-test@example.com` (PowerShell syntax differs). Confirm the synthetic record appears in the correct test location. Upsert can modify existing test contacts; review duplicate settings beforehand.
6. Manually check actual pipeline IDs and calendar appointment policies, compare request bodies with current provider docs and test one synthetic booking with native notifications disabled. The offline execution path invokes the booking method against its emulator, but the live backend remains gated. Live booking wiring, remote idempotency/reconciliation and real-provider integration tests remain a separate engineering stage.
7. Document each tested endpoint, HTTP response, native GHL record IDs (masked in public evidence), test date, and cleanup result. Only after this can a **GHL live-test adapter** be called verified.

## Provider documentation cross-checked Oct 2026

- Contact upsert, v3: https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html
- Calendar free-slots, v3: https://marketplace.gohighlevel.com/docs/ghl/calendars/get-slots/
- Appointment creation, v3: https://marketplace.gohighlevel.com/docs/ghl/calendars/create-appointment/
- Opportunity upsert, v3: https://marketplace.gohighlevel.com/docs/ghl/opportunities/upsert-opportunity/index.html

The code uses v3 headers for the documented operations. Reconfirm schemas/permissions for the specific account before a live integration.
