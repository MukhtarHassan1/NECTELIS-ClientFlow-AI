# Team handoff / access checklist

| Responsibility | Package already supplies | Team member does once |
|---|---|---|
| Integration / backend | FastAPI, models, tests, mock engine, GHL HTTP contract module | Verify authorized GHL scopes, location, calendar & pipeline IDs; capture one real nonproduction test |
| Automation / n8n | Sanitized workflow JSON with booked/review/error routes | Import into your account, configure backend URL securely and test a real execution |
| QA & delivery | Browser proof lab, scenarios, test evidence, case study, recording guide | Run tests on own PC, inspect screenshot/recording accuracy, capture 100-sec video |

## Release labels to use

- **Built & locally tested:** Mock CRM/booking event loop, contact matching, validation, pipelines, audit, failure injection and test-only notification behavior.
- **Contract tested offline:** GHL contact upsert, availability, appointment request formats with fake transport. Not connected to actual GHL.
- **Generated, import pending:** n8n workflow JSON.
- **Implemented, environment setup pending:** Ollama advisory mode and local Mailpit capture (only if local components installed).
- **Not implemented:** Native GHL snapshots, full GHL live orchestration, production outbound SMS/voice, customer-level security/consent review, production hosting.

If the target GoHighLevel job is still open, publish only evidence of verified mock execution and accurately state which vendor-specific steps you would validate in the client account. Do not wait for every optional connector merely to attach a truthful relevant proof.
