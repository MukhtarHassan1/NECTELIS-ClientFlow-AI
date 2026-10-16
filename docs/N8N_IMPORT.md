# n8n workflow: import and run safely

Artifact: `n8n/ClientFlow_AI_Lead_Orchestration.json` (synthetic, credentials removed).

## What the nodes do

1. **Receive Lead** — accepts one JSON payload on a webhook. No production contact data.
2. **Forward to Validated API** — POSTs the webhook body to the FastAPI ledger/processing engine. This is where durable contact and booking logic lives, not a hidden n8n code blob.
3. **Was Appointment Booked?** — explicit routing based on tested API result.
4. **Return Confirmed Booking** / **Return Review / Failure Status** — return the audit-bearing JSON.
5. **Return Safe API Error** — branch for transport failures without leaking raw upstream responses.

## Import procedure

- In n8n, use **Import from File**. Keep **Inactive** while configuring. It does not contain private tokens or webhook URLs.
- The example HTTP node references `CLIENTFLOW_API_URL` and `CLIENTFLOW_WEBHOOK_API_KEY` through `$env`. n8n Cloud may restrict custom environment variables; when restricted, manually set the backend URL and use a credential/header-auth entry **inside n8n** instead of writing a secret in the shared JSON.
- If n8n runs in Docker and FastAPI runs on host Windows/macOS, `host.docker.internal:8000` can work in supported setups. For n8n Cloud, localhost is not reachable: use a securely authenticated HTTPS staging endpoint, or a self-hosted n8n instance on the same private Docker network. **Do not expose an unauthenticated local demo.**
- Send `fixtures/new-lead.json` with your webhook test URL from an authorized environment. Review the n8n execution and the FastAPI `/api/v1/audit/<event_id>` timeline.
- Confirm that the webhook, conditional outputs and n8n node versions work with your installed n8n release; workflow JSON was generated locally, not imported/tested in a connected n8n instance.

**Capability label:** “importable n8n orchestration file (runtime import not independently verified).”
