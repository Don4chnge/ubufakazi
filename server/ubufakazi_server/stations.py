"""Fictional demonstration stations and report routing.

These are NOT SAPS stations. They exist only to demonstrate station-level routing and
access control. A real deployment needs SAPS approval and verified receiving channels.
"""
from __future__ import annotations

PROVINCES = ["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga",
             "North West", "Northern Cape", "Western Cape"]

DEMO_STATIONS = [
    # code, name, province, towns (first station listed for a province is its default)
    ("MTH", "Demo Station · Mthatha", "Eastern Cape", ["Mthatha", "Ngcobo", "Mqanduli", "Libode"]),
    ("GQB", "Demo Station · Gqeberha", "Eastern Cape", ["Gqeberha", "East London", "Kariega", "Makhanda"]),
    ("BFN", "Demo Station · Bloemfontein", "Free State", ["Bloemfontein", "Welkom", "Bethlehem", "Botshabelo"]),
    ("JHB", "Demo Station · Johannesburg Central", "Gauteng", ["Johannesburg", "Soweto", "Sandton", "Randburg"]),
    ("ALB", "Demo Station · Alberton", "Gauteng", ["Alberton", "Germiston", "Boksburg", "Kempton Park"]),
    ("PTA", "Demo Station · Pretoria Central", "Gauteng", ["Pretoria", "Centurion", "Soshanguve", "Mamelodi"]),
    ("DBN", "Demo Station · Durban Central", "KwaZulu-Natal", ["Durban", "Umlazi", "Pinetown", "Pietermaritzburg"]),
    ("PLK", "Demo Station · Polokwane", "Limpopo", ["Polokwane", "Thohoyandou", "Tzaneen", "Mokopane"]),
    ("MBB", "Demo Station · Mbombela", "Mpumalanga", ["Mbombela", "eMalahleni", "Secunda", "Middelburg"]),
    ("MHK", "Demo Station · Mahikeng", "North West", ["Mahikeng", "Rustenburg", "Klerksdorp", "Brits"]),
    ("KIM", "Demo Station · Kimberley", "Northern Cape", ["Kimberley", "Upington", "Kuruman", "Springbok"]),
    ("CPT", "Demo Station · Cape Town Central", "Western Cape", ["Cape Town", "Khayelitsha", "Bellville", "Mitchells Plain"]),
]


def towns_by_province() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {p: [] for p in PROVINCES}
    for _, _, prov, towns in DEMO_STATIONS:
        out[prov] += towns
    return out


def route(province: str | None, town: str | None) -> str:
    """Return the station code a report should go to. Town match first, then the province default."""
    t = (town or "").strip().lower()
    if t:
        for code, _, _, towns in DEMO_STATIONS:
            if t in (x.lower() for x in towns):
                return code
    for code, _, prov, _ in DEMO_STATIONS:
        if prov == province:
            return code
    return "JHB"
