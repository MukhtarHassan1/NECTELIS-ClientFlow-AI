# NECTELIS ClientFlow — client presentation

**Duration:** 100–130 seconds. Record with a 1080p screen capture, only synthetic data. Do not open secrets, personal inboxes, actual client accounts or terminal environment files.

0–12s — **Business problem.** “We connect incoming customer conversations to contacts, appointments and operational follow-through. This is our configurable lead operations engine.” Show the Signal Room topology.

12–35s — **Reviewer input.** Open **02 Integrations → Run the integration**, select **Vapi → Voice report → CRM → appointment**. Ask the viewer to give you a random reference. Edit the reference, run. Highlight `contact_id`, `appointment_id`, and the log. “The Vapi report is normalized, the backend qualifies and books into a real persistent local database.”

35–55s — **Replay.** Select Vapi → repeated call. Explain same `call.id` maps to one booking. Show replay check and SQL-backed event record in Evidence.

55–80s — **Twilio end-to-end boundary.** Select Twilio → inbound SMS to outbound REST to delivery. Show signature accepted, replay suppressed, HTTP POST against emulator, callback signed, final delivery status. Then choose “delivery failed” and show correctly retained failure state.

80–106s — **GoHighLevel API methods.** Run GHL contact → pipeline → appointment, and optionally 429 recovery. Inspect the real request method/path and outcome. State that adapter methods execute against a controlled GHL HTTP emulator. Don't describe this as a live account connection.

106–120s — **Engineering evidence.** Run `RUN_TESTS_WINDOWS.bat` or display the generated isolated matrix/test report. Offer the sanitized JSON execution receipt.

### Strong presentation sentence

> “We’ve implemented the intake and integration logic and verified it with executable backend, database and provider-contract tests. For your own platform accounts, we configure the credentials, calendars/phone/webhooks and permissions, then perform acceptance tests on the live provider before go-live.”

### Don't claim

- “This is live GHL” (without a real account test).
- “Calls and SMS were sent” (offline workbench does neither).
- “Paste any API key and it is production-ready” (not true for provider setup, permissions, compliance or public webhooks).
- “Native GHL snapshots, Vapi synchronous tools or Twilio SIP routing are implemented” (not part of this edition).

### Reuse

For GHL jobs show CRM/booking and safe retries. For AI-agent jobs show Vapi intake, typed data and a booking. For Twilio jobs show signing, REST and callback failures. For n8n jobs show the workflow JSON only after importing and executing it in your own workspace. Retain one underlying product; customize talk track and configuration, not unsupported claims.
