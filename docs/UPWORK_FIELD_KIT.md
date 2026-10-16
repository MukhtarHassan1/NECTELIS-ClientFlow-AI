# NECTELIS — 10-minute proof tailoring for Upwork

## Lead with the client's operational risk

Don't start by saying “we know GHL and n8n.” Start with the failure the buyer actually worries about: missed lead, duplicate customer, overlapping booking, lost webhook, partial CRM update, insufficient authorization, or nonauditable follow-ups. Then select **one observed scenario** to substantiate your answer.

| Buyer request | Clip or screenshot to show | What you can assert | What must stay qualified |
|---|---|---|---|
| HighLevel automation | GHL contract booking and 401/429, local lead booking | Executable GHL HTTP request flows offline + local booking logic | No live HighLevel sub-account connected; no native snapshots |
| n8n workflow specialist | Local workflow trace + sanitized workflow JSON | Observable webhook-processing behaviors and importable export | n8n cloud workspace import/execution pending |
| AI receptionist | Vapi event normalization + consent/booking scenarios | Structured post-call intake adapter and lead pipeline logic | No actual Vapi calls or live tool-calls |
| SMS/Twilio | Signed SMS receipt/tamper check | Local classic-form signature verification and safe review policy | No SMS delivery, sender number or A2P verification |
| API developer | API docs, pytest, 429, post-write ambiguity | FastAPI, schema validation, scoped audit and API contract handling | Real API/account permissions not validated |
| Appointment system | Occupied slot, replay, availability, audit | Local deterministic conflict guard; provider contract simulator | Provider atomic hold/concurrency limitations remain |

Use the CLI to draft a scoped proof note:

```powershell
.\.venv\Scripts\python.exe -m scripts.make_proposal_brief --job ghl --industry "home services" --job-title "GoHighLevel workflow automation"
```

Output appears in `portfolio/generated/`. Choose `--job ghl`, `n8n`, `ai-voice`, `twilio`, `api`, or `backend`. This produces a **starting brief**, not a ready-to-send mass proposal. Read the real listing and replace the context; select supporting evidence truthfully. Do not paste all six proof assets into an Upwork proposal.

## The proof story in under 90 seconds

1. **Problem:** "Teams often lose context when a lead crosses forms, CRM, calendars and notifications."
2. **Solution:** Open Signal Room and submit a synthetic inquiry. Show contact ID, booked status, stage and audit.
3. **Reliability:** Replay the event; show no second booking. Show 429 recovery / 401 stop.
4. **Provider realism:** Open Connector Observatory, run GHL booking and inspect actual request methods/paths/versions; explain controlled responses mean no live GHL account.
5. **Integration flexibility:** Run one Vapi or Twilio inbound contract only when that is relevant to the buyer.
6. **Next step:** State exactly which provider permissions and account-specific IDs are necessary for real acceptance testing.

## Proposal snippet (credible, short)

> We developed ClientFlow AI to demonstrate the failure cases that matter in CRM/appointment automation: repeated webhooks, identity updates, booking conflicts, rate limits and unconfirmed downstream writes. In our local proof, the lead pipeline is fully executable with an event-by-event audit; our HighLevel contact/opportunity/calendar HTTP connector is exercised against an offline contract emulator and can be adapted for a permitted test sub-account. For your account, we'd begin with a scoped contact-upsert and calendar test, verify your stage IDs/duplicate settings, then deliver a traceable workflow and runbook.

Don't substitute "we have connected it to GHL" until there's live evidence. The stronger selling point is that the proof names its boundaries and shows failure-handling code.
