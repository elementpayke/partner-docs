# AGENTS.md

Element Pay Partner API — start here for coding agents.

1. Read [`llms.txt`](llms.txt) (ordered reading list).
2. Follow [`docs/agents.md`](docs/agents.md) (auth, OnRamp path, optional banking/accounts, webhooks).
3. Implement against [`openapi.yaml`](openapi.yaml) (do not invent paths).
4. For local fiat ↔ USDC/USDT (OnRamp + OffRamp), use [`docs/integration-fiat-stablecoin.md`](docs/integration-fiat-stablecoin.md).
5. For vault KYC + accounts route map, use `customers/quickstart.mdx`, `customers/accounts.mdx`, `customers/route-cheat-sheet.mdx`.
6. For optional customer EIP-712 accept (non-custodial), use [`orders/signed-accepts.mdx`](orders/signed-accepts.mdx) — enable **Signed accepts** in Console per API key (not via the partner API).
7. Check [`docs/KNOWN_GAPS.md`](docs/KNOWN_GAPS.md) before assuming undocumented behavior.

**Auth:** `X-API-Key: is_test_YOUR_API_KEY` (sandbox) or `is_live_…` (production).  
**Bases:** `https://sandbox.elementpay.net/api/v1` · `https://api.elementpay.net/api/v1`
