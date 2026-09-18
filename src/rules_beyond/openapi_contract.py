"""Frozen V0.2 OpenAPI entry point.

``contracts/openapi/mvp-v0.2.json`` is a checked-in derived artifact of
``contract_app.openapi()`` and is consumed by Developer B's code generator
(``web/src/contract/generated/api.ts``). ``tests/test_openapi_snapshot.py`` and the
frontend ``contract:check`` job both fail if this app and the snapshot drift.

A3 therefore wires the real routes (see :mod:`rules_beyond.api_app`) into the
same OpenAPI surface. Contract changes, including the read-only model-call receipt
route, must update the checked-in snapshot and generated frontend types together.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi import FastAPI

from .api_app import build_app


def build_contract_app() -> FastAPI:
    """OpenAPI/contract app: the real routes without runtime provider wiring."""

    return build_app()


contract_app = build_contract_app()


def export_openapi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(contract_app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export the frozen Rules Beyond MVP OpenAPI contract."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("contracts/openapi/mvp-v0.2.json"),
    )
    args = parser.parse_args()
    export_openapi(args.output)


if __name__ == "__main__":
    main()
