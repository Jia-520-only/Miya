#!/usr/bin/env python3
"""Verify that the selected Miya profile exposes its expected import modules."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import sys

from dependency_profiles import PROFILE_FILES, canonicalize_name, load_profile


PIP_TO_IMPORT = {
    "beautifulsoup4": "bs4",
    "discord-py": "discord",
    "edge-tts": "edge_tts",
    "faiss-cpu": "faiss",
    "google-genai": "google.genai",
    "lark-oapi": "lark_oapi",
    "line-bot-sdk": "linebot",
    "mattermostdriver": "mattermostdriver",
    "pillow": "PIL",
    "pycryptodome": "Crypto",
    "pyjwt": "jwt",
    "pymupdf": "pymupdf",
    "pytest-asyncio": "pytest_asyncio",
    "pytest-cov": "pytest_cov",
    "python-docx": "docx",
    "python-dotenv": "dotenv",
    "python-magic": "magic",
    "python-magic-bin": "magic",
    "python-multipart": "multipart",
    "python-pptx": "pptx",
    "python-ripgrep": "ripgrep",
    "python-telegram-bot": "telegram",
    "pyserial": "serial",
    "pyyaml": "yaml",
    "qq-botpy": "botpy",
    "rank-bm25": "rank_bm25",
    "scikit-learn": "sklearn",
    "sentence-transformers": "sentence_transformers",
    "slack-bolt": "slack_bolt",
    "slack-sdk": "slack_sdk",
    "sphinx-rtd-theme": "sphinx_rtd_theme",
    "typing-extensions": "typing_extensions",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILE_FILES, default="full")
    return parser.parse_args()


def import_name(distribution_name: str) -> str:
    return PIP_TO_IMPORT.get(distribution_name, distribution_name.replace("-", "_"))


def main() -> int:
    args = parse_args()
    requirements = load_profile(args.profile)
    distribution_modules: dict[str, set[str]] = {}
    for module_name, distributions in importlib.metadata.packages_distributions().items():
        for distribution_name in distributions:
            key = canonicalize_name(distribution_name)
            distribution_modules.setdefault(key, set()).add(module_name)
    missing: list[tuple[str, str]] = []
    found: list[tuple[str, str]] = []

    for distribution_name in requirements:
        candidates = [import_name(distribution_name), *sorted(distribution_modules.get(distribution_name, set()))]
        module_name = candidates[0]
        available = False
        for candidate in dict.fromkeys(candidates):
            try:
                if importlib.util.find_spec(candidate) is not None:
                    module_name = candidate
                    available = True
                    break
            except (ImportError, ModuleNotFoundError, ValueError):
                continue
        target = found if available else missing
        target.append((distribution_name, module_name))

    print("\n" + "=" * 64)
    print(f"Miya runtime import verification: {args.profile}")
    print(f"Python: {sys.executable}")
    print("=" * 64)
    if missing:
        print("\n[IMPORT TARGET MISSING]")
        for distribution_name, module_name in missing:
            print(f"  - {distribution_name} -> {module_name}")

    print("\n" + "-" * 64)
    print(f"Result: {len(found)} import targets found | {len(missing)} missing")
    print("-" * 64)
    if missing:
        print(f"\n[FAIL] The {args.profile} profile is not runtime-ready.")
        return 1
    print(f"\n[OK] The {args.profile} profile is runtime-ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
