#!/usr/bin/env python3
"""Canonical cross-platform dependency installer for Miya."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from dependency_profiles import PROFILE_FILES, ROOT, profile_path


MIN_PYTHON = (3, 11)
VENV_DIR = ROOT / ".venv"


def print_header(version: str, title: str) -> None:
    print("=" * 72)
    print(f"  MIYA v{version} - {title}")
    print("=" * 72)


def miya_version() -> str:
    source = (ROOT / "core" / "version.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*"([^"]+)"', source, re.MULTILINE)
    return match.group(1) if match else "unknown"


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    printable = subprocess.list2cmdline(command) if os.name == "nt" else " ".join(command)
    print(f"[RUN] {printable}")
    completed = subprocess.run(command, cwd=cwd, env=env)
    if completed.returncode:
        raise SystemExit(completed.returncode)


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def ensure_venv(use_venv: bool) -> Path:
    if not use_venv:
        return Path(sys.executable).resolve()

    python = venv_python()
    if not python.exists():
        print(f"[INFO] Creating virtual environment: {VENV_DIR}")
        run([sys.executable, "-m", "venv", str(VENV_DIR)])
    completed = subprocess.run(
        [str(python), "-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"],
        cwd=ROOT,
    )
    if completed.returncode:
        raise SystemExit(f"[ERROR] {VENV_DIR} must use Python 3.11 or newer; recreate it with a supported Python.")
    return python


def find_uv(python: Path) -> str:
    executable = shutil.which("uv")
    if executable:
        return executable

    local_uv = python.parent / ("uv.exe" if os.name == "nt" else "uv")
    if not local_uv.exists():
        print("[INFO] uv not found; installing it into the project virtual environment...")
        run([str(python), "-m", "pip", "install", "uv>=0.8,<1.0"])
    return str(local_uv)


def run_profile_check(python: Path, profile: str, *, quiet: bool = False) -> bool:
    command = [str(python), str(ROOT / "setup/scripts/check_deps.py"), "--profile", profile]
    if quiet:
        command.append("--quiet")
    return subprocess.run(command, cwd=ROOT).returncode == 0


def install_python_dependencies(
    *, python: Path, profile: str, backend: str, upgrade: bool, dry_run: bool
) -> None:
    requirements = profile_path(profile)
    print(f"[INFO] Profile: {profile}")
    print(f"[INFO] Environment: {python}")
    print(f"[INFO] Requirements: {requirements.relative_to(ROOT)}")

    if dry_run:
        print(f"[DRY-RUN] Would install the {profile} profile with {backend}.")
        return

    if not upgrade and run_profile_check(python, profile, quiet=True):
        print(f"[OK] The {profile} profile is already installed and consistent; skipping download.")
        return

    if backend == "uv":
        uv = find_uv(python)
        command = [uv, "pip", "install", "--python", str(python), "-r", str(requirements)]
    else:
        command = [str(python), "-m", "pip", "install", "--progress-bar", "on", "-r", str(requirements)]
    if upgrade:
        command.append("--upgrade")
    run(command)

    print("\n[INFO] Checking installed versions and dependency conflicts...")
    run([str(python), str(ROOT / "setup/scripts/check_deps.py"), "--profile", profile])
    print("\n[INFO] Verifying runtime imports...")
    run([str(python), str(ROOT / "setup/scripts/verify_install.py"), "--profile", profile])

    sync_script = ROOT / "scripts" / "sync_frontend_config.py"
    if sync_script.is_file():
        run([str(python), str(sync_script)])


def _node_version() -> tuple[int, int, int]:
    completed = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", completed.stdout)
    return tuple(int(part) for part in match.groups()) if match else (0, 0, 0)


def install_dsh(*, dry_run: bool) -> None:
    for command in ("node", "npm", "git"):
        if not shutil.which(command):
            raise SystemExit(f"[ERROR] {command} is required for the DeepSeek Harness installation.")
    node_version = _node_version()
    if node_version < (22, 19, 0) or node_version[0] == 23:
        raise SystemExit(f"[ERROR] DeepSeek Harness requires Node.js 22.19+ or 24+ (found {node_version}).")

    if dry_run:
        print("[DRY-RUN] Would initialize and build DeepSeek Harness with its pinned pnpm lockfile.")
        return

    package_json = ROOT / "deepseek-harness/package.json"
    if not package_json.is_file():
        run(["git", "submodule", "update", "--init", "--", "deepseek-harness"])

    pnpm = shutil.which("pnpm")
    if pnpm:
        pnpm_command = [pnpm]
    elif shutil.which("corepack"):
        pnpm_command = ["corepack", "pnpm"]
    else:
        pnpm_command = ["npx", "--yes", "pnpm@11.7.0"]

    dsh_env = {**os.environ, "CI": "true"}
    run([*pnpm_command, "--reporter=append-only", "install", "--frozen-lockfile"], cwd=ROOT / "deepseek-harness", env=dsh_env)
    run([*pnpm_command, "--reporter=append-only", "run", "build"], cwd=ROOT / "deepseek-harness", env=dsh_env)

    tui_dir = ROOT / "tools/dsh-tui"
    tui_binary = tui_dir / "node_modules/dsh-tui/bin/tui.js"
    if not tui_binary.is_file():
        npm_command = ["npm", "ci" if (tui_dir / "package-lock.json").is_file() else "install"]
        run([*npm_command, "--loglevel=info", "--foreground-scripts"], cwd=tui_dir)


def parse_cli(argv: list[str]) -> tuple[str, str, str, bool, bool]:
    backend = "pip"
    use_venv = True
    dry_run = False
    tokens: list[str] = []
    flag_modes = {
        "--full": "full",
        "--minimal": "minimal",
        "--lightweight": "lightweight",
        "--dev": "dev",
        "--check": "check",
        "--upgrade": "upgrade",
        "--dsh": "dsh",
    }
    selected_mode: str | None = None

    for token in argv:
        lowered = token.lower()
        if lowered in {"-h", "--help", "help"}:
            return "help", "full", backend, use_venv, dry_run
        if lowered == "uv" or lowered == "--uv":
            backend = "uv"
        elif lowered == "--no-venv":
            use_venv = False
        elif lowered == "--dry-run":
            dry_run = True
        elif lowered in {"--yes", "-yes"}:
            continue
        elif lowered in flag_modes:
            selected_mode = flag_modes[lowered]
        elif lowered.startswith("-"):
            raise SystemExit(f"[ERROR] Unknown option: {token}")
        else:
            tokens.append(lowered)

    mode = selected_mode or (tokens.pop(0) if tokens else "full")
    if mode == "sync":
        backend = "uv"
        mode = "full"
    profile = tokens.pop(0) if tokens else ("full" if mode in {"check", "upgrade"} else mode)
    if tokens:
        raise SystemExit(f"[ERROR] Unexpected arguments: {' '.join(tokens)}")
    return mode, profile, backend, use_venv, dry_run


def show_help() -> None:
    print(
        """Usage: install.bat|install.sh [uv] [mode] [profile] [options]

