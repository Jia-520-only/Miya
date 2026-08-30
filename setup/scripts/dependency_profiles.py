"""Shared dependency profile parsing and validation helpers for Miya installers."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
except ImportError:  # packaging is bundled with pip in a fresh virtual environment.
    from pip._vendor.packaging.requirements import Requirement
    from pip._vendor.packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[2]
REQUIREMENTS_DIR = ROOT / "setup" / "requirements"

PROFILE_FILES = {
    "minimal": REQUIREMENTS_DIR / "minimal.txt",
    "lightweight": REQUIREMENTS_DIR / "lightweight.txt",
    "full": REQUIREMENTS_DIR / "full.txt",
    "dev": REQUIREMENTS_DIR / "dev.txt",
    "desktop": REQUIREMENTS_DIR / "desktop.txt",
}


@dataclass(frozen=True)
class RequirementSource:
    requirement: Requirement
    source: Path
    line_number: int


@dataclass
class ProfileCheckResult:
    profile: str
    installed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatched: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.missing or self.mismatched or self.conflicts)


def profile_path(profile: str) -> Path:
    try:
        return PROFILE_FILES[profile]
    except KeyError as exc:
        choices = ", ".join(PROFILE_FILES)
        raise ValueError(f"Unknown dependency profile {profile!r}; choose one of: {choices}") from exc


def _strip_inline_comment(line: str) -> str:
    marker = line.find(" #")
    return line[:marker].rstrip() if marker >= 0 else line


def _read_requirement_sources(path: Path, seen: set[Path]) -> list[RequirementSource]:
    path = path.resolve()
    if path in seen:
        return []
    if not path.is_file():
        raise FileNotFoundError(f"Requirements file not found: {path}")

    seen.add(path)
    result: list[RequirementSource] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = _strip_inline_comment(raw_line.strip())
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement ")):
            include = line.split(maxsplit=1)[1].strip()
            result.extend(_read_requirement_sources(path.parent / include, seen))
            continue
        if line.startswith("-"):
            continue

        try:
            requirement = Requirement(line)
        except Exception as exc:
            raise ValueError(f"Invalid requirement at {path}:{line_number}: {line}") from exc
        if requirement.marker is None or requirement.marker.evaluate():
            result.append(RequirementSource(requirement, path, line_number))
    return result


def load_profile(profile: str) -> OrderedDict[str, list[RequirementSource]]:
    grouped: OrderedDict[str, list[RequirementSource]] = OrderedDict()
    for item in _read_requirement_sources(profile_path(profile), set()):
        name = canonicalize_name(item.requirement.name)
        grouped.setdefault(name, []).append(item)
    return grouped


def check_profile(profile: str, *, run_pip_check: bool = True) -> ProfileCheckResult:
    result = ProfileCheckResult(profile=profile)
    for name, sources in load_profile(profile).items():
        display_name = sources[0].requirement.name
        try:
            installed_version = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            constraints = ", ".join(str(item.requirement.specifier) for item in sources if item.requirement.specifier)
            result.missing.append(f"{display_name} {constraints}".strip())
            continue

        failed = [str(item.requirement.specifier) for item in sources if installed_version not in item.requirement.specifier]
        if failed:
            result.mismatched.append(f"{display_name}=={installed_version} (need {' and '.join(failed)})")
        else:
            result.installed.append(f"{display_name}=={installed_version}")

    if run_pip_check:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        if completed.returncode:
            result.conflicts.extend(
                line.strip() for line in (completed.stdout + completed.stderr).splitlines() if line.strip()
            )
    return result

