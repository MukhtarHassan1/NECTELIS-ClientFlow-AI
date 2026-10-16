# Final verification record — integration edition

**Delivered scope:** ClientFlow mock lead engine + Connector Observatory for HighLevel HTTP contracts and Vapi/Twilio inbound contracts. **No live provider account was used.**

- Backend/unit/HTTP integration tests: **70 passed** (run `python -m pytest -q`).
- Offline provider scenario report: **10/10 passed** (run `python -m scripts.export_connector_evidence`).
- Browser JavaScript scenario buttons: **10/10 passed**, tested in headless Chromium with FastAPI running locally and requests bridged through an isolated browser harness because direct browser navigation was blocked by the environment.
- Mobile responsive lab: 390 px width; no horizontal overflow observed.
- New GHL behaviors: contact upsert; opportunity upsert; free-slot check; appointment; booked-stage upsert; replay safety; changed-body ID conflict; HTTP 429 bounded retry; HTTP 401 no retry; unavailable slot; lost-response manual reconciliation.
- Vapi: structuredData to LeadEvent, call ID replay identity, endpoint disabled by default and guarded by configured secret; no actual call.
- Twilio: signed classic form webhook and replay handling, tamper/URL-path verification, endpoint disabled by default; no actual SMS.
- n8n: existing sanitized export retained; live import remains unverified.

**Not tested/not claimed:** GHL sub-account permissions, native automations, real remote appointment concurrency and provider idempotency, Vapi tool calls, Twilio actual SMS/calling, public deployment, external notifications, paid AI inference or actual production-scale performance. The default application remains mock only.

Reports: `evidence/pytest-results.txt`, `evidence/pytest-junit.xml`, `evidence/provider-contract-report.json`, `evidence/browser-contract-verification.txt`.

- Reviewer-controlled live browser challenge: **7/7 assertions passed**, verified against actual FastAPI TestClient + SQLite in an isolated Chromium harness (direct local HTTP navigation blocked in the build environment).
- Independent CLI challenge: **7/7 assertions passed**, fresh temporary SQLite; see `evidence/independent-local-proof-latest.json`.
- Source and instructions: `docs/REVIEWER_CHALLENGE.md`; Github CI workflow is provided but has **not** yet run on the user’s GitHub account.
