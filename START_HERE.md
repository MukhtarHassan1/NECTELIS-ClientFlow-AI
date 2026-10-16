# START HERE — CLIENTFLOW AI / THE SIGNAL ROOM

**You now have a runnable synthetic lead-to-booking proof plus an executable offline provider-contract lab**. No GoHighLevel or Vapi/Twilio account is required for the demo.

## 1. Fastest way to run

On Windows 11, **double-click `RUN_WINDOWS.bat`** inside the extracted folder. It creates the virtual environment, installs requirements and starts the local server automatically. The first run needs internet access to install Python packages. Alternatively, in PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn clientflow.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** → click **RUN ALL EIGHT** → inspect the eight verdicts → open an event in **Execution ledger**. Inspect the actual JSON results and the audit timeline.

## 2. Let clients choose the test — strongest no-card proof

Scroll to **02 Proof challenge + connectors**, and find **Your input. Our backend. Your verdict.**
Ask the client for a random phrase and synthetic name. Press **EXECUTE INDEPENDENT CHECK**. The system creates a fresh event, verifies a real SQLite write, replays the request, and rejects a mutated replay. Expect **7/7 BACKEND VERIFIED** only when the real HTTP and database assertions pass. Export the actual evidence and open the JSON.

For verification outside any HTML page, open another terminal and run:

```powershell
.\.venv\Scripts\python.exe -m scripts.independent_proof
```

This creates isolated new SQLite records and asserts the results. For the exact review/recording sequence, read **`docs/REVIEWER_CHALLENGE.md`**. This is the recommended centerpiece of the agency video because the reviewer controls the input and can check outputs independently.

## 2. Test the actual HighLevel connector *code* — for free

Scroll to **Show the mechanism / Connector Observatory** and click **01 / Contact → pipeline → booked**. You will see five actual HighLevel-shaped HTTP requests made by the connector **against an in-memory emulator**. Then run 429, replay, 401 and lost-response cases; the terminal server stays local and never contacts GHL. Click Vapi and Twilio to demonstrate the two inbound adapters. Export the JSON evidence. This is not a real GHL deployment and must not be narrated as one.

## 4. Run engineering checks

Open a second terminal inside this folder:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The file `evidence/pytest-results.txt` records the build-environment test outcome; the command above verifies your machine independently. Also run:

```powershell
.\.venv\Scripts\python.exe -m scripts.export_connector_evidence
.\.venv\Scripts\python.exe -m scripts.make_proposal_brief --job ghl --industry "home services" --job-title "GoHighLevel automation specialist"
```

Use `docs/VIDEO_SHOTLIST_INTEGRATION.md` to record the best focused clip; `docs/UPWORK_FIELD_KIT.md` selects which evidence belongs in which proposal.

## 5. Optional human steps (required for real GHL/n8n proof)

- **n8n**: Read `docs/N8N_IMPORT.md`, import `n8n/ClientFlow_AI_Lead_Orchestration.json` in your workspace, configure secure API access, and verify with an actual n8n execution.
- **GHL**: Request permission for a dedicated sub-account, set private tokens **locally** and follow `docs/GHL_ACCESS_AND_VALIDATION.md`. The separate connector module exists but is not automatically activated or represented as tested.
- **True AI inference**: Install Ollama and a suitable local model, set `OLLAMA_MODEL`, re-run the demo and record evidence. Until then the assistant is **deterministic, AI-ready**—not an actual running LLM.
- **Agency proof video**: Record a live local run using `docs/RECORDING_AND_PROPOSALS.md`. Don't claim that a clip or real GHL integration exists until you create/test it.
- **Real notifications**: With Docker available, Mailpit captures internal test emails at `http://127.0.0.1:8025`. Local Python mode logs them without sending; no paid SMS/email accounts required for the core.

## 6. Exact delivery status

**Delivered and verified:** reviewer-controlled backend challenge (7 live browser assertions against actual FastAPI and SQLite via a test bridge), independent command-line proof, offline Connector Observatory (10 browser-executed provider scenarios using local API, without external provider calls); 70 automated backend and contract checks; FastAPI engine; two YAML profiles; new Signal Room UI interactions (headless Chromium + actual local API through a build-environment HTTP bridge); persistent mock CRM/booking/replay ledger; follow-up queue; consent safeguards; local audit; simulated fault handling; tests; provider-request-shape tests; docs; case study; n8n export; screenshots.

**Requires your authorized environment:** real GHL data operations and native GHL workflows; importing/running n8n; genuine locally installed LLM inference; a video recorded on your computer; full real provider failure/recovery verification.

The agency can demonstrate this mock proof today, clearly labeled. It should not market the unverified integrations as production work.

## 7. What changed since the first ZIP

Read `docs/SIGNAL_ROOM_UPGRADE.md` for the full list of UI decisions, fixed loopholes, regression cases, browser-verification method and limitations. See `docs/OPERATOR_WALKTHROUGH.md` for the agency demonstration sequence. The old screenshots have been replaced by screenshots of the redesigned interface.
