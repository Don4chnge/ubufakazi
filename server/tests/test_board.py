"""Syndicate jurisdiction board: syndicates across provinces and station jurisdictions, with station isolation."""
from __future__ import annotations


def test_routing_follows_the_jurisdiction_where_the_victim_was_scammed():
    from ubufakazi_server.stations import DEMO_STATIONS, PROVINCES, jurisdiction_of, route
    assert route("Gauteng", "Vanderbijlpark") == "VER" and route("KwaZulu-Natal", "Ladysmith") == "NCS"
    assert route("Limpopo", None) == "PLK"                       # unknown town: the province default
    assert {p for _, _, p, _ in DEMO_STATIONS} == set(PROVINCES)  # every province has demo stations
    towns = [t.lower() for *_, ts in DEMO_STATIONS for t in ts]
    assert len(towns) == len(set(towns))                          # each town belongs to exactly one jurisdiction
    assert jurisdiction_of("nowhere") is None


def test_national_command_sees_syndicates_across_provinces(login):
    c, _ = login("admin")
    b = c.get("/api/police/intel/board").json()
    assert b["full"] and len(b["provinces"]) == 9
    assert all(p["station_count"] >= 3 for p in b["provinces"])
    big = b["syndicates"][0]
    assert big["victims"] >= 9 and len(big["provinces"]) >= 6 and big["total_amount"] > 0
    assert big["lead"]["code"] in {j["code"] for j in big["jurisdictions"]}
    assert any(m["bank"] == "Ubuntu Trust Bank" for s in b["syndicates"] for m in s["mules"])
    otp = next(s for s in b["syndicates"] if s["scam_type"] == "bank_impersonation")
    assert len(otp["mules"]) == 2                                  # two mule accounts linked through shared phones


def test_station_officer_sees_counts_not_details_for_other_jurisdictions(login):
    c, me = login("officer.joburg")
    b = c.get("/api/police/intel/board").json()
    assert not b["full"] and b["totals"]["amount"] is None
    for s in b["syndicates"]:
        assert s["your_victims"] >= 1 and s["total_amount"] is None
        for j in s["jurisdictions"]:
            if not j["own"]:
                assert j["amount"] is None and j["towns"] == [] and j["references"] == []


def test_bank_staff_cannot_open_the_board(login):
    c, _ = login("bank.reviewer")
    assert c.get("/api/police/intel/board").status_code == 403
