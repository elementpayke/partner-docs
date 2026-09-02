#!/usr/bin/env python3
"""
Mintlify-specific OpenAPI enrichment for partner-docs.

Run after sync-openapi-responses (or sync_partner_openapi_to_docs):

- Injects singular ``example`` on each response (Mintlify Try-it panels use this).
- Adds ``x-mint.content`` blocks with formatted endpoint guides.
- Drops empty FastAPI-only 422 stubs when a documented partner error exists.
- Replaces ``POST /partner/orders/quote`` request schema with a Try-it-friendly surface.
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
- **`bank`** (local fiat) — active networks only; use returned `banks[].id` as `payment_method.network_id` on quote
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

### Customer identity
**Preferred:** `customer_id` (`pcus_*` from an **approved** [customer vault](/customers/quickstart) case) — omit the inline `customer` object.

**Legacy:** inline `customer` on quote still works; see [Sandbox test payloads](/sandbox/test-payloads) for corridor-specific shapes.

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

QUOTE_TRY_IT_DEFAULT = {
    "order_type": "OnRamp",
    "currency": "KES",
    "country": "KE",
    "local_amount": 800,
    "customer_id": "pcus_a1b2c3d4e5f6",
    "asset": {
        "token": "0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913",
        "currency": "USDC",
        "network": "BASE",
    },
    "payment_method": {
        "type": "mobile_money",
        "phone_number": "+2541111111111",
        "network_id": "7ea6df5c-6bba-46b2-a7e6-f511959e7edb",
    },
    "wallet_address": "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe",
}

PARTNER_ORDER_QUOTE_TRY_IT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["order_type"],
    "properties": {
        "order_type": {
            "type": "string",
            "enum": ["OnRamp", "OffRamp"],
            "description": "OnRamp = fiat to crypto. OffRamp = crypto to fiat.",
            "example": "OnRamp",
        },
        "country": {
            "type": "string",
            "minLength": 2,
            "maxLength": 2,
            "description": "ISO country (African corridors). Omit for EUR/USD international bank payin.",
            "example": "KE",
        },
        "currency": {
            "type": "string",
            "minLength": 3,
            "maxLength": 3,
            "example": "KES",
        },
        "local_amount": {
            "type": "integer",
            "minimum": 1,
            "description": "OnRamp: fiat amount the customer pays.",
            "example": 800,
        },
        "crypto_amount": {
            "type": "number",
            "exclusiveMinimum": 0,
            "description": "OffRamp: stablecoin amount the customer sends.",
            "example": 20,
        },
        "customer_id": {
            "type": "string",
            "description": (
                "Preferred: approved vault customer id (pcus_*). "
                "Omit inline customer when set."
            ),
            "example": "pcus_a1b2c3d4e5f6",
        },
        "customer": {
            "type": "object",
            "description": (
                "Legacy inline KYC. Omit when customer_id is set. "
                "Corridor-specific examples: /sandbox/test-payloads."
            ),
            "additionalProperties": True,
        },
        "asset": {
            "type": "object",
            "description": "Stablecoin asset block (sandbox default: Base USDC).",
            "properties": {
                "token": {
                    "type": "string",
                    "example": "0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913",
                },
                "currency": {"type": "string", "example": "USDC"},
                "network": {"type": "string", "example": "BASE"},
            },
        },
        "payment_method": {
            "type": "object",
            "description": (
                "Fiat rail. mobile_money: phone_number + network_id. "
                "bank: account_number, account_name, network_id."
            ),
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["mobile_money", "bank"],
                    "example": "mobile_money",
                },
                "phone_number": {
                    "type": "string",
                    "description": "E.164 MSISDN (mobile_money).",
                    "example": "+2541111111111",
                },
                "account_number": {"type": "string"},
                "account_name": {"type": "string"},
                "network_id": {
                    "type": "string",
                    "description": "Institution UUID from GET /partner/catalog.",
                    "example": "7ea6df5c-6bba-46b2-a7e6-f511959e7edb",
                },
            },
        },
        "wallet_address": {
            "type": "string",
            "description": "OnRamp: destination wallet for stablecoin delivery.",
            "example": "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe",
        },
        "refund_address": {
            "type": "string",
            "description": "OffRamp: refund wallet if payout fails.",
            "example": "0x3333333333333333333333333333333333333333",
        },
    },
    "title": "PartnerOrderQuoteRequestTryIt",
    "description": (
        "Canonical quote body for Mintlify Try it. The live API also accepts "
        "legacy top-level fields (provider, channel_id, destination, …) — "
        "see Quickstart and /sandbox/test-payloads."
    ),
    "example": QUOTE_TRY_IT_DEFAULT,
}

QUOTE_TRY_IT_EXAMPLES: dict[str, Any] = {
    "ke_onramp_vault_customer_id": {
        "summary": "KE OnRamp — vault customer_id (recommended)",
        "description": (
            "Use an approved pcus_* from the customer vault. "
            "Discover network_id from GET /partner/catalog?country=KE&order_type=OnRamp."
        ),
        "value": QUOTE_TRY_IT_DEFAULT,
    },
    "ke_offramp_vault_customer_id": {
        "summary": "KE OffRamp — vault customer_id",
        "description": "Customer sends USDC; receives KES by mobile money.",
        "value": {
            "order_type": "OffRamp",
            "currency": "KES",
            "country": "KE",
            "crypto_amount": 20,
            "customer_id": "pcus_a1b2c3d4e5f6",
            "asset": {
                "token": "0xc2132d05d31c914a87c6611c10748aeb04b58e8f",
                "currency": "USDT",
                "network": "POLYGON",
            },
            "payment_method": {
                "type": "mobile_money",
                "phone_number": "+2541111111111",
                "network_id": "7ea6df5c-6bba-46b2-a7e6-f511959e7edb",
            },
            "refund_address": "0x3333333333333333333333333333333333333333",
        },
    },
    "ke_onramp_inline_sandbox": {
        "summary": "KE OnRamp — inline customer (legacy)",
        "description": (
            "Sandbox success MSISDN +2541111111111. "
            "Prefer customer_id for new integrations."
        ),
        "value": {
            "order_type": "OnRamp",
            "currency": "KES",
            "country": "KE",
            "local_amount": 800,
            "asset": {
                "token": "0x833589fcd6edb6e08f4c7c32d4f71b54bdA02913",
                "currency": "USDC",
                "network": "BASE",
            },
            "customer": {
                "uid": "sandbox-ke-onramp-success-001",
                "type": "user",
                "name": "Successful Jane Customer",
                "country": "KE",
                "phone": "+2541111111111",
                "email": "jane@example.com",
                "id_number": "A1234567",
                "id_type": "passport",
            },
            "payment_method": {
                "type": "mobile_money",
                "phone_number": "+2541111111111",
                "network_id": "7ea6df5c-6bba-46b2-a7e6-f511959e7edb",
            },
            "wallet_address": "0xde0B295669a9FD93d5F28D9Ec85E40f4cb697BAe",
        },
    },
}


def simplify_quote_try_it(doc: dict[str, Any]) -> int:
    """Replace bloated auto-generated quote schema with a Try-it-friendly surface."""

    paths = doc.setdefault("paths", {})
    quote_op = paths.get("/partner/orders/quote", {}).get("post")
    if not isinstance(quote_op, dict):
        return 0

    components = doc.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas["PartnerOrderQuoteRequestTryIt"] = deepcopy(PARTNER_ORDER_QUOTE_TRY_IT_SCHEMA)

    request_body = quote_op.setdefault("requestBody", {})
    content = request_body.setdefault("content", {})
    media = content.setdefault("application/json", {})
    media["schema"] = {"$ref": "#/components/schemas/PartnerOrderQuoteRequestTryIt"}
    media["example"] = deepcopy(QUOTE_TRY_IT_DEFAULT)
    media["examples"] = deepcopy(QUOTE_TRY_IT_EXAMPLES)

    mint = quote_op.setdefault("x-mint", {})
    mint["playground"] = {"expand": False}

    return 1


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
            guide_text = guide.strip()
            mint = operation.setdefault("x-mint", {})
            mint["content"] = guide_text
            # Mintlify renders `description` and x-mint.content — keep description
            # to one short line so the formatted guide is not duplicated as a wall
            # of text (synced OpenAPI uses inline markdown without line breaks).
            operation["description"] = guide_text.split("\n\n", 1)[0].replace("\n", " ")
            applied += 1
    return applied


def enrich(doc: dict[str, Any]) -> dict[str, int]:
    working = deepcopy(doc)
    return {
        "examples_injected": inject_response_examples(working),
        "examples_collapsed": collapse_plural_examples(working),
        "validation_stubs_patched": patch_empty_validation_stubs(working),
        "guides_applied": apply_x_mint_guides(working),
        "quote_try_it_simplified": simplify_quote_try_it(working),
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
            f"+{result['guides_applied']} x-mint guides, "
            f"quote_try_it={result['quote_try_it_simplified']}"
        )


if __name__ == "__main__":
    main()
