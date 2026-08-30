#!/usr/bin/env python3
"""Sync config/frontend.json to miya_frontend/.env."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "frontend.json"
ENV_PATH = ROOT / "miya_frontend" / ".env"


def main() -> None:
    if not CONFIG_PATH.exists():
        print(f"[WARN] {CONFIG_PATH} not found, skipping")
        return

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    api = config.get("api_server", {})
    port = api.get("port", 8000)
    host = api.get("host", "127.0.0.1")

    ENV_PATH.write_text(
        f"VITE_API_PORT={port}\n"
        f"VITE_API_HOST={host}\n",
        encoding="utf-8",
    )
    print(f"[OK] Synced frontend config: {host}:{port} -> {ENV_PATH}")


if __name__ == "__main__":
    main()
