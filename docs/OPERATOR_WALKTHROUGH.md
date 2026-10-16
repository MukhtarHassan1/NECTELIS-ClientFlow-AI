# 3-minute operator guide — integration edition

1. Launch `RUN_WINDOWS.bat`; open `http://127.0.0.1:8000`.
2. Confirm top badge **LOCAL SANDBOX / MOCK CRM**; this is not connected to live GHL.
3. In **Test studio**, submit a sample lead or click **RUN ALL EIGHT**, then inspect events and audit.
4. Scroll to **Show the mechanism**. Click GHL **01 / Contact → pipeline → booked**.
5. Explain five visible API operations: contact upsert, opportunity upsert, free-slot check, appointment creation, stage upsert. Note the exact documented request paths and actual HTTP methods, but responses come from an offline emulator.
6. Run **HTTP 429**, **replay**, and **lost booking response** to show reliability decisions. Do not call the last case recovered automatically; the operator must reconcile it.
7. For a voice job only, click **Vapi**; for a messaging job, click **Twilio**. Neither placed calls or sent messages.
8. Click **EXPORT VERIFIED TRACE** then share a screenshot and short video with the correct "Offline contract lab" caption.
9. Use `docs/UPWORK_FIELD_KIT.md` to tailor the proof for a specific listing rather than editing engine code.
10. Run `python -m pytest -q` and keep test results available during interviews.

The external integration is NOT connected to live provider accounts. Always mention provider test access is the next verification milestone.

---

# Operator walkthrough — ClientFlow AI / The Signal Room

**Do not need GHL for the local proof.** This is an interaction-by-interaction guide for the updated interface.

## Run a live local scenario

1. Launch `RUN_WINDOWS.bat` and open `http://127.0.0.1:8000`.
2. Observe the top-right **LOCAL SANDBOX / MOCK CRM** indicator. It must not be changed to imply a live GHL account.
3. In **Incoming lead**, choose Northline Home Services or Horizon Realty. YAML-driven services and time-zone rules are loaded from the `/api/v1/profiles` endpoint.
4. Enter a name, synthetic `example.com` email, valid optional phone, supported service, and a future appointment in **your browser's local timezone**. Consent is a deliberate opt-in switch.
5. Click **PROCESS THIS INQUIRY**. A successful booking uses the local simulator; the identity, booking, and audit rows are persisted in SQLite.
6. Scroll to **Nothing disappears**: inspect returned JSON, per-event decision steps, and the persistent ledger. Selecting any row opens its client/source-scoped audit.

## Prove resilience

Use **RUN ALL EIGHT**, which executes each scenario against the API and checks its specific expectation. The tiles turn green only when a scenario meets its expected outcome. A non-green tile needs investigation, not a scripted success claim.

- Clean capture: new synthetic contact and booking.
- Replay shield: exact event repeated with no extra writes.
- Identity update: matching contact updated, not duplicated.
- Slot contention: a second requester cannot claim an already-occupied time.
- Rate-limit recovery: injected **mock** 429, bounded retry, then success.
- Auth interruption: injected **mock** 401, no blind retries.
- Consent gate: absent opt-in results in review; external messages remain disabled.
- Notify failure: injected internal provider failure is logged while the booking remains retained.

## Read and export evidence

- **Last execution:** machine-readable result, including exact status and connector mode.
- **What happened:** sanitized audit steps with attempts and safe error categories.
- **Execution ledger:** persistent recent events; filter by outcome and inspect.
- **COPY JSON:** copies the last selected JSON response.
- **EXPORT LOCAL EVIDENCE:** downloads a JSON report of the masked synthetic state and the browser session's scenario verdicts. These verdicts are not long-term CI records.

## Operator settings

The top-right gear opens **Room settings**. Density and reduced-motion preferences are local browser settings. **RESET SYNTHETIC DATA** removes the local mock database rows only and asks for confirmation. Real CRM actions and outbound sending cannot be enabled from this UI.

## Quick agency video outline (90 seconds)

1. 0–15s: the new Signal Room, visible **MOCK CRM** warning, five-stage map.
2. 15–33s: submit a synthetic lead; show created contact and booking in JSON.
3. 33–56s: run replay, slot contention, and mock 429; show scenario verdicts.
4. 56–76s: scroll to the audit and inspect a failure trace.
5. 76–90s: switch industry profile, explain next step for authorized GHL integration and what is not yet tested.

**Never describe the screen as a native GHL dashboard, a connected customer CRM, live AI inference without local Ollama, or production deployment.**
