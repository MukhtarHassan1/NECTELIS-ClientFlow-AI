# Engineering changelog — Operations Edition

## Implemented

- New **Integration Workbench** with dynamic synthetic inputs, three provider selectors, twelve selectable scenarios, browser-initiated FastAPI calls, safe trace rendering, raw JSON and downloadable execution receipts.
- **GHL job orchestration:** contact upsert → opportunity upsert → free-slot validation → appointment create → stage update; 429 retry only on contact upsert, no blind booking retry after transport ambiguity; 401 and conflicts isolated; realistic HTTP emulator with recorded paths and status codes.
- **Vapi:** end-of-call-report / structuredData → typed lead → local CRM → durable booking, plus replay and malformed payload tests; supports structuredData from message.analysis and call.analysis; `X-Vapi-Secret` authentication for opt-in webhooks.
- **Twilio:** signed form inbound SMS, manual-review default, outbound Messages REST client using HTTP Basic Auth, test-only recipient allowlist/consent gate, signed delivery callback with persistent message state, terminal-state locking, rate-limit and signature tampering paths.
- **Live test guards:** explicit operator CLI, environment switch, synthetic recipient allowlist, unique provider jobs persisted before remote writes, reconciliation rather than unsafe replay.
- **Security and quality:** fixed a FastAPI route-order conflict between Twilio status callback and dynamic channel path; added tests for malformed inputs, tampered callbacks, unauthorized outbound, delivery transitions and repeated bookings.

## Tests

See `evidence/pytest-results-operations.txt` and `evidence/operations-matrix-release.json`. The offline matrix uses a separate temporary SQLite database and zero live provider network calls.

## Remaining with vendor access

Live Twilio message delivery/country compliance, GHL account-specific schema/scopes/calendar users, Vapi authorized assistant webhook logs/phone call charges, public HTTPS deployment, native GHL workflows, Vapi synchronous tool-calls, Twilio SIP voice routing. These are not certified by offline tests.
