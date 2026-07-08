#!/usr/bin/env python3
"""
Mintlify-specific OpenAPI enrichment for partner-docs.

Run after sync-openapi-responses (or sync_partner_openapi_to_docs):

- Injects singular ``example`` on each response (Mintlify Try-it panels use this).
- Adds ``x-mint.content`` blocks with formatted endpoint guides.
- Drops empty FastAPI-only 422 stubs when a documented partner error exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    REPO_ROOT / "api-reference" / "openapi.json",
    REPO_ROOT / "openapi.json",
)

# Mintlify MDX rendered above auto-generated params/responses (x-mint extension).
ENDPOINT_GUIDES: dict[tuple[str, str], str] = {
    ("get", "/partner/corridors"): """\
Indicative catalog for partner checkout UI.

### African markets (`african_markets`)
Local fiat corridors: **country**, **currency**, and **onramp** / **offramp** flags.

Optional filters: `country`, `currency`, `order_type` (`OnRamp` | `OffRamp`).

### International bank (`international_bank`)
EUR/USD bank transfer **payin** — **currency only** (do not pass ISO country).

<Note>
Binding eligibility is confirmed at [`POST /partner/orders/quote`](/partner/orders/quote).
</Note>
""",
    ("get", "/partner/catalog"): """\
Single indicative catalog for partner checkout: per-country onramp/offramp, `mobile_money` and `bank` buckets with live provider lists, optional `rails` for international payout markets, and `international_bank` for EUR/USD payin.

### Provider IDs
`providers[].id` is the opaque institution UUID to send as `payment_method.network_id` on quote. Bank rows may also use [`GET /partner/banks`](/partner/banks).

Each provider includes `min_amount`, `max_amount`, and `currency` for checkout validation.

<Warning>
**OnRamp and OffRamp provider lists can differ** for the same country — filter with `order_type`.
</Warning>

Optional filters: `country`, `currency`, `order_type`. Omit filters for the full tree.

<Note>
Binding eligibility: [`POST /partner/orders/quote`](/partner/orders/quote).
</Note>
""",
    ("get", "/partner/payment-methods"): """\
Indicative payment methods for one corridor.

### African corridors
- **`country`** — required
- **`currency`** — optional; must match the catalog when sent; response `context` always includes both
- **`order_type`** — `OnRamp` or `OffRamp`; omit to get both `onramp` and `offramp` buckets

### International bank
- **`currency`** = EUR or USD (required)
- Do **not** pass `country`
- EUR/USD onramp returns `bank`
- Offramp uses international bank when configured

### International bank payout markets
Example: FR + EUR offramp — pass `country` + `currency`. Returns rails such as `BankSepa` and `BankSwift` with `type` set to the international bank `PaymentMethodType`.

### Local fiat (African)
`mobile_money` and `bank` rows include a **`networks[]`** list (`id`, `name`, `min_amount`, `max_amount`, `currency`) for client-side amount gating.

<Note>
Binding check: [`POST /partner/orders/quote`](/partner/orders/quote).
</Note>
""",
    ("get", "/partner/order-requirements"): """\
Returns partner-neutral **field name** hints before [`POST /partner/orders/quote`](/partner/orders/quote).

Call after [`GET /partner/corridors`](/partner/corridors) and [`GET /partner/payment-methods`](/partner/payment-methods).

### Query
`country`, `currency`, `order_type` (`OnRamp` or `OffRamp`).

When several payout rails exist, list them with [`GET /partner/payment-methods`](/partner/payment-methods) first, then pass `payment_method_type` (e.g. `BankSepa`) on this call. Single-rail international bank corridors (e.g. GH) may omit it.

### Rails
- **`mobile_money`** or **`bank`** — both require `network_id` on quote (from catalog `providers[].id` or [`GET /partner/banks`](/partner/banks) for bank)
- Optional **`customer_type`** (`retail` or `institution`) on local fiat corridors

This endpoint does **not** return JSON Schema, bank lists, fees, or provider labels. Bank lists and dynamic form schemas are separate partner endpoints (see [Quickstart](/quickstart)).

