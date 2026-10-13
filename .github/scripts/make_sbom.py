"""Write the SBOM of a release (SEC-04): what is in the integration.

The integration has no dependencies, so the list is mostly its own files, each
with a SHA-256. Whatever `manifest.json` declares under `requirements` is
listed as a library. The file is CycloneDX 1.6 and carries no timestamp: the
same commit always gives the same file, so a reader can make it again from the
tag and compare.

    python3 .github/scripts/make_sbom.py sbom.cdx.json
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPONENT = "custom_components/renson_arean"


def _files() -> list[str]:
    """Return what git has under the integration: that is what HACS hands out."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", COMPONENT],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return sorted(path for path in listed.split("\0") if path)


def _library(requirement: str) -> dict:
    name, _, version = requirement.partition("==")
    library = {"type": "library", "bom-ref": requirement, "name": name}
    if version:
        library["version"] = version
        library["purl"] = f"pkg:pypi/{re.sub(r'[-_.]+', '-', name).lower()}@{version}"
    return library


def build() -> dict:
    manifest = json.loads((ROOT / COMPONENT / "manifest.json").read_text())
    files = [
        {
            "type": "file",
            "bom-ref": path,
            "name": path,
            "hashes": [
                {
                    "alg": "SHA-256",
                    "content": hashlib.sha256((ROOT / path).read_bytes()).hexdigest(),
                }
            ],
        }
        for path in _files()
    ]
    libraries = [_library(requirement) for requirement in manifest["requirements"]]
    content = json.dumps([manifest["version"], libraries, files], sort_keys=True)
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, content)}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "bom-ref": manifest["domain"],
                "name": manifest["domain"],
                "version": manifest["version"],
                "properties": [
                    # Parts of Home Assistant itself, not packages.
                    {"name": "homeassistant:dependencies", "value": ",".join(manifest["dependencies"])},
                ],
            }
        },
        "components": libraries + files,
    }


if __name__ == "__main__":
    out = Path(sys.argv[1])
    sbom = build()
    out.write_text(json.dumps(sbom, indent=2) + "\n")
    print(f"{out}: {len(sbom['components'])} components")
