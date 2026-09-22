#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDON_CONFIG_PATH = REPO_ROOT / "addons/github-config-sync/config.yaml"
CHANGELOG_PATH = REPO_ROOT / "CHANGELOG.md"

VERSION_PATTERN = re.compile(r'^version:\s*["\']?([^"\']+)["\']?\s*$', re.MULTILINE)
SIMPLE_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+")
PRE_RELEASE_PATTERN = re.compile(r"-\d+[0-9A-Za-z.\-]*$")


def read_version() -> str:
    """Read the add-on version from config.yaml (single source of truth)."""
    text = ADDON_CONFIG_PATH.read_text(encoding="utf-8")
    match = VERSION_PATTERN.search(text)
    if match is None:
        raise SystemExit(f"Could not read version from {ADDON_CONFIG_PATH}")
    version = match.group(1)
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?", version):
        raise SystemExit(f"Unexpected version format in config.yaml: {version}")
    return version


def is_prerelease(version: str) -> bool:
    return PRE_RELEASE_PATTERN.search(version) is not None


def read_changelog_section(changelog: Path, version: str) -> str:
    """Return the changelog section body for the given version."""
    content = changelog.read_text(encoding="utf-8")
    match = re.search(rf"(?m)^## {re.escape(version)}[ \t]*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if match is None:
        raise SystemExit(f"Could not find '## {version}' section in {changelog}")
    return match.group(1).strip() + "\n"


def current_branch() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit("Not in a git repository")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish the current version's changelog section as a GitHub release (vX.Y.Z); pre-release versions are marked --prerelease.",
    )
    parser.add_argument(
        "--version",
        help="Version to release (defaults to the add-on version in config.yaml).",
    )
    parser.add_argument(
        "--branch",
        help="Branch the release tag should point at (defaults to the current branch).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only print the release notes that would be published; do not create anything.",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    tag = f"v{version}"
    prerelease = is_prerelease(version)
    branch = args.branch or current_branch()
    body = read_changelog_section(CHANGELOG_PATH, version)

    if args.check:
        print(f"tag:        {tag}")
        print(f"branch:     {branch}")
        print(f"prerelease: {prerelease}")
        print("notes:")
        print(body)
        return 0

    try:
        release_args = [
            "gh",
            "release",
            "create",
            tag,
            "--title",
            tag,
            "--target",
            branch,
            "--notes",
            body,
        ]
        if prerelease:
            release_args.append("--prerelease")
        subprocess.run(release_args, check=True)
    except FileNotFoundError as err:
        raise SystemExit("The GitHub CLI (gh) is required to publish releases") from err
    except subprocess.CalledProcessError as err:
        raise SystemExit(f"gh release create failed: {err}") from err

    print(f"published: {tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())