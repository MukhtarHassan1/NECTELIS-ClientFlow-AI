# REVIEWER CHALLENGE — PROVE IT IS NOT A STATIC HTML DEMO

**What it proves:** Real FastAPI requests mutate a real, local SQLite database; the response can be queried independently, replayed safely, and challenged with altered input. The downloaded package includes tests and source code. The GHL connector code is separately contract-tested offline. **Nothing in this demonstration proves that a live HighLevel account is connected.**

## 90-second client walkthrough

1. Open `http://127.0.0.1:8000` with your terminal visible. Show `http://127.0.0.1:8000/docs` briefly if a technical evaluator wants the FastAPI API surface.
2. Click **02 Proof challenge + connectors** or scroll to **Show the mechanism**. Point to **Your input. Our backend. Your verdict.**
3. **Ask the client to choose a random phrase** (e.g. `client chose code 49`) and a **synthetic** name (e.g. `Alex Reviewer`). Type it live.
4. Click **EXECUTE INDEPENDENT CHECK**. The browser sends the new request to `/api/v1/leads` and reads the resulting SQLite rows using `/api/v1/proof/verify/...`.
5. Show the **7/7 verdict**, especially new event/contact/booking counters, no extra records on replay, and `HTTP 409` for changed-body replay. Click **Inspect exact request and response evidence**.
6. Click **EXPORT ACTUAL EVIDENCE**, and open the JSON. It includes the chosen phrase, actual API request, responses, persisted-row verification, deltas, and a truthful `live_ghl_connected: false` flag.
7. In **GoHighLevel** click **01 / Contact → pipeline → booked** and show the `POST /contacts/upsert`, `POST /opportunities/upsert`, free-slots GET and appointment POST sequence. State explicitly: *"These are actual Python connector method calls with simulated HTTP responses, not a live GHL account."*
8. Open a command prompt in the project folder and run the independent verifier:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.independent_proof
   ```

   This generates a fresh event in **a separate temporary SQLite database**, runs real HTTP requests through the FastAPI ASGI application, verifies each stored effect, and writes `evidence/independent-local-proof-latest.json`. It does not overwrite your current demonstration records.

9. Optional technical evidence:

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -q
   ```

   Tests are not prefilled on the page. Failures produce nonzero exit codes. A purposely corrupted booking/contact linkage causes the readback verifier to fail in the regression suite.

## What happens when the reviewer presses the button

```
Reviewer-supplied phrase + synthetic name
      |
      v
POST /api/v1/leads   (new unpredictable ID)
      |    local FastAPI -> lead rules -> mock CRM -> SQLite booking & audit
      v
POST /api/v1/leads   (same event body)
      |    replay shield -> ZERO additional event/contact/booking rows
      v
GET /api/v1/proof/verify/{client}/{source}/{event}
      |    independent SQL query of event/contact/booking/audit
      v
GET /api/v1/state   (before/after counters)
      v
POST /api/v1/leads   (changed name; reused ID)
      |    HTTP 409, no mutation
      v
Backend-derived 7 assertions + downloadable raw evidence JSON
```

The verifier deliberately returns `passed=false` if its stored rows disagree (e.g., missing contact). It cannot be made to pass by changing a text badge in the browser. You can demonstrate this to developers using `tests/test_proof_verify.py` without corrupting your real demo database.

## Engineering / truthful client language

> We built ClientFlow AI as a working FastAPI and SQL-backed lead-to-booking proof. You can choose a random demo input while I run it; the system processes the event, persists the booking and audit, prevents duplicate writes, and independently checks the resulting database rows. We also execute our GHL API connector methods against an offline HTTP emulator and expose request traces for review. Live tenant authorization and account-specific tests are the final integration step, not something we've represented as complete.

**Do not say:** "Our CRM is connected to live GoHighLevel", "Vapi handles real calls" or "this is live GHL proof". Without authorized accounts, such statements would be false.

## Known boundaries

- `WEBHOOK_API_KEY` and `ADMIN_API_KEY` can protect routes; if enabled, the local browser demonstration needs a corresponding secure integration method. Default quick-start is local-only with no keys.
- The app runs on `127.0.0.1`, not a hosted public link. Client live participation requires screen sharing or their own authorized local setup; never expose admin/reset endpoints on the public Internet.
- SQLite is the local proof store; it is not evidence of horizontal scaling, multi-user isolation, or remote provider idempotency.
- If you disable outbound/live integrations, no real phone calls, SMS or GHL account writes occur.
