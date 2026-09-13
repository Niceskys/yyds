"""ASGI entry point for the real V0.2 HTTP backend (the surface Developer B B4 calls).

Start the backend with either::

    python -m rules_beyond.api_server --host 127.0.0.1 --port 8000
    uvicorn rules_beyond.api_server:create_runtime_app --factory --host 127.0.0.1 --port 8000

Then the frozen five routes are reachable under ``http://127.0.0.1:8000/api/v1``.

The repository/provider wiring is built inside ``create_runtime_app()`` at startup,
so importing this module alone never requires an API key and never
touches the network. There is deliberately no extra health/business route: the
public surface stays exactly the frozen five routes.
"""

from __future__ import annotations

import argparse

from fastapi import FastAPI

from .api_app import build_app
from .api_runtime import build_runtime_repository_from_env

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def create_runtime_app() -> FastAPI:
    """FastAPI app bound to the configured model-backed in-memory repository."""

    return build_app(build_runtime_repository_from_env())


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Rules Beyond V0.2 HTTP backend.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="bind host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="bind port (default 8000)")
    args = parser.parse_args()
    uvicorn.run(create_runtime_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
