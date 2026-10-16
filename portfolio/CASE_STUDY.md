# ClientFlow AI | NECTELIS Engineering Proof

**Category:** GHL-style lead management, API integration, workflow automation, booking reliability  
**Environment:** FastAPI, SQLAlchemy, SQLite/PostgreSQL-ready, n8n export, two YAML profiles  
**Verification:** Local synthetic tests only | **GHL connector:** full offline HTTP sequence executed and traceable; not integrated live

## Operational problem

In small-business intake automations, duplicate webhook deliveries, unstable contact matching, calendar conflicts and failed notifications can lose inquiries or create double bookings. A simple form-to-email workflow conceals those failures.

## What we built

ClientFlow AI accepts structured synthetic inquiries, validates service/consent/identity, consults a persistent replay ledger, upserts a contact in its mock CRM, assigns a configurable pipeline stage, checks a requested calendar slot and records a booking or a review reason. It leaves an event-linked audit and internal follow-up item. The original Signal Room interface lets reviewers run an eight-scenario reliability suite, inspect profile/source-scoped event trails and export sanitized local results in a few clicks.

## Tested engineering behaviors (mock/synthetic environment)

- An accepted lead creates one contact and one booking.
- A replayed webhook returns the original result without a second booking or notification.
- Updating an existing lead preserves its contact identity.
- Two simultaneous bookings for the same slot do not both succeed in the single-process demo.
- A simulated 429 recovers with bounded retry attempts; simulated 401 stops writes.
- A simulated notification failure does not undo the booking.
- A simulated post-write calendar timeout recovers its original booking rather than creating a second.
- Switching the YAML profile changes the supported services and pipeline stages.

## Why clients should care

The technical proof is about predictable system behavior under stress, not a flashy mock user interface. It gives an integration specialist a repeatable way to discuss deduplication, scheduling safeguards, observable failures and domain-specific configuration before connecting a real CRM.

## The new Connector Observatory

The client can click a complete GHL-style sequence: contact upsert → opportunity upsert → calendar free-slot lookup → appointment creation → booked-stage update. Each stage exposes sanitized **actual HTTP request fields, API version, status and outcome** from the local mocked provider. Additional cases test replay, changed-event conflict, 429 backoff, failed authorization, no-slot outcomes and a lost booking response that requires manual reconciliation instead of blind retries. Vapi and Twilio show structured end-call input and signed inbound SMS contracts respectively. These operations are real software executions against **local emulator responses**, not screenshots of a real HighLevel account.

## Limits and next verification milestone

This is **not** a live GHL deployment or proof of native snapshots, external messaging, AI phone conversations or enterprise-scale availability. The next milestone is an **authorized GHL sandbox** with one synthetic contact, one explicit calendar booking and native pipeline validation. Screenshots and video should say MOCK MODE unless those tests actually pass in a real sub-account.

## Verification in the redesigned edition

**66 backend and provider-contract checks passed**, the ten provider-contract browser scenarios were validated (8 GHL + Vapi + Twilio), and the eight original local CRM scenarios were verified using headless Chromium running the actual UI logic and local FastAPI operations through an HTTP bridge. The visual evidence and test records are included in `evidence/`; no real GHL service calls were used. Regression checks now reject changed-body event replay, isolate audit lookups by source/profile, reject past booking times, prevent cross-origin local reset, and preserve confirmed future bookings after contact updates.

**Portfolio screenshots:** `evidence/connector-observatory-desktop.png`, `evidence/clientflow-signal-room-tested.png`. Clearly caption them *Synthetic mock environment — not a connected GHL account*.
