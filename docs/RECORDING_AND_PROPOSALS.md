# Video and Upwork adaptation plan

## 100-second master video: one uninterrupted real local run

| Time | Show on screen | Narration cue |
|---|---|---|
| 00:00–00:12 | The Signal Room title & LOCAL SANDBOX / MOCK CRM label | “A reusable proof of lead-to-booking engineering, with a synthetic CRM and calendar.” |
| 00:12–00:27 | Show the redesigned Signal Room and submit the inquiry | “An inbound request is validated and assigned a stable event ID.” |
| 00:27–00:42 | Result JSON, contact ID & booked status | “The engine upserts the contact and verifies the slot before recording the appointment.” |
| 00:42–00:58 | Run Replay shield | “A second delivery reuses the original result without duplicating a booking.” |
| 00:58–01:13 | Run Rate-limit recovery | “A simulated 429 followed by 200 shows bounded attempts and audit visibility.” |
| 01:13–01:27 | Switch profile to Real Estate | “Industry changes happen in YAML, without changing processing code.” |
| 01:27–01:40 | Tests + exact status labels | “These are local mock-mode tests; GHL live access and n8n deployment require separate validation.” |

Do not show terminal API keys, client contacts, private URLs or any actual client identifiers. Record 1080p, crop to legible output and leave the MOCK label visible. No video is included until a human records an actual run on their machine; do not upload staged/fictional client-case testimonials.

## Three reusable cuts

- **CRM / appointment (30s):** New event → created contact → booked appointment → final stage.
- **Reliability (30s):** Same event replay → no added booking → sample audit log.
- **Automation troubleshooting (30s):** 429 simulated → retry path → recovered outcome + notification failure without booking loss.

## Proposal-ready truthful excerpt

> We built ClientFlow AI, a configurable synthetic lead-to-booking proof that performs schema validation, CRM-style contact upserts, rule-based qualification, appointment conflict checks, audit trails and replay-safe processing. We tested both success and failure scenarios, including a 429→200 mock retry and duplicate webhook delivery. The code also includes a separate GoHighLevel API connector module, but we would validate it against your authorized sub-account before promising live behavior. For your project, I would start by checking your existing contact dedupe policy, pipeline IDs and calendar availability rules.

Use the team's accurate attribution and only the relevant screenshots/clip for each job. Never imply prior client engagement from these synthetic demonstrations.


**New visual assets:** `evidence/clientflow-cover-1440x930.png` (shareable UI cover), `evidence/clientflow-signal-room-overview.png` and `evidence/clientflow-signal-room-tested.png` (actual execution), and `docs/OPERATOR_WALKTHROUGH.md` (updated narration). Only a human-recorded clip is evidence of real native browser interaction on the target computer.
