#!/usr/bin/env python3
"""
Merge OpenAPI ``responses`` blocks from the aggregator partner snapshot into this site.

Usage (after exporting in element-pay-aggregator):

    python scripts/export_partner_openapi.py   # in aggregator repo
    python scripts/sync-openapi-responses.py \\
        ../element-pay-aggregator/app/docs/partner/openapi.snapshot.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    REPO_ROOT / "api-reference" / "openapi.json",
    REPO_ROOT / "openapi.json",
)


def merge_responses(snapshot: dict, doc: dict) -> int:
    updated = 0
    for path, methods in snapshot.get("paths", {}).items():
        if path not in doc.get("paths", {}):
            continue
        for method, operation in methods.items():
            if not isinstance(operation, dict) or "responses" not in operation:
                continue
            if method not in doc["paths"][path]:
                continue
            doc["paths"][path][method]["responses"] = operation["responses"]
            updated += 1
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "snapshot",
        type=Path,
        help="Path to openapi.snapshot.json from element-pay-aggregator",
    )
    args = parser.parse_args()
    if not args.snapshot.is_file():
        print(f"Snapshot not found: {args.snapshot}", file=sys.stderr)
        sys.exit(1)

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    for target in TARGETS:
        if not target.is_file():
            print(f"Skip missing {target}", file=sys.stderr)
            continue
        doc = json.loads(target.read_text(encoding="utf-8"))
        count = merge_responses(snapshot, doc)
        target.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        print(f"Updated {count} operations in {target}")

    enrich_script = REPO_ROOT / "scripts" / "enrich_openapi_for_mintlify.py"
    if enrich_script.is_file():
        subprocess.run([sys.executable, str(enrich_script)], check=True)
    else:
        print(f"Skip Mintlify enrich — missing {enrich_script}", file=sys.stderr)


if __name__ == "__main__":
    main()
