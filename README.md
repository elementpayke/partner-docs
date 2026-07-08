# Element Pay Partner API — documentation

Self-contained Mintlify site for B2B partners (African fiat corridors: mobile money and bank).

**API runtime:** Element Pay aggregator — `https://sandbox.elementpay.net/api/v1/partner/*` (sandbox) and `https://api.elementpay.net/api/v1/partner/*` (production).

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
| `api-reference/openapi.json` | OpenAPI spec — auto-generates Try-it endpoint pages |
| `postman/` | Postman collection import |
| `*.mdx` | Guides, corridors, sandbox playbooks |
| `favicon.svg`, `logo/` | Branding (from edocs) |

## `openapi.json`

Lives **in this repo only**. Mintlify reads it for the API Reference tab.

- Edit or replace `openapi.json` here when the partner API contract changes.
- **Response examples** (200 / 400 / 422 / 502) are sourced from the aggregator OpenAPI export. After changing partner routes or `app/docs/responses/*` in `element-pay-aggregator`:

  ```bash
  # from element-pay-aggregator (recommended)
  python scripts/export_partner_openapi.py
  python scripts/sync_partner_openapi_to_docs.py
  # sync also runs scripts/enrich_openapi_for_mintlify.py (formatted guides + response examples)

  # or from partner-docs
  python scripts/sync-openapi-responses.py \\
    ../element-pay-aggregator/app/docs/partner/openapi.snapshot.json
  python scripts/enrich_openapi_for_mintlify.py
  ```

  Restart `mint dev` to see updated Try-it examples.

- Keep examples provider-neutral (no upstream PSP names in messages or error blobs).

`quote_id` prefixes like `yc_receive_*` are intentional contract identifiers.

## Deploy (Mintlify)

1. Connect **this** repo in [Mintlify](https://mintlify.com).
2. Docs directory = **repository root** (where `mint.json` is).
3. Push to `main` → Mintlify deploys. Independent of API server deploys.

## Partner handoff

- Hosted Mintlify URL
- Sandbox `is_test_…` API key + webhook secret
- Email template: `sandbox/onboarding.mdx`
