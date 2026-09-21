# Element Pay Partner API — documentation

Self-contained Mintlify site for B2B partners (African fiat corridors: mobile money and bank), plus **agent-readable** OpenAPI and Markdown entrypoints.

**API runtime:** Element Pay aggregator — `https://sandbox.elementpay.net/api/v1/partner/*` (sandbox) and `https://api.elementpay.net/api/v1/partner/*` (production).

## Start here (agents + humans)

| File | Purpose |
|------|---------|
| [`llms.txt`](llms.txt) | Ordered list of canonical paths to read first |
| [`AGENTS.md`](AGENTS.md) / [`docs/agents.md`](docs/agents.md) | Auth, sandbox OnRamp happy path, webhooks, pitfalls |
| [`openapi.yaml`](openapi.yaml) | OpenAPI 3.1 — servers, `X-API-Key`, all `/partner/*` paths, webhook schemas |
| [`docs/integration-fiat-stablecoin.md`](docs/integration-fiat-stablecoin.md) | Local fiat ↔ USDC/USDT (OnRamp + OffRamp) |
| [`docs/KNOWN_GAPS.md`](docs/KNOWN_GAPS.md) | Conflicts and TODO stubs (no guessed behavior) |

Mintlify Try-it still uses [`api-reference/openapi.json`](api-reference/openapi.json) (kept in sync with root `openapi.json` / `openapi.yaml`).

## Local preview

```bash
npm i -g mint
cd partner-docs
mint dev
```

Opens at `http://localhost:3000`. **No other repo or scripts required.**

## What's in this repo

| File | Purpose |
|------|---------|
| `docs.json` | Mintlify config (Guides + API Reference tabs) |
| `openapi.yaml` / `openapi.json` | Partner API contract (agent + sync source) |
| `api-reference/openapi.json` | Same spec for Mintlify API Reference |
| `postman/` | Postman collection import |
| `*.mdx` | Guides, corridors, sandbox playbooks |
| `docs/*.md` | Agent / integrator Markdown (not Mintlify-only) |
| `favicon.svg`, `logo/` | Branding |

## OpenAPI

Lives **in this repo**. Prefer **`openapi.yaml`** for agents; JSON copies feed Mintlify.

- Edit or replace the spec when the partner API contract changes; keep YAML and both JSON files aligned.
- **Response examples** (200 / 400 / 422 / 502) are sourced from the aggregator OpenAPI export. After changing partner routes or `app/docs/responses/*` in `element-pay-aggregator`:

  ```bash
  # from element-pay-aggregator (recommended)
  python scripts/export_partner_openapi.py
  python scripts/sync_partner_openapi_to_docs.py
  # sync also runs scripts/enrich_openapi_for_mintlify.py (formatted guides + response examples)

  # or from partner-docs
  python scripts/sync-openapi-responses.py \
    ../element-pay-aggregator/app/docs/partner/openapi.snapshot.json
  python scripts/enrich_openapi_for_mintlify.py
  ```

  Then re-apply sandbox + production `servers` and the `webhooks` section (see `docs/KNOWN_GAPS.md` if automation drops them). Restart `mint dev` to see updated Try-it examples.

- Keep examples provider-neutral (no upstream PSP names in messages or error blobs).

`quote_id` prefixes like `yc_receive_*` are intentional contract identifiers.

## Deploy (Mintlify)

1. Connect **this** repo in [Mintlify](https://mintlify.com).
2. Docs directory = **repository root** (where `docs.json` is).
3. Push to `main` → Mintlify deploys. Independent of API server deploys.

## Partner handoff

- Hosted Mintlify URL
- Sandbox `is_test_…` API key + webhook secret (never commit real secrets — use placeholders like `YOUR_API_KEY`)
- Email template: `sandbox/onboarding.mdx`
