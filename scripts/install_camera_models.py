"""Download the opt-in Miya Vision camera models from model_catalog.json."""

from __future__ import annotations

import argparse
import json
import shutil
import ssl
import sys
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install explicitly selected local camera ONNX models")
    parser.add_argument("--accept-licenses", action="store_true", help="confirm that you reviewed each upstream license")
    parser.add_argument("--model", action="append", dest="models", help="filename to install; repeatable")
    args = parser.parse_args()
    if not args.accept_licenses:
        print("Refusing download: pass --accept-licenses after reviewing model_catalog.json.", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    catalog_path = root / "mcpserver" / "screen_vision" / "model_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    destination = root / "models" / "camera_vision"
    destination.mkdir(parents=True, exist_ok=True)
    selected = set(args.models or [name for name, entry in catalog["models"].items() if entry.get("url")])
    unknown = selected - set(catalog["models"])
    if unknown:
        print(f"Unknown model(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2
    context = ssl.create_default_context()
    for filename in selected:
        entry = catalog["models"][filename]
        if not entry.get("url"):
            print(f"Skipping {filename}: no verified public URL; install this model manually after license review.")
            continue
        target = destination / filename
        print(f"Downloading {entry['name']} -> {target}")
        with urllib.request.urlopen(entry["url"], context=context, timeout=120) as response, target.with_suffix(".download").open("wb") as handle:
            shutil.copyfileobj(response, handle)
        target.with_suffix(".download").replace(target)
    print("Camera models installed. Restart the MCP service, then refresh capabilities.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
