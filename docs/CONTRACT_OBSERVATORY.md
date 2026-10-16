# Connector Observatory — what is actually implemented

This is a working developer test laboratory, not a simulated login screen. The UI drives local FastAPI endpoints, which execute the **same `GHLTestConnector` HTTP methods** an authorized live-test harness would call. The transport is `httpx.MockTransport`, a deterministic stand-in for external HighLevel services. It records method, path, version, sanitized request-field names and status. No network request is sent to GHL.

## GoHighLevel request contracts (v3)

| Step | HTTP request | Verified offline behavior |
|---|---|---|
| Contact upsert | `POST /contacts/upsert` | Correct location / identity fields; create/update response |
| Opportunity upsert | `POST /opportunities/upsert` | Pipeline/stage/contact mapping, stable opportunity ID |
| Availability | `GET /calendars/{calendarId}/free-slots` | Query range in epoch milliseconds; confirm desired slot exists |
| Appointment | `POST /calendars/events/appointments` | Contact and calendar mapping; `toNotify=false`; `ignoreFreeSlotValidation=false` |
| Stage finalization | `POST /opportunities/upsert` | Reuse original opportunity ID and map booked stage |

The offline harness exercises booking, replay, existing-contact update, HTTP 429 with `Retry-After`, unavailable slot, 401 stop, changed-body replay conflict, and uncertain post-write appointment response. When the provider might have created a booking but the response is lost, the result is **reconciliation required**, not a blind second POST. The laboratory ledger lives for each scenario; the main lead engine retains its separate durable SQLite replay ledger.

**Nonclaims:** It does **not** establish that a HighLevel tenant accepts every payload, that duplicate matching works identically in every sub-account, that all scopes/permissions are granted, that native GHL workflows/snapshots are created, or that a remote booking survives concurrent conflict. Those require a real, authorized account and provider-side review.

## Vapi

`channel_adapters.normalize_vapi_report` accepts an `end-of-call-report` containing a stable `call.id` plus `analysis.structuredData` fields. It converts this to the ClientFlow lead contract and does not infer content from unreviewed transcripts. The optional `/api/v1/channels/vapi/{client_key}` endpoint is off by default and requires an operator-configured secret; **the Vapi `tool-calls` protocol is not implemented** and must not be advertised as such. No voice call, assistant creation, transcription, live appointment tool call or Vapi account execution has been verified.

## Twilio

`channel_adapters.validate_twilio_signature` validates the classic form webhook HMAC using a configured canonical HTTPS URL. Offline tests verify acceptance of a valid signature and rejection after request tampering. Inbound SMS normalizes to **manual review, no presumed consent**, using `MessageSid` for replay identity. The optional `/api/v1/channels/twilio/{client_key}` endpoint is off by default and requires the Twilio auth token, canonical URL and signed request. Twilio recommends its official RequestValidator SDK for production deployments; this proof currently covers only the classic form signature scheme, not JSON/Proxy/advanced webhook variants. It sends no SMS and places no calls.

## How to reproduce

1. Double-click `RUN_WINDOWS.bat` or run the local FastAPI server.
2. Open `http://127.0.0.1:8000` and scroll to **Show the mechanism**.
3. Click each GHL, Vapi, Twilio scenario. Read request/status trace and outcome.
4. Press **EXPORT VERIFIED TRACE** for a machine-readable proof explicitly marked offline.
5. For a single combined report, run `python -m scripts.export_connector_evidence`; the fresh file is saved to `evidence/provider-contract-report-latest.json` (the packaged baseline is `evidence/provider-contract-report.json`).
6. Run `python -m pytest -q`. Compare the count with `evidence/pytest-results.txt`.

**Why this helps clients:** They can see how a correct integration manages identity, routing, scheduling and failure states *before* their credentials are used. This does not replace the final live integration acceptance test.

## Official provider reference material

- HighLevel contact upsert: https://marketplace.gohighlevel.com/docs/ghl/contacts/upsert-contact/index.html
- HighLevel opportunity upsert: https://marketplace.gohighlevel.com/docs/ghl/opportunities/upsert-opportunity/index.html
- HighLevel free slots: https://marketplace.gohighlevel.com/docs/ghl/calendars/get-slots/
- HighLevel create appointment: https://marketplace.gohighlevel.com/docs/ghl/calendars/create-appointment/
- Vapi server events: https://docs.vapi.ai/server-url/events
- Vapi server authentication: https://docs.vapi.ai/server-url/server-authentication
- Twilio webhook validation: https://www.twilio.com/docs/usage/webhooks/webhooks-security

Provider contracts and access requirements may change. Revalidate against the docs and live account before deployment.
