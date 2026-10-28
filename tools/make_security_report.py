"""Runs the test suite and writes the summary shown on /security (server/ubufakazi_server/web/security-tests.json)."""
from __future__ import annotations

import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

SERVER = pathlib.Path(__file__).resolve().parent.parent / "server"
r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:warnings"], cwd=SERVER, capture_output=True, text=True)
last = [l for l in r.stdout.splitlines() if re.search(r"\d+ (passed|failed)", l)][-1]
num = lambda k: int(m.group(1)) if (m := re.search(rf"(\d+) {k}", last)) else 0  # noqa: E731
files = len(list((SERVER / "tests").glob("test_*.py")))
out = {"passed": num("passed"), "failed": num("failed"), "skipped": num("skipped"), "test_files": files,
       "python": sys.version.split()[0], "run_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
(SERVER / "ubufakazi_server" / "web" / "security-tests.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(out)
sys.exit(0 if out["failed"] == 0 else 1)