<Note>
Binding check: [`POST /partner/orders/quote`](/partner/orders/quote).
</Note>
""",
    ("get", "/partner/banks"): """\
Lists bank/network institution options for a rail chosen via [`GET /partner/payment-methods`](/partner/payment-methods).

### Query
`country`, `currency`, `order_type` (`OnRamp` | `OffRamp`), and `payment_method_type`.

### Rails
- **`bank`** (local fiat) — active networks only; use returned `institutions[].id` as `payment_method.network_id` on quote
- **`mobile_money`** — returns **422**; use [`GET /partner/catalog`](/partner/catalog) `providers[].id` for momo `network_id`
- International bank types (e.g. `BankSepa`, `BankSwift`) — best-effort enum options from upstream form schema
""",
    ("get", "/partner/rates/indicative"): """\
Returns **indicative** `buy` / `sell` rates for comma-separated ISO fiat codes.

<Warning>
These rates are **not** binding. Use [`POST /partner/orders/quote`](/partner/orders/quote) for checkout pricing.
</Warning>

Response `data` includes `requested`, `rates`, and `fetched_at`.

**Auth:** `X-API-Key` header.
""",
    ("post", "/partner/orders/quote"): """\
Create a binding quote for a fiat ↔ crypto order.

<Steps>
  <Step title="Create quote">
    `POST` with corridor, customer, and payment method details.
  </Step>
  <Step title="Show pricing">
    Display returned amounts and **payment instructions** to the user (OnRamp).
  </Step>
  <Step title="Accept">
    [`POST /partner/orders/{quote_id}/accept`](/partner/orders/{quote_id}/accept) when the user confirms.
  </Step>
</Steps>

### Discovery before quote
- [`GET /partner/catalog`](/partner/catalog) or [`GET /partner/payment-methods`](/partner/payment-methods) → rails for the corridor
- [`GET /partner/catalog?order_type=OnRamp`](/partner/catalog) or `OffRamp` → `providers[].id` for momo/bank
- [`GET /partner/order-requirements`](/partner/order-requirements) → exact field names (`network_id` required for momo/bank)
- [`GET /partner/banks`](/partner/banks) → bank institution UUIDs where applicable

### Payment method by rail
**`mobile_money`**
- `payment_method.type=mobile_money`
- `payment_method.phone_number` (E.164)
- `payment_method.network_id` (UUID from catalog `providers[].id`)

**`bank`**
- `payment_method.type=bank`
- `account_number`, `account_name`
- `payment_method.network_id` (from [`GET /partner/banks`](/partner/banks) or catalog)

`provider` is optional — when omitted, ElementPay auto-routes by corridor.

### Quote IDs
- OnRamp: `yc_receive_<id>`
- OffRamp: `yc_send_<id>`

The quote expires at `data.expires_at`.
""",
    ("post", "/partner/orders/{quote_id}/accept"): """\
Accept a previously created quote and create the local order.

Send the same customer and payment method payload shape used at quote time (see [Test payloads](/sandbox/test-payloads)).

