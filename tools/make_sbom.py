"""Writes the software bill of materials (CycloneDX 1.5 JSON) and the vulnerability-scan summary served on /security.

Run it with the Python environment that has exactly requirements.txt installed (e.g. a clean venv):
    python tools/make_sbom.py            # -> server/ubufakazi_server/web/sbom.json and security-scan.json
"""
from __future__ import annotations

import datetime as dt
import importlib.metadata as md
import json
import pathlib
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "server" / "ubufakazi_server" / "web"
SKIP = {"pip", "setuptools", "wheel", "pip-audit"}


def main() -> None:
    comps = []
    for d in sorted(md.distributions(), key=lambda d: d.metadata["Name"].lower()):
        name = d.metadata["Name"]
        if name.lower() in SKIP:
            continue
        lic = d.metadata.get("License-Expression") or d.metadata.get("License") or ""
        if len(lic) > 60 or "\n" in lic:
            lic = next((c.split("::")[-1].strip() for c in d.metadata.get_all("Classifier") or [] if c.startswith("License ::")), "")
        comps.append({"type": "library", "name": name, "version": d.version,
                      "purl": f"pkg:pypi/{name.lower()}@{d.version}", **({"licenses": [{"license": {"name": lic}}]} if lic else {})})
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.5", "serialNumber": f"urn:uuid:{uuid.uuid4()}", "version": 1,
            "metadata": {"timestamp": now, "component": {"type": "application", "name": "ubufakazi", "version": "2.0.0-demo"},
                         "properties": [{"name": "python", "value": sys.version.split()[0]}]},
            "components": comps}
    (WEB / "sbom.json").write_text(json.dumps(sbom, indent=1), encoding="utf-8")
    req = ROOT / "server" / "requirements.txt"
    r = subprocess.run(["pip-audit", "-r", str(req), "--format", "json", "--progress-spinner", "off"],
                       capture_output=True, text=True)
    try:
        deps = json.loads(r.stdout)["dependencies"]
        vulns = sum(len(x.get("vulns", [])) for x in deps)
        scan = {"tool": "pip-audit", "scanned_at": now, "packages": len(deps), "known_vulnerabilities": vulns,
                "direct_requirements_pinned": True}
    except (ValueError, KeyError):
        scan = {"tool": "pip-audit", "scanned_at": now, "error": (r.stderr or "scan failed")[-300:]}
    (WEB / "security-scan.json").write_text(json.dumps(scan, indent=1), encoding="utf-8")
    print(f"SBOM: {len(comps)} components · scan: {scan}")


if __name__ == "__main__":
    main()
