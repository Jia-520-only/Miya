from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "setup" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from dependency_profiles import canonicalize_name, load_profile  # noqa: E402
from install import parse_cli  # noqa: E402

try:
    from packaging.requirements import Requirement
except ImportError:
    from pip._vendor.packaging.requirements import Requirement


def _requirement_signatures(path: Path) -> set[tuple[str, str, str, tuple[str, ...]]]:
    signatures = set()
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        requirement = Requirement(line)
        signatures.add(
            (
                canonicalize_name(requirement.name),
                str(requirement.specifier),
                str(requirement.marker or ""),
                tuple(sorted(requirement.extras)),
            )
        )
    return signatures


def _pyproject_signatures(items: list[str]) -> set[tuple[str, str, str, tuple[str, ...]]]:
    signatures = set()
    for item in items:
        requirement = Requirement(item)
        signatures.add(
            (
                canonicalize_name(requirement.name),
                str(requirement.specifier),
                str(requirement.marker or ""),
                tuple(sorted(requirement.extras)),
            )
        )
    return signatures


def test_profiles_expand_as_expected() -> None:
    minimal = set(load_profile("minimal"))
    lightweight = set(load_profile("lightweight"))
    full = set(load_profile("full"))
    dev = set(load_profile("dev"))
    desktop = set(load_profile("desktop"))

    assert minimal < lightweight < full < dev
    assert "pytest" not in full
    assert "pytest" in dev
    assert "chromadb" in full
    assert "chromadb" in desktop
    assert "google-genai" in lightweight
    assert "google-generativeai" not in full


def test_platform_markers_select_one_magic_distribution() -> None:
    full = set(load_profile("full"))
    magic_packages = {name for name in full if name in {"python-magic", "python-magic-bin"}}
    expected = {"python-magic-bin"} if sys.platform == "win32" else {"python-magic"}
    assert magic_packages == expected


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ([], ("full", "full", "pip", True, False)),
        (["uv", "minimal"], ("minimal", "minimal", "uv", True, False)),
        (["check", "dev"], ("check", "dev", "pip", True, False)),
        (["--dev", "--dry-run"], ("dev", "dev", "pip", True, True)),
        (["upgrade", "--no-venv"], ("upgrade", "full", "pip", False, False)),
        (["uv", "sync"], ("full", "full", "uv", True, False)),
    ],
)
def test_installer_cli(arguments: list[str], expected: tuple[str, str, str, bool, bool]) -> None:
    assert parse_cli(arguments) == expected


def test_pyproject_matches_canonical_dependency_categories() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]
    extras = project["optional-dependencies"]

    assert _pyproject_signatures(project["dependencies"]) == _requirement_signatures(
        ROOT / "setup" / "dependencies" / "base.txt"
    )

    mappings = {
        "ai": "ai.txt",
        "database": "database.txt",
        "office": "office.txt",
        "network": "network.txt",
        "tts": "tts.txt",
        "viz": "viz.txt",
        "qq-extras": "qq_extras.txt",
        "platform": "platform_adapters.txt",
        "observability": "observability.txt",
        "win32": "win32.txt",
    }
    for extra, filename in mappings.items():
        assert _pyproject_signatures(extras[extra]) == _requirement_signatures(
            ROOT / "setup" / "dependencies" / filename
        ), extra

    assert _pyproject_signatures(pyproject["dependency-groups"]["dev"]) == _requirement_signatures(
        ROOT / "setup" / "dependencies" / "dev.txt"
    )


def test_obsolete_environment_snapshot_is_not_used_as_a_lockfile() -> None:
    assert not (ROOT / "setup" / "requirements-lock.txt").exists()
