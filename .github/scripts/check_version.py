"""Check that the version is told the same way everywhere.

Without an argument (push, pull request): `manifest.json` carries a valid
version and `docs/release-notes.md` has a section for it.

With a tag and the pre-release flag (release): additionally, the tag is that
version, a beta is published as a pre-release (HACS only offers those to users
who opted in to betas), and a final release no longer has its notes marked as
in preparation. HACS shows the tag to users, and Home Assistant shows the
manifest version — they must not disagree.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "custom_components" / "renson_arean" / "manifest.json"
NOTES = ROOT / "docs" / "release-notes.md"

# Year.month.sequence, optionally a beta: 2026.9.0, 2026.9.1, 2026.10.0b1.
VERSION = re.compile(r"^\d{4}\.(?:[1-9]|1[0-2])\.\d+(?:b\d+)?$")
IN_PREPARATION = "in preparation"


def main(tag: str | None, prerelease: bool = False) -> list[str]:
    errors: list[str] = []
    version = json.loads(MANIFEST.read_text())["version"]
    if not VERSION.match(version):
        errors.append(f"manifest.json: '{version}' is not year.month.sequence")

    # A beta shares the release notes of the version it leads up to.
    base = re.sub(r"b\d+$", "", version)
    heading = next(
        (
            line
            for line in NOTES.read_text().splitlines()
            if re.match(rf"^## {re.escape(base)}(?:\s|$)", line)
        ),
        None,
    )
    if heading is None:
        errors.append(f"docs/release-notes.md: no section '## {base}'")

    if tag is not None:
        tag_version = tag.removeprefix("v")
        if tag_version != version:
            errors.append(
                f"tag '{tag}' means version '{tag_version}', "
                f"manifest.json says '{version}'"
            )
        is_beta = bool(re.search(r"b\d+$", tag_version))
        if is_beta and not prerelease:
            errors.append(
                f"'{tag}' is a beta but not published as a pre-release: "
                "HACS would offer it to everyone"
            )
        if heading and IN_PREPARATION in heading and not is_beta:
            errors.append(
                f"docs/release-notes.md: '{heading}' is still marked {IN_PREPARATION}"
            )
    return errors


if __name__ == "__main__":
    problems = main(
        sys.argv[1] if len(sys.argv) > 1 else None,
        len(sys.argv) > 2 and sys.argv[2] == "true",
    )
    for problem in problems:
        print(f"::error::{problem}")
    if not problems:
        print("Version consistent.")
    sys.exit(1 if problems else 0)
