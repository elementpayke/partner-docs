---
title: "Local fiat ↔ USDC/USDT"
---

# Integration guide — local fiat ↔ stablecoin

One corridor pattern for both directions. Only a few quote fields change per market and asset. Based on existing repo docs / OpenAPI — see [`KNOWN_GAPS.md`](KNOWN_GAPS.md) for unknowns.

**Product:** corridor **quote → accept** (`POST /partner/orders/quote` → `POST /partner/orders/{quote_id}/accept` → `order.settled`).  
**Not this guide:** ledger `…/conversions` (fiat↔fiat banking) — see `customers/conversions.mdx`.

## Directions (same endpoints)

| Direction | `order_type` | Customer pays | Customer receives | Amount field |
|-----------|--------------|---------------|-------------------|--------------|
| **OnRamp** (local → crypto) | `OnRamp` | Local fiat (momo/bank) | USDC or USDT to `wallet_address` | `local_amount` |
| **OffRamp** (crypto → local) | `OffRamp` | Stablecoin (prod: on-chain; sandbox: name trigger) | Fiat to momo/bank | `crypto_amount` |

Always discover `network_id` with the **same** `country` + `order_type` as the quote (`GET /partner/catalog` or `GET /partner/payment-methods`). Provider lists differ by direction.

## What changes between corridors

| Field | How to set it |
|-------|----------------|
| `country` | ISO country from your catalog (e.g. `KE`, `NG`, `UG`) |
| `currency` | ISO 4217 local fiat (e.g. `KES`, `NGN`, `UGX`) |
| `order_type` | `OnRamp` or `OffRamp` |
| Amount | OnRamp: `local_amount` · OffRamp: `crypto_amount` |
| `asset` | See stablecoin table below |
| `payment_method` | `mobile_money` (+ `phone_number`) or `bank` (+ `account_number` / `account_name`) + `network_id` |
| `wallet_address` | **OnRamp required** (receive crypto) |
| `refund_address` | **OffRamp required** |
| `customer_id` | Approved vault `pcus_*` (preferred) |

Field hints: `GET /partner/order-requirements?country=…&currency=…&order_type=…`. Playbooks: `corridors/kenya.mdx`, `corridors/nigeria.mdx`, `corridors/uganda.mdx`, `corridors/overview.mdx`.

## Stablecoin assets (documented)

| Use | `asset.currency` | `asset.network` | `asset.token` |
|-----|------------------|-----------------|---------------|
| **Default (recommended)** | `USDC` | `BASE` | `0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913` |
| Alternate | `USDT` | `POLYGON` | `0xc2132d05d31c914a87c6611c10748aeb04b58e8f` |

Same addresses on sandbox and production. Prefer Base USDC unless QA confirms USDT for your corridor (`corridors/overview.mdx`). KE OffRamp sandbox samples often use Polygon USDT.

## How the rate is quoted and locked

| Stage | Endpoint | Binding? | What you get |
|-------|----------|----------|--------------|
| UI ticker (optional) | `GET /partner/rates/indicative?fiat=KES,NGN,…` | **No** | Corridor fiat vs USD for display |
| Order quote | `POST /partner/orders/quote` | **Yes** until `expires_at` | Locked pricing in `data.amounts` |
| Accept | `POST /partner/orders/{quote_id}/accept` | Consumes quote | Creates `order_id`; rail starts |
| Settlement | Webhook `order.settled` (or order GET) | Final amounts | `amount_crypto`, `amount_fiat`, `exchange_rate`, … |

### Quote fields to show / store

| Field | Meaning |
|-------|---------|
| `data.quote_id` | Pass to accept (e.g. `yc_receive_…`) |
| `data.expires_at` | Re-quote if past; accept returns **410** when expired |
| `data.amounts.rate` | Locked FX for this quote |
| `data.amounts.user_pays` | `{ amount, currency }` (fiat or crypto depending on direction) |
| `data.amounts.user_receives` | `{ amount, currency, network? }` |
| `data.amounts.fees` | e.g. `service_fee_local`, `service_fee_usd` |

**TTL in seconds:** not a fixed published constant — honor `expires_at`. TODO: [`KNOWN_GAPS.md`](KNOWN_GAPS.md).

Indicative rates are **not** binding and **not** ledger-pair FX.

## Worked examples (same shape)

### OnRamp — local amount → USDC (KE momo sandbox)

```bash
export BASE="https://sandbox.elementpay.net/api/v1"
export API_KEY="is_test_YOUR_API_KEY"
export CUSTOMER_ID="pcus_YOUR_APPROVED_CUSTOMER"
# network_id from: GET $BASE/partner/catalog?country=KE&order_type=OnRamp

curl -sS -X POST "$BASE/partner/orders/quote" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{
    "order_type": "OnRamp",
    "currency": "KES",
    "country": "KE",
    "local_amount": 800,
    "customer_id": "'"$CUSTOMER_ID"'",
    "asset": {
      "token": "0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913",
      "currency": "USDC",
      "network": "BASE"
    },
    "payment_method": {
      "type": "mobile_money",
      "phone_number": "+2541111111111",
      "network_id": "REPLACE_FROM_CATALOG"
    },
    "wallet_address": "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe"
  }'
```

