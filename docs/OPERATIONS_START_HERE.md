# ClientFlow AI · Operations Edition

**Start here on Windows.** This archive is a full source project, not a screenshot or a single HTML file.

## Launch locally

1. Extract this ZIP into its **own new folder**. Do not merge with older ClientFlow editions.
2. Close any old ClientFlow Command Prompt windows so port `8000` is free.
3. Open `NECTELIS_ClientFlow_AI` and double-click `RUN_WINDOWS.bat`.
4. Open **http://127.0.0.1:8000**. Hard-refresh with Ctrl+Shift+R if necessary.
5. Click top navigation **02 Integrations**, find **Run the integration.**
6. Set provider, path, synthetic name and a random run reference; click **EXECUTE WORKFLOW**.
7. Inspect the actual checks, request trace, stored contact/booking/message outcome, and export the receipt.
8. Test Vapi → CRM → appointment; Twilio inbound signature → outbound REST → delivery status; and GHL contact → pipeline → booking.

**No account or payment is needed for these local tests.** The visible sandbox indicator stays accurate.

## Test independently

After startup installed Python packages, double-click `RUN_TESTS_WINDOWS.bat`. It runs pytest and then an isolated 12-scenario provider exercise with a separate temporary SQLite DB. A machine-readable report is written to `evidence/operations-matrix-local.json`.

Or type this in a terminal opened in the project directory:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m scripts.verify_operations --output evidence\operations-matrix-local.json
```

## Recording

Read `docs/CLIENT_DEMO_STORYBOARD.md`. Show a fresh reviewer-chosen input, a successful Vapi booking with real local SQLite persistence, a Twilio signed delivery receipt, then a GHL HTTP trace. **When discussing external vendors, say “provider adapters implemented and tested offline; authorized live validation pending.”**

## Activating actual vendors

Read `docs/PROVIDER_ACTIVATION.md` before buying a subscription or setting any token. A provider secret alone is not sufficient: public HTTPS URLs, rights, webhook settings, account IDs, calendar availability, messaging sender approval and consent are relevant. No provider can be declared live-tested by this package.

## Security

No secrets belong in a browser form, demo video, public repository, or generated evidence. The demo server listens on `127.0.0.1` by default. It is not an internet-hardened multi-tenant deployment.