OnRamp: final payment instructions are returned after accept when applicable.
""",
}


def _first_example_value(media: dict[str, Any]) -> Any | None:
    if "example" in media:
        return media["example"]
    examples = media.get("examples")
    if not isinstance(examples, dict) or not examples:
        return None
    first = next(iter(examples.values()))
    if isinstance(first, dict) and "value" in first:
        return first["value"]
    return first


def collapse_plural_examples(doc: dict[str, Any]) -> int:
    """Keep one ``example`` per status — Mintlify uses inline tabs instead of dropdowns."""
    collapsed = 0
    for path_item in (doc.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for response in (operation.get("responses") or {}).values():
                if not isinstance(response, dict):
                    continue
                content = response.get("content")
                if not isinstance(content, dict):
                    continue
                media = content.get("application/json")
                if not isinstance(media, dict):
                    continue
                examples = media.get("examples")
                if not isinstance(examples, dict) or len(examples) <= 1:
                    continue
                if "example" not in media:
                    first = _first_example_value(media)
                    if first is not None:
                        media["example"] = first
                media.pop("examples", None)
                collapsed += 1
    return collapsed


def inject_response_examples(doc: dict[str, Any]) -> int:
    """Add singular ``example`` so Mintlify renders response bodies."""
    updated = 0
    for path, path_item in (doc.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for response in (operation.get("responses") or {}).values():
                if not isinstance(response, dict):
                    continue
                content = response.get("content")
                if not isinstance(content, dict):
                    continue
                media = content.get("application/json")
                if not isinstance(media, dict):
                    continue
                existing = media.get("example")
                if existing not in (None, {}):
                    continue
                value = _first_example_value(media)
                if value is not None and value != {}:
                    media["example"] = value
                    updated += 1
    return updated


def _validation_example_for_path(path: str) -> dict[str, Any]:
    if path.endswith("/rates/indicative"):
        return {
            "status": "error",
            "message": "Query parameter `fiat` is required (e.g. fiat=NGN,KES,GHS).",
            "data": {"field": "fiat"},
        }
    if "/orders/" in path:
        return {
            "status": "error",
            "message": "Missing requirements for selected route",
            "data": {"field": "order_type"},
        }
    return {
        "status": "error",
        "message": "Validation error",
        "data": {"field": "country"},
    }


def patch_empty_validation_stubs(doc: dict[str, Any]) -> int:
    """Fill empty FastAPI validation stubs so Mintlify shows a body."""
    patched = 0
    for path, path_item in (doc.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            responses = operation.get("responses")
            if not isinstance(responses, dict):
                continue
            for code, response in responses.items():
                if code != "422" or not isinstance(response, dict):
                    continue
                content = response.get("content") or {}
                media = content.get("application/json")
                if not isinstance(media, dict):
                    continue
                if media.get("example") not in (None, {}):
                    continue
                if media.get("examples"):
                    continue
                schema = media.get("schema") or {}
                ref = schema.get("$ref", "")
                if not ref.endswith("/HTTPValidationError"):
                    continue
                example = _validation_example_for_path(path)
                media["example"] = example
                media["schema"] = {
                    "type": "object",
                    "required": ["status", "message"],
                    "properties": {
                        "status": {"type": "string", "enum": ["error"]},
                        "message": {"type": "string"},
                        "data": {"type": ["object", "null"]},
                    },
                }
                patched += 1
    return patched


def apply_x_mint_guides(doc: dict[str, Any]) -> int:
    applied = 0
    for path, path_item in (doc.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            guide = ENDPOINT_GUIDES.get((method, path))
            if not guide:
                continue
            mint = operation.setdefault("x-mint", {})
            mint["content"] = guide.strip()
            applied += 1
    return applied


def enrich(doc: dict[str, Any]) -> dict[str, int]:
    working = deepcopy(doc)
    return {
        "examples_injected": inject_response_examples(working),
        "examples_collapsed": collapse_plural_examples(working),
        "validation_stubs_patched": patch_empty_validation_stubs(working),
        "guides_applied": apply_x_mint_guides(working),
        "_doc": working,  # type: ignore[typeddict-item]
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "targets",
        nargs="*",
        type=Path,
        help="openapi.json files (default: api-reference/openapi.json and openapi.json)",
    )
    args = parser.parse_args()
    targets = args.targets or list(TARGETS)

    for target in targets:
        if not target.is_file():
            print(f"Skip missing {target}", file=sys.stderr)
            continue
        doc = json.loads(target.read_text(encoding="utf-8"))
        result = enrich(doc)
        enriched_doc = result.pop("_doc")
        target.write_text(json.dumps(enriched_doc, indent=2) + "\n", encoding="utf-8")
        print(
            f"{target}: +{result['examples_injected']} examples, "
            f"~{result['examples_collapsed']} collapsed, "
            f"~{result['validation_stubs_patched']} validation stubs, "
            f"+{result['guides_applied']} x-mint guides"
        )


if __name__ == "__main__":
    main()
