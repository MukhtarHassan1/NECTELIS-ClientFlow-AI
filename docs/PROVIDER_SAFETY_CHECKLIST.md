# Provider connection safety gate (human approval required)

**Default:** local mock CRM; no paid APIs, no live voice, no outbound messaging, no customer records, no provider webhooks.

Before enabling any external webhook or GHL test write:

- Obtain explicit agency/client permission, including data handling and test scope.
- Use a dedicated, disposable **authorized** test account and synthetic contact identities (`example.com`).
- Confirm location/account IDs, calendar, pipeline/stage mappings, timezone, duplicate-contact rules and per-platform entitlements.
- Keep secrets in `.env` or your credential vault; never in GitHub, videos, screenshots, or ChatGPT messages.
- Bind HTTP services securely with TLS and access restrictions if a webhook must be exposed. Local `127.0.0.1` URLs are not accessible directly to external providers.
- Enable provider ingress (`ENABLE_PROVIDER_WEBHOOKS=true`) only when token/signature configuration, origin URL and authentication are valid. Leave disabled for portfolio recordings.
- This release has **no general-purpose live provider orchestration toggle**. The existing GHL smoke-test CLI is read-only by default, with a separately acknowledged synthetic-contact write option. Connecting a complete live GHL account still requires external integration QA and safeguards.
- Do not use production client PII or unsolicited SMS/calls; respect consent, quiet hours, account ownership and opt-out requirements.
- When an external appointment POST times out after possible creation, quarantine and reconcile using provider records before retrying; never promise exactly-once writes across arbitrary APIs.
- Confirm cleanup of all synthetic contacts/appointments/pipelines after testing. Record pass/fail and provider IDs only in private evidence.

For production-grade Twilio validation use the maintained Twilio RequestValidator SDK and verify the externally visible URL through your reverse proxy. For Vapi use an organization-configured server credential, not a transient secret entered into a prompt. Test tool-calls as a separate protocol if needed; this release implements only end-call-report intake.
