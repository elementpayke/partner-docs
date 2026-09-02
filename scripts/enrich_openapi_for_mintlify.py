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
Use **one** of:

- **`customer_id`** (`pcus_*` from an **approved** [customer vault](/customers/quickstart) case) — recommended for new integrations
- **Inline `customer`** — still supported; pick **KE OnRamp — inline customer** in Try it or fill the `customer` object

Do not send both. Corridor-specific inline shapes: [Sandbox test payloads](/sandbox/test-payloads).

<Note>
Try it omits legacy top-level fields (`provider`, `channel_id`, `destination`, `rail`, …). Omit `provider` on live calls too — Element Pay auto-routes by corridor.
</Note>

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
    ("get", "/partner/customers/requirements"): """\
Return the **full KYC package** for a customer type before create/submit.

### Query
- **`type`** — `individual` (default) or `business`
- **`country`** — optional ISO code; sharpens corridor-specific conditional fields (e.g. NG BVN, US EIN)

Response `data` lists `required_fields`, `required_documents`, `optional_fields`, and `conditional_fields`. Use this to build `profile` on [`POST /partner/customers`](/partner/customers) and document uploads.

<Note>
This is **not** the same as [`GET /partner/order-requirements`](/partner/order-requirements) (quote field hints per corridor).
</Note>
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
                "Approved vault customer id (pcus_*). Use this **or** inline "
                "`customer`, not both."
            ),
            "example": "pcus_a1b2c3d4e5f6",
        },
        "customer": {
            "type": "object",
            "description": (
                "Inline retail KYC when you do not use customer_id. "
                "Corridor extras (BVN, institution): /sandbox/test-payloads."
            ),
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "Partner-stable user id for this order.",
                    "example": "sandbox-ke-onramp-success-001",
                },
                "type": {
                    "type": "string",
                    "enum": ["user", "institution"],
                    "example": "user",
                },
                "name": {"type": "string", "example": "Successful Jane Customer"},
                "country": {"type": "string", "example": "KE"},
                "phone": {"type": "string", "example": "+2541111111111"},
                "address": {
                    "type": "string",
                    "description": "Customer address (required for many local corridors, e.g. KE).",
                    "example": "Nairobi",
                },
                "dob": {
                    "type": "string",
                    "description": "Date of birth (corridor-specific format, e.g. MM/DD/YYYY for KE).",
                    "example": "02/01/1997",
                },
                "email": {"type": "string", "example": "jane@example.com"},
                "id_number": {"type": "string", "example": "A1234567"},
                "id_type": {"type": "string", "example": "passport"},
            },
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
        "Quote body for Mintlify Try it. Includes customer_id **or** inline "
        "customer, asset, and payment_method only. Not shown here (still "
        "accepted on live API if needed): provider, channel_id, channel_type, "
        "sequence_id, destination, source, sender, recipient, rail, token "
        "top-level alias, crypto_currency/crypto_network hints."
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
        "summary": "KE OnRamp — inline customer",
        "description": (
            "Inline customer object (no customer_id). Sandbox success MSISDN "
            "+2541111111111."
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
                "address": "Nairobi",
                "dob": "02/01/1997",
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

PARTNER_ERROR_ENVELOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["status", "message"],
    "properties": {
        "status": {"type": "string", "enum": ["error"]},
        "message": {"type": "string"},
        "data": {"type": ["object", "null"]},
    },
}

PARTNER_SUCCESS_ENVELOPE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["status", "message", "data"],
    "properties": {
        "status": {"type": "string", "enum": ["success"]},
        "message": {"type": "string"},
        "data": {"type": "object"},
    },
}

PARTNER_UNAUTHORIZED_RESPONSE: dict[str, Any] = {
    "description": "Missing or invalid API key",
    "content": {
        "application/json": {
            "schema": deepcopy(PARTNER_ERROR_ENVELOPE_SCHEMA),
            "example": {"status": "error", "message": "Unauthorized", "data": None},
        }
    },
}

CUSTOMER_VAULT_APPROVED_ROW: dict[str, Any] = {
    "id": "pcus_a1b2c3d4e5f6",
    "partner_customer_ref": "partner-cust-001",
    "type": "individual",
    "status": "approved",
    "profile": {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "date_of_birth": "1990-01-15",
        "country_of_residence": "GB",
        "phone": "+447700900123",
        "gender": "f",
        "id_type": "passport",
        "id_number": "A1234567",
        "address": {
            "line1": "1 Example Street",
            "city": "London",
            "country": "GB",
            "postal_code": "E1 6AN",
        },
    },
    "documents": [
        {
            "id": "pdoc_a1b2c3d4e5f6",
            "category": "identity",
            "content_type": "application/pdf",
            "created_at": "2026-08-01T12:00:00+00:00",
        },
        {
            "id": "pdoc_b2c3d4e5f6a7",
            "category": "address",
            "content_type": "application/pdf",
            "created_at": "2026-08-01T12:01:00+00:00",
        },
    ],
    "products": {"deposit_account": {"status": "ready"}},
    "created_at": "2026-08-01T11:55:00+00:00",
    "updated_at": "2026-08-01T12:05:00+00:00",
    "submitted_at": "2026-08-01T12:02:00+00:00",
}

CUSTOMER_VAULT_INCOMPLETE_ROW: dict[str, Any] = {
    "id": "pcus_a1b2c3d4e5f6",
    "partner_customer_ref": "cust-ke-001",
    "type": "individual",
    "status": "incomplete",
    "profile": {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
        "date_of_birth": "1990-01-15",
        "country_of_residence": "GB",
        "phone": "+447700900123",
        "gender": "f",
        "address": {
            "line1": "1 Example Street",
            "city": "London",
            "country": "GB",
            "postal_code": "E1 6AN",
        },
    },
    "documents": [],
    "products": {"deposit_account": {"status": "none"}},
    "missing": [
        "profile.id_number",
        "profile.id_type",
        "document.identity",
        "document.address",
    ],
    "created_at": "2026-08-01T11:55:00+00:00",
    "updated_at": "2026-08-01T11:55:00+00:00",
    "submitted_at": None,
}

CUSTOMER_VAULT_PENDING_ROW: dict[str, Any] = {
    **deepcopy(CUSTOMER_VAULT_APPROVED_ROW),
    "status": "pending_review",
    "products": {"deposit_account": {"status": "none"}},
    "updated_at": "2026-08-01T12:02:00+00:00",
    "submitted_at": "2026-08-01T12:02:00+00:00",
}
CUSTOMER_VAULT_PENDING_ROW.pop("missing", None)

CUSTOMER_REQUIREMENTS_INDIVIDUAL: dict[str, Any] = {
    "type": "individual",
    "required_fields": [
        "first_name",
        "last_name",
        "email",
        "date_of_birth",
        "country_of_residence",
        "gender",
        "phone",
        "address",
        "id_number",
        "id_type",
    ],
    "required_documents": [
        {
            "key": "identity",
            "description": "Government photo ID (passport, license, national ID)",
        },
        {
            "key": "address",
            "description": "Proof of address (last 3 months)",
        },
    ],
    "optional_fields": [
        "middle_name",
        "liveness_check_id",
        "proof_of_address_type",
        "additional_id_number",
        "additional_id_type",
    ],
    "conditional_fields": [
        {
            "field": "additional_id_type",
            "when": "country_of_residence == NG",
            "required": True,
            "description": "Nigeria BVN type (use bvn)",
            "example": "bvn",
        },
        {
            "field": "additional_id_number",
            "when": "country_of_residence == NG",
            "required": True,
            "description": "Nigeria BVN number (11 digits)",
            "example": "12345678901",
        },
    ],
    "products": {
        "deposit_account": {
            "notes": (
                "deposit_account.status ready means KYC approved and partner may "
                "open deposit accounts — no automatic account open."
            ),
        },
    },
    "notes": (
        "Full individual package is required before submit. profile.address must "
        "include line1, city, and country. profile.id_number and profile.id_type "
        "are required. Nigeria residents must also include profile.additional_id_type "
        "(bvn) and profile.additional_id_number."
    ),
}

CUSTOMER_REQUIREMENTS_BUSINESS_US: dict[str, Any] = {
    "type": "business",
    "required_fields": [
        "legal_name",
        "email",
        "phone",
        "website",
        "business_type",
        "country_of_incorporation",
        "registered_address",
        "industry",
        "registration_number",
        "description",
        "incorporation_meta",
        "monthly_payments_count",
        "monthly_transaction_value",
        "max_transfer_amount",
        "annual_turnover",
        "customer_types",
        "funding_source",
        "officers",
        "tax_id",
    ],
    "required_documents": [
        {
            "key": "certificate_of_incorporation",
            "description": "Business registration document",
        },
        {
            "key": "memorandum_of_association",
            "description": "Memorandum / articles document",
        },
        {
            "key": "proof_of_address",
            "description": "Business proof of address (last 3 months)",
        },
        {"key": "identity", "description": "Officer government photo ID"},
        {
            "key": "address",
            "description": "Officer proof of address (last 3 months)",
        },
    ],
    "optional_fields": [
        "liveness_check_id",
        "sales_channel",
        "operating_address",
    ],
    "conditional_fields": [
        {
            "field": "tax_id",
            "when": "country_of_incorporation == US",
            "required": True,
            "description": "US EIN (9 digits)",
            "example": "123456789",
        },
    ],
    "products": {
        "deposit_account": {
            "notes": (
                "After status approved and deposit_account becomes ready, partner "
                "may open deposit accounts via account APIs."
            ),
        },
    },
    "notes": (
        "Full business package is required before submit. US-incorporated "
        "businesses must include profile.tax_id (EIN)."
    ),
}

SEND_PREVIEW_DATA: dict[str, Any] = {
    "preview_token": "nvsend.eyJhbGciOiJIUzI1NiJ9.preview",
    "currency": "USDC",
    "network": "Base",
    "amount": "5.00",
    "fee": "0.05",
    "receive_amount": "4.95",
    "fee_status": "estimated",
    "chain_disclaimer": "Send only USDC on Base to the destination address.",
    "expires_at": "2026-07-30T12:10:00+00:00",
}

SEND_CONFIRMED_DATA: dict[str, Any] = {
    "id": 55,
    "entity_id": 12,
    "account_id": 21,
    "status": "submitted",
    "currency": "USDC",
    "network": "Base",
    "to_address": "0x40C2f2e0326bD1f647fbeB8732529e08B4DB309f",
    "amount": "5.00",
    "fee": "0.05",
    "receive_amount": "4.95",
    "fee_status": "final",
    "chain_disclaimer": "Send only USDC on Base to the destination address.",
    "created_at": "2026-08-01T12:05:00+00:00",
}


def _json_success(message: str, data: Any) -> dict[str, Any]:
    return {"status": "success", "message": message, "data": data}


def _ensure_unauthorized(responses: dict[str, Any]) -> None:
    if "401" not in responses:
        responses["401"] = deepcopy(PARTNER_UNAUTHORIZED_RESPONSE)


def _patch_success_response(
    responses: dict[str, Any],
    code: str,
    *,
    message: str,
    data: Any,
    schema_ref: str,
    description: str | None = None,
    examples: dict[str, Any] | None = None,
) -> None:
    response = responses.setdefault(code, {})
    if description:
        response["description"] = description
    content = response.setdefault("content", {})
    media = content.setdefault("application/json", {})
    media["schema"] = {"$ref": schema_ref}
    media["example"] = _json_success(message, data)
    if examples:
        media["examples"] = examples


def _patch_error_response(
    responses: dict[str, Any],
    code: str,
    *,
    description: str,
    example: dict[str, Any],
) -> None:
    responses[code] = {
        "description": description,
        "content": {
            "application/json": {
                "schema": deepcopy(PARTNER_ERROR_ENVELOPE_SCHEMA),
                "example": example,
            }
        },
    }


def _register_partner_response_schemas(schemas: dict[str, Any]) -> None:
    schemas["PartnerErrorEnvelope"] = deepcopy(PARTNER_ERROR_ENVELOPE_SCHEMA)
    schemas["PartnerSuccessEnvelope"] = deepcopy(PARTNER_SUCCESS_ENVELOPE_SCHEMA)
    schemas["PartnerCustomerRequirementsData"] = {
        "type": "object",
        "required": [
            "type",
            "required_fields",
            "required_documents",
            "optional_fields",
            "conditional_fields",
            "products",
            "notes",
        ],
        "properties": {
            "type": {"type": "string", "enum": ["individual", "business"]},
            "required_fields": {"type": "array", "items": {"type": "string"}},
            "required_documents": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["key", "description"],
                    "properties": {
                        "key": {"type": "string"},
                        "description": {"type": "string"},
                    },
                },
            },
            "optional_fields": {"type": "array", "items": {"type": "string"}},
            "conditional_fields": {
                "type": "array",
                "items": {"type": "object", "additionalProperties": True},
            },
            "products": {"type": "object"},
            "notes": {"type": "string"},
        },
        "title": "PartnerCustomerRequirementsData",
    }
    schemas["PartnerCustomerRequirementsSuccessResponse"] = {
        "type": "object",
        "required": ["status", "message", "data"],
        "properties": {
            "status": {"type": "string", "enum": ["success"]},
            "message": {"type": "string", "example": "Customer requirements"},
            "data": {"$ref": "#/components/schemas/PartnerCustomerRequirementsData"},
        },
        "title": "PartnerCustomerRequirementsSuccessResponse",
    }
    if "PartnerCustomerVaultRow" in schemas:
        schemas["PartnerCustomerVaultSuccessResponse"] = {
            "type": "object",
            "required": ["status", "message", "data"],
            "properties": {
                "status": {"type": "string", "enum": ["success"]},
                "message": {"type": "string"},
                "data": {"$ref": "#/components/schemas/PartnerCustomerVaultRow"},
            },
            "title": "PartnerCustomerVaultSuccessResponse",
        }
    schemas["PartnerCustomerDocumentUploadData"] = {
        "type": "object",
        "required": ["document", "customer"],
        "properties": {
            "document": {"$ref": "#/components/schemas/PartnerCustomerDocumentMeta"},
            "customer": {"$ref": "#/components/schemas/PartnerCustomerVaultRow"},
        },
        "title": "PartnerCustomerDocumentUploadData",
    }
    schemas["PartnerCustomerDocumentUploadSuccessResponse"] = {
        "type": "object",
        "required": ["status", "message", "data"],
        "properties": {
            "status": {"type": "string", "enum": ["success"]},
            "message": {"type": "string", "example": "Document uploaded"},
            "data": {"$ref": "#/components/schemas/PartnerCustomerDocumentUploadData"},
        },
        "title": "PartnerCustomerDocumentUploadSuccessResponse",
    }


def patch_partner_integrator_responses(doc: dict[str, Any]) -> int:
    """Fill success/error response examples missing from FastAPI export."""

    paths = doc.setdefault("paths", {})
    components = doc.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    _register_partner_response_schemas(schemas)

    vault_schema = "#/components/schemas/PartnerCustomerVaultSuccessResponse"
    req_schema = "#/components/schemas/PartnerCustomerRequirementsSuccessResponse"
    doc_upload_schema = (
        "#/components/schemas/PartnerCustomerDocumentUploadSuccessResponse"
    )
    envelope_schema = "#/components/schemas/PartnerSuccessEnvelope"

    patched = 0

    req_op = paths.get("/partner/customers/requirements", {}).get("get")
    if isinstance(req_op, dict):
        responses = req_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "200",
            message="Customer requirements",
            data=deepcopy(CUSTOMER_REQUIREMENTS_INDIVIDUAL),
            schema_ref=req_schema,
            description=(
                "Required profile fields and document categories for the "
                "requested customer type."
            ),
            examples={
                "individual": {
                    "summary": "Individual package",
                    "value": _json_success(
                        "Customer requirements",
                        deepcopy(CUSTOMER_REQUIREMENTS_INDIVIDUAL),
                    ),
                },
                "business_us": {
                    "summary": "Business package (US)",
                    "description": "Pass `type=business&country=US` to hard-require tax_id.",
                    "value": _json_success(
                        "Customer requirements",
                        deepcopy(CUSTOMER_REQUIREMENTS_BUSINESS_US),
                    ),
                },
            },
        )
        _patch_error_response(
            responses,
            "400",
            description="Invalid customer type query parameter",
            example={
                "status": "error",
                "message": "Invalid customer type",
                "data": {
                    "field": "type",
                    "allowed": ["business", "individual"],
                },
            },
        )
        _ensure_unauthorized(responses)
        if "422" in responses:
            responses["422"]["description"] = "Query validation error"
            media = responses["422"].get("content", {}).get("application/json", {})
            if isinstance(media, dict):
                media["example"] = {
                    "status": "error",
                    "message": "Validation error",
                    "data": {"field": "type"},
                }
        patched += 1

    create_op = paths.get("/partner/customers", {}).get("post")
    if isinstance(create_op, dict):
        responses = create_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "201",
            message="Customer created",
            data=deepcopy(CUSTOMER_VAULT_INCOMPLETE_ROW),
            schema_ref=vault_schema,
            description="New incomplete vault case (or existing row on idempotent ref hit).",
        )
        _ensure_unauthorized(responses)
        patched += 1

    get_op = paths.get("/partner/customers/{customer_id}", {}).get("get")
    if isinstance(get_op, dict):
        responses = get_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "200",
            message="Customer",
            data=deepcopy(CUSTOMER_VAULT_APPROVED_ROW),
            schema_ref=vault_schema,
            description="One tenant-owned customer including document metadata and missing[].",
        )
        _patch_error_response(
            responses,
            "404",
            description="Customer not found for this API key",
            example={
                "status": "error",
                "message": "Customer not found",
                "data": None,
            },
        )
        _ensure_unauthorized(responses)
        patched += 1

    patch_op = paths.get("/partner/customers/{customer_id}", {}).get("patch")
    if isinstance(patch_op, dict):
        responses = patch_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "200",
            message="Customer updated",
            data=deepcopy(CUSTOMER_VAULT_INCOMPLETE_ROW),
            schema_ref=vault_schema,
            description="Updated draft customer (may include missing[] while incomplete).",
        )
        _ensure_unauthorized(responses)
        patched += 1

    upload_op = paths.get("/partner/customers/{customer_id}/documents", {}).get("post")
    if isinstance(upload_op, dict):
        responses = upload_op.setdefault("responses", {})
        uploaded_customer = deepcopy(CUSTOMER_VAULT_INCOMPLETE_ROW)
        uploaded_customer["documents"] = [
            {
                "id": "pdoc_a1b2c3d4e5f6",
                "category": "identity",
                "content_type": "application/pdf",
                "created_at": "2026-08-01T12:00:00+00:00",
            }
        ]
        uploaded_customer["missing"] = [
            "profile.id_number",
            "profile.id_type",
            "document.address",
        ]
        _patch_success_response(
            responses,
            "201",
            message="Document uploaded",
            data={
                "document": uploaded_customer["documents"][0],
                "customer": uploaded_customer,
            },
            schema_ref=doc_upload_schema,
            description="Document stored; returns metadata and updated customer row.",
        )
        _ensure_unauthorized(responses)
        patched += 1

    submit_op = paths.get("/partner/customers/{customer_id}/submit", {}).get("post")
    if isinstance(submit_op, dict):
        responses = submit_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "200",
            message="Customer submitted",
            data=deepcopy(CUSTOMER_VAULT_PENDING_ROW),
            schema_ref=vault_schema,
            description="Package submitted for review (or current row if already submitted).",
        )
        responses["422"] = {
            "description": "Package incomplete — missing profile fields or documents",
            "content": {
                "application/json": {
                    "schema": deepcopy(PARTNER_ERROR_ENVELOPE_SCHEMA),
                    "example": {
                        "status": "error",
                        "message": "Customer package is incomplete",
                        "data": {
                            "code": "package_incomplete",
                            "missing": [
                                "profile.id_number",
                                "profile.id_type",
                                "document.identity",
                                "document.address",
                            ],
                        },
                    },
                }
            },
        }
        _ensure_unauthorized(responses)
        patched += 1

    retry_op = paths.get(
        "/partner/customers/{customer_id}/deposit-account/retry", {}
    ).get("post")
    if isinstance(retry_op, dict):
        responses = retry_op.setdefault("responses", {})
        retry_customer = deepcopy(CUSTOMER_VAULT_APPROVED_ROW)
        retry_customer["products"] = {"deposit_account": {"status": "provisioning"}}
        _patch_success_response(
            responses,
            "200",
            message="Deposit account provisioning retried",
            data=retry_customer,
            schema_ref=vault_schema,
            description="Failed deposit-account attempt re-queued (unchanged KYC/KYB only).",
        )
        _patch_error_response(
            responses,
            "409",
            description="Customer not approved or deposit account not in failed state",
            example={
                "status": "error",
                "message": "Deposit account provisioning is not in a failed state",
                "data": {"deposit_account_status": "ready"},
            },
        )
        _ensure_unauthorized(responses)
        patched += 1

    send_preview_op = paths.get(
        "/partner/customers/{customer_id}/accounts/{account_id}/sends/preview", {}
    ).get("post")
    if isinstance(send_preview_op, dict):
        responses = send_preview_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "201",
            message="Send preview",
            data=deepcopy(SEND_PREVIEW_DATA),
            schema_ref=envelope_schema,
            description="Estimated fees and preview token for confirm step.",
        )
        _patch_error_response(
            responses,
            "409",
            description="Deposit account is not ready",
            example={
                "status": "error",
                "message": "Deposit account is not ready",
                "data": {"deposit_account_status": "pending"},
            },
        )
        _ensure_unauthorized(responses)
        patched += 1

    send_confirm_op = paths.get(
        "/partner/customers/{customer_id}/accounts/{account_id}/sends", {}
    ).get("post")
    if isinstance(send_confirm_op, dict):
        responses = send_confirm_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "201",
            message="Send submitted",
            data=deepcopy(SEND_CONFIRMED_DATA),
            schema_ref=envelope_schema,
            description="Stablecoin send accepted for processing.",
        )
        _ensure_unauthorized(responses)
        patched += 1

    send_get_op = paths.get(
        "/partner/customers/{customer_id}/accounts/{account_id}/sends/{send_id}", {}
    ).get("get")
    if isinstance(send_get_op, dict):
        responses = send_get_op.setdefault("responses", {})
        _patch_success_response(
            responses,
            "200",
            message="Send",
            data=deepcopy(SEND_CONFIRMED_DATA),
            schema_ref=envelope_schema,
            description="Stablecoin send status for polling.",
        )
        _ensure_unauthorized(responses)
        patched += 1

    for path_key, method in (
        ("/partner/orders/quote", "post"),
        ("/partner/orders/{quote_id}/accept", "post"),
        ("/partner/orders/{order_id}", "get"),
    ):
        op = paths.get(path_key, {}).get(method)
        if not isinstance(op, dict):
            continue
        responses = op.get("responses") or {}
        for code in ("200", "201"):
            response = responses.get(code)
            if not isinstance(response, dict):
                continue
            media = (response.get("content") or {}).get("application/json")
            if not isinstance(media, dict):
                continue
            if media.get("example") and (
                not media.get("schema") or media.get("schema") == {}
            ):
                media["schema"] = {"$ref": envelope_schema}
                patched += 1

    list_op = paths.get("/partner/customers", {}).get("get")
    if isinstance(list_op, dict):
        _ensure_unauthorized(list_op.setdefault("responses", {}))

    return patched


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
        "partner_responses_patched": patch_partner_integrator_responses(working),
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
            f"quote_try_it={result['quote_try_it_simplified']}, "
            f"partner_responses={result['partner_responses_patched']}"
        )


if __name__ == "__main__":
    main()
