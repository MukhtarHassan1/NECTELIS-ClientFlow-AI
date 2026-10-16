# The Signal Room — Interface & Reliability Upgrade

**Release:** ClientFlow AI / Signal Room refresh (14 October 2026)
**Scope:** The original packaged ClientFlow proof was used as the foundation. This release replaces its old green CRM-style layout with an independent, original operations-instrument design and adds regression coverage.

## Design decisions

- **Signal-first visual language:** near-black ink, warm amber signals, cold-steel blue controls, off-white evidence reading area. No sidebar/dashboard-card template copied from another product.
- **Action before decoration:** a five-stage diagram highlights observed audit steps; each of eight one-click scenarios writes synthetic operations through the local FastAPI server.
- **Real information hierarchy:** input, exception controls, last JSON response, decision timeline, persisted ledger, profiles and delivery boundary are visible in one workspace.
- **Evidence remains honest:** mock operations, rule-based qualification and disabled customer outbound are identified directly in the interface.
- **Usable controls:** Run All Eight, scenario-specific pass indicators, real status filter, scoped audit inspection, copy JSON, export masked synthetic proof report, operator drawer, display density, motion preference and confirmation-gated local synthetic reset.
- **Responsive behavior:** tested with a 390 px viewport for horizontal overflow. Uses native labels and keyboard-reachable form controls; mobile layout stacks panels.

## Improvements verified in automated backend tests

1. **Changed-body event replay:** `(client_key, source, event_id)` is still the identity key, but now the normalized request is fingerprinted. An exact replay returns the previous result; a reused ID with different content returns `409` instead of silently claiming success.
2. **Cross-profile and cross-source audit isolation:** prefer `GET /api/v1/audit/{client_key}/{source}/{event_id}`. Ambiguous older, partial lookup paths return `409` rather than returning another profile/source's trace.
3. **Past appointments:** cannot be booked; are explicitly audited as unavailable.
4. **Synthetic reset CSRF boundary:** cross-origin browser requests to reset are refused, with localhost/same-origin control retained. This is NOT a public admin authentication system.
5. **Validation rejection protection:** malformed, unauthenticated webhook requests do not create persisted rejection rows when webhook API auth is enabled.
6. **Orphaned connector failures:** an upstream CRM failure creates an internal human-review action even when no contact was created.
7. **Existing bookings:** updating an already-booked contact without requesting a new appointment retains the prior confirmed future-booking stage.
8. **SQLite compatibility:** `connect_db()` adds the new `request_fingerprint` column to older local SQLite databases without dropping synthetic tables. Legacy events without a fingerprint require a new event ID on replay. This migration does NOT replace proper schema migration management for external databases.

## Actual verification

- Backend: run `python -m pytest -q` and see `evidence/pytest-results.txt` and `evidence/pytest-junit.xml`.
- Browser: JavaScript controls exercised in headless Chromium against the running FastAPI application through a local HTTP bridge, because this build environment blocks browser navigation to localhost. **All eight scenarios passed, no JS exceptions, and no horizontal overflow at 390 px.** The user should still open the app normally at `127.0.0.1:8000` to confirm browser-to-server networking in their own environment.
- The screenshots in `evidence/` were captured from those actual UI interactions, not invented backend logs or fabricated provider accounts.
- GHL and n8n integrations remain NOT live-verified. No external SMS/email/voice activity was performed.

## Limitations to disclose

- This mock proof is single-process. Its Python lock serializes local processing; **it is not a distributed booking lock** and not proof of global provider exactly-once semantics.
- Real GHL credentials, authorized user permissions, native GHL workflow tests, API rate limits and production CRM behavior still require independent validation.
- The operator interface is for loopback development. Do not deploy it publicly without authentication, authorization, CSRF controls, a session-based gateway, HTTPS and infrastructure hardening.
- `ADMIN_API_KEY` and `WEBHOOK_API_KEY` are suitable for secured API clients; setting them will require authenticated proxy integration for the simple browser UI. Never embed secret admin keys into public JavaScript.
- Optional Ollama inference remains opt-in and advisory; the routing/booking decisions shown in the included screenshots are rule-based.

## Human handoff

1. Extract the ZIP to a **new** folder to avoid mixing old frontend assets.
2. Run `RUN_WINDOWS.bat`, open `http://127.0.0.1:8000`, confirm **LOCAL SANDBOX / MOCK CRM**.
3. Click **Run All Eight**; inspect both the results and the per-event audit timeline.
4. Open **Room settings** to test density, reduce motion or reset local test data. Reset requires confirmation.
5. Only after that, connect an *authorized* GHL test sub-account in a separate verification step and import the provided n8n workflow into a permitted workspace. See `docs/GHL_ACCESS_AND_VALIDATION.md` and `docs/N8N_IMPORT.md`.
6. Record a walkthrough of the genuinely running workspace for NECTELIS's Upwork proposals. Claim only the modes that you tested.
