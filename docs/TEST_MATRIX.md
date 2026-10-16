# Test coverage & publish gate

Run `python -m pytest -q` from the project root. **Actual output** is saved in `../evidence/pytest-results.txt`. The individual cases below were exercised in the local test run; no real GHL, n8n Cloud, Outlook or telephony endpoints were called.

| Blueprint case | Observed in mock mode | Mechanism |
|---|---|---|
| CF-T01 new contact + booking | PASS | Contact, stage, one booking, local test notification |
| CF-T02 update existing | PASS | Same contact ID, changed phone |
| CF-T03 event replay | PASS | Stored result, no new writes |
| CF-T04 invalid service payload | PASS | HTTP 422, no contact; safe rejection audit |
| CF-T05 missing consent | PASS | Manual review, outbound suppressed |
| CF-T06 unavailable slot | PASS | Business-hours rejection |
| CF-T07 competing requests | PASS **single process** | Two threads, at most one booking |
| CF-T08 429 then 200 | PASS **simulated provider** | Bounded attempts with recorded retry |
| CF-T09 401 auth error | PASS **simulated provider** | No CRM writes, no retry loop |
| CF-T10 calendar ambiguity | PASS **simulated timeout after write** | Reconcile by durable event ID; one booking |
| CF-T11 team notification failed | PASS **simulated provider** | Booking retained and failure logged |
| CF-T12 switch industry | PASS | Real-estate YAML, no engine change |
| CF-T13 dry-run | PASS | No local writes |
| CF-T14 disallow outbound | PASS | Mock mode does not provide external transport |

Additional tests cover overlapping durations, identity conflicts, invalid phone, unknown client, profile isolation, authenticated API routes, local reset, audit PII minimization and GHL connector HTTP-contract checks. New regression cases verify changed-body replay rejection (409), source/profile-scoped traces, past-slot rejection, cross-origin reset protection, unauthenticated invalid-payload handling, operator follow-ups on early CRM failures and preserving confirmed future bookings.

**Not verified:** Real GHL native workflows, GHL live booking, real CRM rate limits, n8n import and execution, local Ollama with installed model, distributed worker concurrency, arbitrary remote side-effect recovery, Docker Compose on user hardware, and outbound messages. These require their own recorded evidence. Contract checks are not a substitute for an authorized provider test.

**UI run:** 8/8 scenarios in headless Chromium with JavaScript talking to the actual local FastAPI server via an HTTP bridge (the build environment blocks normal browser navigation). No page JavaScript exceptions; no horizontal overflow at a 390 px viewport. Refer to `evidence/browser-verification.txt` and `docs/SIGNAL_ROOM_UPGRADE.md`.
