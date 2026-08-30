#!/usr/bin/env python3
"""Check one Miya dependency profile against the active Python environment."""

from __future__ import annotations

import argparse
import sys

from dependency_profiles import PROFILE_FILES, check_profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=PROFILE_FILES, default="full")
    parser.add_argument("--no-pip-check", action="store_true", help="Skip pip's transitive conflict check")
    parser.add_argument("--quiet", action="store_true", help="Only return an exit status")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = check_profile(args.profile, run_pip_check=not args.no_pip_check)
    if args.quiet:
        return 0 if result.ok else 1

    print("\n" + "=" * 64)
    print(f"Miya dependency check: {args.profile}")
    print(f"Python: {sys.executable}")
    print("=" * 64)

    if result.missing:
        print("\n[MISSING]")
        for item in result.missing:
            print(f"  - {item}")
    if result.mismatched:
        print("\n[VERSION MISMATCH]")
        for item in result.mismatched:
            print(f"  - {item}")
    if result.conflicts:
        print("\n[ENVIRONMENT CONFLICT]")
        for item in result.conflicts:
            print(f"  - {item}")

    print("\n" + "-" * 64)
    print(
        f"Result: {len(result.installed)} OK | {len(result.missing)} missing | "
        f"{len(result.mismatched)} mismatch | {len(result.conflicts)} conflict"
    )
    print("-" * 64)
    if result.ok:
        print(f"\n[OK] The {args.profile} profile is installed and consistent.")
    else:
        print(f"\nRun: install.bat {args.profile}  (Windows)")
        print(f"     ./install.sh {args.profile} (Linux/macOS)")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
