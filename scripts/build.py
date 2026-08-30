#!/usr/bin/env python3
"""Canonical cross-platform builder for Miya's DSH and Electron frontends."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DSH_DIR = ROOT / "deepseek-harness"
DSH_PACKAGE = DSH_DIR / "package.json"
DSH_TUI_DIR = ROOT / "tools" / "dsh-tui"
FRONTEND_DIR = ROOT / "miya_frontend"
MIN_NODE = (22, 19, 0)
PNPM_VERSION = "11.7.0"


def command_text(command: list[str]) -> str:
    return subprocess.list2cmdline(command) if os.name == "nt" else " ".join(command)


def resolve_command(command: list[str]) -> list[str]:
    if os.name != "nt" or not command:
        return command

    executable = command[0]
    if not executable or executable.startswith("-"):
        return command
    if os.path.sep in executable or (os.path.altsep and os.path.altsep in executable):
        return command

    candidate = shutil.which(executable)
    if not candidate:
        return command

    resolved = [candidate, *command[1:]]
    return resolved


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None, dry_run: bool = False) -> None:
    if cwd == ROOT:
        location = "."
    else:
        try:
            location = str(cwd.relative_to(ROOT))
        except ValueError:
            location = str(cwd)
    command = resolve_command(command)
    print(f"[RUN] {command_text(command)}  (cwd={location})")
    if dry_run:
        return
    completed = subprocess.run(command, cwd=cwd, env=env)
    if completed.returncode:
        print(f"\n[ERROR] Command failed with exit code {completed.returncode}:")
        print(f"  Command: {command_text(command)}")
        print(f"  Working directory: {location}")
        print("")
        raise SystemExit(completed.returncode)


def require_command(name: str) -> str:
    executable = shutil.which(name)
    if not executable:
        raise SystemExit(f"[ERROR] {name} is required but was not found on PATH.")
    return executable


def run_npm_install(cwd: Path, *, env: dict[str, str] | None = None, dry_run: bool = False) -> None:
    """Run npm ci with automatic fallback to npm install on Windows EPERM errors."""
    lockfile = cwd / "package-lock.json"
    install_ci = ["npm", "ci", "--loglevel=info", "--foreground-scripts", "--legacy-peer-deps"]
    install_fallback = ["npm", "install", "--loglevel=info", "--foreground-scripts", "--legacy-peer-deps"]

    if not lockfile.is_file():
        run(install_fallback, cwd=cwd, env=env, dry_run=dry_run)
        return

    try:
        run(install_ci, cwd=cwd, env=env, dry_run=dry_run)
    except SystemExit as exc:
        if os.name != "nt" or exc.code not in (4294963248, -4048, 4048):
            raise
        print(f"\n[WARN] npm ci failed (EPERM on native module). Retrying with npm install...")
        run(install_fallback, cwd=cwd, env=env, dry_run=dry_run)


def node_version() -> tuple[int, int, int]:
    node = require_command("node")
    completed = subprocess.run([node, "--version"], capture_output=True, text=True, check=True)
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", completed.stdout)
    if not match:
        raise SystemExit(f"[ERROR] Unable to parse Node.js version: {completed.stdout.strip()}")
    return tuple(int(part) for part in match.groups())


def validate_node() -> None:
    version = node_version()
    supported = (version >= MIN_NODE and version[0] == 22) or version[0] >= 24
    if not supported:
        raise SystemExit(
            "[ERROR] DeepSeek Harness requires Node.js 22.19+ (22.x) or 24+. "
            f"Found {version[0]}.{version[1]}.{version[2]}."
        )
    print(f"[OK] Node.js {version[0]}.{version[1]}.{version[2]} is supported.")


def pnpm_command() -> list[str]:
    pnpm = shutil.which("pnpm")
    if pnpm:
        return [pnpm]
    if shutil.which("npx"):
        return ["npx", "--yes", f"pnpm@{PNPM_VERSION}"]
    corepack = shutil.which("corepack")
    if corepack:
        return [corepack, "pnpm"]
    raise SystemExit("[ERROR] pnpm, corepack, or npx is required for the DSH build.")


def ensure_dsh_submodule(*, dry_run: bool) -> None:
    if DSH_PACKAGE.is_file():
        return
    require_command("git")
    print("[INFO] Initializing the DeepSeek Harness submodule...")
    run(["git", "submodule", "update", "--init", "--", "deepseek-harness"], dry_run=dry_run)
    if not dry_run and not DSH_PACKAGE.is_file():
        raise SystemExit("[ERROR] DeepSeek Harness submodule is still unavailable after initialization.")


def check_dsh_web_build(*, dry_run: bool = False) -> None:
    dsh_bin = DSH_DIR / "apps" / "cli" / "lib" / "bin.js"
    if dsh_bin.is_file():
        print(f"[OK] DSH Web runtime is present: {dsh_bin}")
        return

    print("\n[WARN] DSH Web startup is not ready: deepseek-harness has not been built yet.")
    print("  This is required for Electron to launch the DSH Web host.")
    print("  Please run one of the following before launching DSH Web:")
    print("    1) build.bat -> [1] Build DSH (DeepSeek Harness + dsh-tui)")
    print("    2) cd deepseek-harness && pnpm install && pnpm run build")
    print("")
    if not dry_run:
        raise SystemExit("[ERROR] DSH Web startup will fail until deepseek-harness is built.")


def build_dsh(*, dry_run: bool) -> None:
    print("\n=== Building DeepSeek Harness ===")
    ensure_dsh_submodule(dry_run=dry_run)
    pnpm = pnpm_command()
    env = {
        **os.environ,
        "CI": "true",
        "COREPACK_ENABLE_AUTO_PIN": "0",
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
        "npm_config_registry": "https://registry.npmjs.org/",
        # Keep Corepack's download cache inside the writable project tree.
        "COREPACK_HOME": str(ROOT / ".cache" / "corepack"),
    }
    install_args = [*pnpm, "--reporter=append-only", "install", "--frozen-lockfile", "--registry=https://registry.npmjs.org/"]
    build_args = [*pnpm, "--reporter=append-only", "run", "build"]
    run(install_args, cwd=DSH_DIR, env=env, dry_run=dry_run)
    run(build_args, cwd=DSH_DIR, env=env, dry_run=dry_run)

    if not DSH_TUI_DIR.joinpath("package.json").is_file():
        raise SystemExit(f"[ERROR] dsh-tui package manifest is missing: {DSH_TUI_DIR}")

    tui_lock = DSH_TUI_DIR / "package-lock.json"
    if tui_lock.is_file() and "registry.npmmirror.com" in tui_lock.read_text(encoding="utf-8", errors="ignore"):
        print("[WARN] dsh-tui lockfile was pinned to registry.npmmirror.com; regenerating it from the official npm registry.")
        backup = DSH_TUI_DIR / "package-lock.json.bak"
        if backup.exists():
            backup.unlink()
        tui_lock.rename(backup)
        tui_lock = DSH_TUI_DIR / "package-lock.json"

    npm_env = {
        **os.environ,
        "NPM_CONFIG_REGISTRY": "https://registry.npmjs.org/",
        "npm_config_registry": "https://registry.npmjs.org/",
    }
    run_npm_install(DSH_TUI_DIR, env=npm_env, dry_run=dry_run)
    tui_binary = DSH_TUI_DIR / "node_modules" / "dsh-tui" / "bin" / "tui.js"
    if not dry_run and not tui_binary.is_file():
        raise SystemExit("[ERROR] dsh-tui installation completed but tui.js is missing.")
    print("[OK] DSH and dsh-tui are ready.")
    check_dsh_web_build(dry_run=dry_run)


def build_desktop(*, dry_run: bool) -> None:
    print("\n=== Building Electron Desktop ===")
    if not (FRONTEND_DIR / "package.json").is_file():
        raise SystemExit(f"[ERROR] Frontend package manifest is missing: {FRONTEND_DIR}")

    check_dsh_web_build(dry_run=dry_run)

    registry = "https://registry.npmjs.org/"
    npm_env = {
        **os.environ,
        "NPM_CONFIG_REGISTRY": registry,
        "npm_config_registry": registry,
    }

    lockfile = FRONTEND_DIR / "package-lock.json"
    if lockfile.is_file() and "registry.npmmirror.com" in lockfile.read_text(encoding="utf-8", errors="ignore"):
        print("[WARN] package-lock.json was pinned to registry.npmmirror.com; regenerating the frontend lock from the official npm registry.")
        backup = FRONTEND_DIR / "package-lock.json.bak"
        if backup.exists():
            backup.unlink()
        lockfile.rename(backup)
        lockfile = FRONTEND_DIR / "package-lock.json"

    run_npm_install(FRONTEND_DIR, env=npm_env, dry_run=dry_run)

    esbuild_installer = FRONTEND_DIR / "node_modules" / "esbuild" / "install.js"
    if dry_run or esbuild_installer.is_file():
        run(["node", "node_modules/esbuild/install.js"], cwd=FRONTEND_DIR, env=npm_env, dry_run=dry_run)
    run(["npm", "run", "build"], cwd=FRONTEND_DIR, env=npm_env, dry_run=dry_run)
    print("[OK] Electron desktop build complete.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", choices=("menu", "all", "dsh", "desktop"), default="all")
    parser.add_argument("--dry-run", action="store_true", help="Print the build plan without running commands")
    return parser.parse_args(argv)


def choose_mode() -> str:
    if not sys.stdin.isatty():
        print("[INFO] Non-interactive input detected; selecting all builds.")
        return "all"
    print("\n" + "=" * 48)
    print("             MIYA Build Menu")
    print("=" * 48)
    print("  [1] Build DSH (DeepSeek Harness + dsh-tui)")
    print("  [2] Build Desktop (Electron frontend)")
    print("  [3] Build All (DSH + Desktop)")
    print("  [Q] Quit")
    print("=" * 48)
    try:
        choice = input("Select [1/2/3/Q]: ").strip().lower()
    except EOFError:
        return "all"
    return {"1": "dsh", "2": "desktop", "3": "all", "q": "quit"}.get(choice, "invalid")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mode = choose_mode() if args.mode == "menu" else args.mode
    if mode == "quit":
        print("[INFO] Build cancelled.")
        return 0
    if mode == "invalid":
        print("[ERROR] Invalid build selection.")
        return 2
    require_command("npm")
    validate_node()
    sync_script = ROOT / "scripts" / "sync_frontend_config.py"
    if sync_script.is_file():
        run([sys.executable, str(sync_script)], dry_run=args.dry_run)

    if mode in {"all", "dsh"}:
        build_dsh(dry_run=args.dry_run)
    if mode in {"all", "desktop"}:
        build_desktop(dry_run=args.dry_run)

    print("\n[OK] MIYA build completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
