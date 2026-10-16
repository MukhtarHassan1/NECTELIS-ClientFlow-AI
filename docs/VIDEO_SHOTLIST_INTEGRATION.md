# 95-second video — real execution, truthful provider claims

Camera instruction: **record a human-executed browser demonstration at 1080p** after running local backend checks. Use synthetic data, hide all credentials, and keep the mock/offline badge visible at every provider screenshot. No prerecorded/faked output is distributed.

| Time | Action | Exact on-screen point |
|---|---|---|
| 0:00–0:12 | Show title + topology | "Configurable inquiry → contact → qualification → booking → audit." |
| 0:12–0:28 | Submit lead | Show local CRM contact ID, booked appointment and profile |
| 0:28–0:39 | Replay shield | Same request, no second booking |
| 0:39–0:55 | Go to **Show the mechanism** and click GHL booking | Five connector request operations: contacts/upsert, opportunities/upsert, free-slots, appointment, stage update |
| 0:55–1:08 | Click GHL 429 and lost booking response | "Bounded retries, and manual reconciliation when a write outcome is ambiguous." |
| 1:08–1:19 | Select Vapi or Twilio | Show only the provider appropriate for this listing; end-call mapping or signed SMS |
| 1:19–1:35 | Show boundary + export JSON | "Offline adapter contract evidence. Real provider validation requires authorized access." |

Three optional separate cuts: 30s CRM contact and stage mapping; 30s reliability (replay/429/timeout); 30s voice/message ingestion protocol. Avoid spreading unrelated capabilities across a short proposal.

**Verbal phrasing:** "This demonstration tests our GHL adapter's actual HTTP request logic against a controlled offline provider, so you can inspect what the integration will call. We have not connected a live GHL account in this footage."
