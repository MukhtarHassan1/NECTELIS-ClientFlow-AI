# Security, scopes and known limitations

**Never use this ZIP as an exposed production CRM.** It is an isolated proof system.

- Localhost default; HTTP-only local use; no reverse-proxy production hardening, rate-limiting, SOC2/ISO certification, privacy-compliance certification, field-level RBAC, encryption at rest or multi-tenant security boundaries.
- No customer secrets or actual client records; use synthetic `example.com` emails and fictional identities. Local demo state can be reset through the admin API.
- The browser UI is a demo admin console with no login. Setting `ADMIN_API_KEY` protects admin API routes but also disables unauthenticated browser dashboard state unless you add an authenticated local proxy. Avoid exposing port 8000 to the public internet.
- For external n8n Webhook, configure `WEBHOOK_API_KEY`, HTTPS, n8n-side authentication/signature verification, IP safeguards and proxy throttling before exposing a gateway.
- Mock notifications use a **local log by default**, with optional SMTP messages captured by **Mailpit on localhost/internal Docker network only**, and no real outside SMTP/SMS/Vapi/Twilio/GHL delivery. Follow-ups are internal **human-review queue items**, not sent follow-up campaigns.
- GHL contact/opportunity/calendar methods run together in an offline contract lab using MockTransport. They are **not** connected to a real sub-account, and the main application remains a local mock process. GHL APIs may change; test each endpoint on an authorized test location.
- `ghl_live_check.py` read-only by default; one synthetic test contact upsert requires explicit flags and an environment write approval. Never use production data or broad token scopes.
- Optional Ollama is real local inference and may consume significant machine memory. Rules continue to govern booking and validation even when inference is on; model output is not a source of truth.
- SQLite plus a Python lock is a single-process proof. Compose uses PostgreSQL for state but still one app worker. Multiple processes or real GHL calendars require distributed booking locks, reconciliation, retries with genuine `Retry-After`, durable work queues and availability holds.
- Slot check demonstrates timezone/business-hours/interval collision; no service capacity, holidays, staff schedules, blackout calendars, travel buffer, capacity pooling, rescheduling or daylight ambiguity policies.
- Existing contacts are matched by exact normalized email/phone within one synthetic client; real GHL uses location duplicate settings, native IDs, custom fields and owner policies. Both matching strategies require explicit client-specific tests.
- No native GHL workflow or snapshot has been exported. The included JSON is an **n8n workflow**.
- Validation errors are written to a **safe rejection audit** containing only field paths/type categories; no rejected PII is logged.
- Retention and consent requirements differ by jurisdiction; a general consent boolean is only a small part of a real communication compliance program.

**Truthful wording for proposals:** “We built and tested a reusable synthetic lead-to-booking engine with validation, contact upserts, duplicate-event protection, conflict checks, test-only notifications, auditing and reproducible failure scenarios. We also supply an unverified GHL adapter ready for authorized sandbox configuration.”

### Additional safety boundaries in the Signal Room release

- Reusing a processed event ID with changed content returns `409` based on a stored canonical request fingerprint; a legacy record without a fingerprint is not treated as a proven replay.
- Audit lookup can be fully scoped by `client_key`, `source` and `event_id`; ambiguous partial lookups return 409.
- A cross-origin browser request cannot reset the local synthetic data, but this is a local defensive measure **not a replacement** for a production authenticated admin control.
- Malformed unauthenticated webhook bodies do not create rejection audit records when `WEBHOOK_API_KEY` is configured.
- The refreshed browser UI is an operator tool for a local loopback sandbox and remains unsuitable for direct public exposure.
