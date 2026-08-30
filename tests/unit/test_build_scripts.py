from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build.py"
SPEC = importlib.util.spec_from_file_location("miya_build", BUILD_SCRIPT)
assert SPEC and SPEC.loader
build = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build
SPEC.loader.exec_module(build)


@pytest.mark.parametrize(
    ("args", "mode", "dry_run"),
    [([], "all", False), (["menu"], "menu", False), (["dsh"], "dsh", False), (["desktop", "--dry-run"], "desktop", True)],
)
def test_build_modes(args: list[str], mode: str, dry_run: bool) -> None:
    parsed = build.parse_args(args)
    assert parsed.mode == mode
    assert parsed.dry_run is dry_run


def test_build_rejects_unknown_mode() -> None:
    with pytest.raises(SystemExit):
        build.parse_args(["cce"])


def test_non_interactive_menu_defaults_to_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(build.sys.stdin, "isatty", lambda: False)
    assert build.choose_mode() == "all"


def test_run_resolves_windows_bare_executables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, list[str]] = {}

    def fake_run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None):
        captured["cmd"] = cmd

        class Completed:
            returncode = 0

        return Completed()

    monkeypatch.setattr(build.subprocess, "run", fake_run)
    monkeypatch.setattr(build.shutil, "which", lambda name: r"C:\Program Files\nodejs\npm.cmd" if name == "npm" else None)

    build.run(["npm", "ci"], cwd=tmp_path)

    assert captured["cmd"][0] == r"C:\Program Files\nodejs\npm.cmd"
    assert captured["cmd"][1:] == ["ci"]


def test_dsh_toolchain_versions_are_pinned() -> None:
    assert build.PNPM_VERSION == "11.7.0"
    assert build.MIN_NODE == (22, 19, 0)
    assert '"packageManager": "pnpm@11.7.0"' in (ROOT / "deepseek-harness" / "package.json").read_text()