Swap `country` / `currency` / phone / `network_id` for other OnRamp markets (e.g. NG bank + BVN — see `corridors/nigeria.mdx`). Success/failure sandbox identities: `sandbox/success-failure.mdx`.

### OffRamp — USDT/USDC → local fiat (same accept path)

Checklist from `orders/quote-and-accept.mdx`:

| Field | OffRamp |
|-------|---------|
| `order_type` | `OffRamp` |
| Amount | `crypto_amount` |
| `asset` | Often Polygon USDT on KE sandbox; use Base USDC when enabled for your key |
| `payment_method` | Payout momo/bank + catalog `network_id` for **OffRamp** |
| `refund_address` | Required |
| `wallet_address` | Omit |

**Sandbox:** do not settle by sending testnet crypto — include `Successful` in retail `customer.name` (or institution `business_name`) so the crypto leg auto-credits (`sandbox/success-failure.mdx`, `corridors/kenya.mdx`).  
**Production:** after accept, customer sends the exact crypto amount to `payment_instructions.crypto_deposit` before that address’s `expires_at`. Deposit address is **per order** — do not reuse.

Accept is identical for both directions:

```bash
sleep 2
curl -sS -X POST "$BASE/partner/orders/$QUOTE_ID/accept" \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{}'
```

## What ID to store for reconciliation

| ID | When available | Use |
|----|----------------|-----|
| `customer_id` (`pcus_*`) | After vault create | End-user mapping |
| `partner_customer_ref` | If set on create | Your customer key |
| `quote_id` | Quote response | Accept + support |
| `order_id` (`YC-…`) | Accept / webhooks | **Primary settlement key** |
| `X-Webhook-Id` | Each webhook | Dedupe |
| `settlement_transaction_hash` | Settled webhook when present | Rail / chain ref |

Prefer `order_id` as the ledger journal external reference.

## When funds are final

| Signal | Safe to update ledger? |
|--------|-------------------------|
| Quote created | No — pricing only |
| Accept `200` / `order.processing` | No — pending |
| Webhook **`order.settled`** | **Yes** — source of truth |
| Webhook `order.failed` | No — surface failure |
| Webhook `order.refunded` | Reverse / adjust per your rules |

Backup poll: `GET /partner/orders/{order_id}`.

| Direction | Typical ledger effect on `order.settled` |
|-----------|------------------------------------------|
| OnRamp | **Credit** stablecoin (from `amount_crypto`) |
| OffRamp | **Debit** stablecoin / confirm fiat payout (from settled amounts) |

## Fees and currency codes

- Fiat: ISO 4217 from catalog (`KES`, `NGN`, …).
- Crypto: `USDC`/`USDT` as in the asset table.
- Fee fields on quote: `amounts.fees.service_fee_local`, `amounts.fees.service_fee_usd`.
- Static fee schedule / BPS: **not** in this repo — use per-quote `fees`. TODO: [`KNOWN_GAPS.md`](KNOWN_GAPS.md).

## Stablecoin minor-unit ledgers

API examples return **decimal** crypto amounts (e.g. `5.95`), not integer minor units.

Integrator convention (your system):

```text
ledger_amount_minor = round(amount_crypto * 1_000_000)   # USDC/USDT typically 6 decimals
```

Display local fiat from `amount_fiat` / `user_pays` (or non-binding indicative rates for marketing only). Never replace the locked quote rate for checkout confirmation. Credit/debit from the **settled** webhook amounts, not a re-fetched indicative rate.

## Minimal settled handler sketch

```python
# Pseudocode — verify HMAC before this (webhooks.mdx / docs/agents.md)
def handle_order_settled(headers, body: dict):
    assert headers["X-Webhook-Event"] == "order.settled"
    if already_processed(headers["X-Webhook-Id"]):
        return 200
    order_id = body["order_id"]
    crypto = body["amount_crypto"]
    fiat = body.get("amount_fiat")
    order_type = body.get("order_type")  # OnRamp | OffRamp when present
    # Prefer asset currency/network stored with order_id at quote/accept time
    apply_ledger(
        external_ref=order_id,
        order_type=order_type,
        amount_minor=int(round(crypto * 1_000_000)),
        metadata={"fiat_currency": body.get("currency"), "amount_fiat": fiat},
    )
    mark_processed(headers["X-Webhook-Id"])
    return 200
```

Store the quote’s `asset.currency` / `network` with `order_id` at accept time — settled webhook examples emphasize fiat `currency` and `amount_crypto`, not always a full asset object ([`KNOWN_GAPS.md`](KNOWN_GAPS.md) if you need a richer schema).

## Related OpenAPI operations

- `GET /partner/catalog` · `GET /partner/payment-methods` · `GET /partner/order-requirements`
- `POST /partner/orders/quote` · `POST /partner/orders/{quote_id}/accept` · `GET /partner/orders/{order_id}`
- `GET /partner/rates/indicative`
- `webhooks.partnerEvent` (outbound)

Agent path: [`agents.md`](agents.md).