Modes:
  full          Complete production profile (default)
  minimal       Core runtime and OpenAI-compatible provider
  lightweight   Core and AI providers without the full feature set
  dev           Full production profile plus development tools
  check [name]  Check an installed profile (default: full)
  upgrade       Upgrade the full production profile
  dsh           Install and build DeepSeek Harness and dsh-tui

Options:
  --uv          Use uv as the installer backend
  --no-venv     Install into the current Python environment
  --dry-run     Validate arguments and show the selected install plan
  -h, --help    Show this help
"""
    )


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < MIN_PYTHON:
        print(f"[ERROR] Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or newer is required.")
        return 1

    raw_args = list(sys.argv[1:] if argv is None else argv)
    mode, profile, backend, use_venv, dry_run = parse_cli(raw_args)
    if mode == "help":
        show_help()
        return 0

    version = miya_version()
    if mode == "dsh":
        print_header(version, "DeepSeek Harness Installer")
        install_dsh(dry_run=dry_run)
        print("\n[OK] DeepSeek Harness is ready.")
        return 0

    if mode not in {*PROFILE_FILES, "check", "upgrade"} or profile not in PROFILE_FILES:
        raise SystemExit(f"[ERROR] Unknown install mode or profile: {mode} {profile}")

    print_header(version, "Dependency Installer")
    python = ensure_venv(use_venv)
    if mode == "check":
        if dry_run:
            print(f"[DRY-RUN] Would check the {profile} profile in {python}.")
            return 0
        return 0 if run_profile_check(python, profile) else 1

    install_python_dependencies(
        python=python,
        profile=profile,
        backend=backend,
        upgrade=mode == "upgrade",
        dry_run=dry_run,
    )
    if dry_run:
        print(f"\n[OK] The {profile} installation plan is valid.")
    else:
        print(f"\n[OK] MIYA {profile} dependencies are ready in {python}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
