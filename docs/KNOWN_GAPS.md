---
title: "Known gaps"
---

# Known gaps and conflicts

This file records **conflicts inside this repo** and **TODOs** where behavior is not documented. Do **not** invent API fields to fill these — confirm with Element Pay (`compliance@elementpay.net`) before shipping production assumptions.

## Conflicts (prefer code/examples in-repo)

| Topic | Conflict | Prefer |
|-------|----------|--------|
| Auth schemes in OpenAPI | Spec also lists `JWTBearer` / `HTTPBearer` | **`X-API-Key` only** for `/partner/*` (see `authentication.mdx`; schemes annotated as unused) |
| Base URLs in tooling | Older `docs.json` / Mintlify `api.baseUrl` was sandbox-only | MDX + `openapi.yaml` **servers**: sandbox + production |
| README deploy path | README mentioned `mint.json` | Repo uses **`docs.json`** |
| `GET /partner/banks` | OpenAPI: bank/network options; guides: not for NG retail / momo / primary KE bank discovery | Prefer **`catalog` / `payment-methods`** for African retail; follow corridor pages |
| Inline `customer` on quote | Still in sandbox/Postman examples | **Deprecated** — new work uses vault `customer_id` (`orders/quote-and-accept.mdx`) |
| Card APIs | Documented in `customers/cards.mdx` + route cheat sheet | **Not** in `openapi.yaml` paths — treat as guide-only until exported |

## TODOs (missing from repo — stub only)

| Gap | Impact | Stub |
|-----|--------|------|
| Exact quote TTL in seconds | Agents must parse `expires_at` | **TODO:** publish nominal TTL if product has a fixed window |
| Static fee schedule / BPS | Fee table not in docs | **TODO:** use per-quote `amounts.fees`; request schedule from EP if needed |
| Account webhook body schemas | `account.*` events listed; no full JSON examples in `webhooks.mdx` | **TODO:** add examples; OpenAPI webhook `oneOf` notes this |
| Card charge OpenAPI | Cards guide without OpenAPI | **TODO:** export card paths into OpenAPI when stable |
| Production IP allowlisting details | Mentioned in onboarding checklist | **TODO:** document if required for your key |
| USDC minor-unit API field | API returns decimals | Integrators convert ×10⁶ locally — **not** an API contract field |
| Hosted Mintlify public URL | README placeholder | Set in partner handoff |

## Dual products easy to confuse

| Product | Paths | Direction |
|---------|-------|-----------|
| Corridor ramp | `/partner/orders/quote`, `…/accept` | Fiat ↔ crypto (e.g. local fiat → USDC) |
| Ledger conversion | `…/accounts/{id}/conversions/preview` | Fiat ↔ fiat on **same** customer banking accounts |
| Indicative rates | `/partner/rates/indicative` | Non-binding UI ticker |

## Source preference

1. `openapi.yaml` / `openapi.json` path + response examples  
2. MDX guides with copy-paste curls (`quickstart`, `orders/quote-and-accept`, `webhooks`)  
3. Postman collection  
4. This gaps file when sources disagree
