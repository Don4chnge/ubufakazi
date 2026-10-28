"""Every file in the sample evidence kit is accepted by the evidence pipeline (all categories, all formats)."""
from __future__ import annotations

import pytest

from conftest import KIT

SAMPLES = KIT / "samples"
CATS = {"01": "scam", "02": "banking_fraud", "03": "scam", "04": "scam", "05": "scam"}


@pytest.mark.skipif(not SAMPLES.exists(), reason="sample kit not built (python3 tools/make_sample_kit.py)")
@pytest.mark.parametrize("folder", sorted(p.name for p in SAMPLES.iterdir() if p.is_dir()) if SAMPLES.exists() else [])
def test_category_samples_are_accepted(app, folder):
    from ubufakazi_server import services
    from ubufakazi_server.db import SessionLocal
    from ubufakazi_server.models import Report
    files = [(p.read_bytes(), p.name, "") for p in sorted((SAMPLES / folder).iterdir()) if p.name != "README.txt"]
    res = services.submit_report(files=files, source="web", category=CATS[folder[:2]], language="en",
                                 province="Gauteng", town="Johannesburg", description="Sample kit upload test for " + folder,
                                 consent_given=True)
    assert res["rejected"] == [], res["rejected"]
    services.process_report(res["id"])
    db = SessionLocal()
    try:
        r = db.get(Report, res["id"])
        assert r.processing_status == "ready" and len(r.evidence) == len(files)
        kinds = {e.detected_type for e in r.evidence}
        if any(n.endswith(".mp3") for _, n, _ in files):
            assert "mp3" in kinds
        if any(n.endswith(".mp4") for _, n, _ in files):
            assert "mp4" in kinds
    finally:
        db.close()
