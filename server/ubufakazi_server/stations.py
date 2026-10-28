"""Fictional demonstration stations, their jurisdictions, and report routing.

These are NOT SAPS stations and the jurisdictions are NOT official SAPS precinct boundaries. They exist to
demonstrate jurisdiction-based routing: a report goes to the demo station whose area covers the town where the
victim was scammed. A real deployment needs SAPS approval and the official precinct boundaries.
"""
from __future__ import annotations

PROVINCES = ["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga",
             "North West", "Northern Cape", "Western Cape"]

# code, name, province, jurisdiction (towns the station covers). The first station listed for a province is the
# province default, used when the town is unknown. Codes of existing stations never change (accounts refer to them).
DEMO_STATIONS = [
    ("MTH", "Demo Station · Mthatha", "Eastern Cape", ["Mthatha", "Ngcobo", "Mqanduli", "Libode"]),
    ("GQB", "Demo Station · Gqeberha", "Eastern Cape", ["Gqeberha", "Kariega", "Jeffreys Bay", "Makhanda"]),
    ("ELN", "Demo Station · East London", "Eastern Cape", ["East London", "Mdantsane", "Qonce", "Komani"]),
    ("BFN", "Demo Station · Bloemfontein", "Free State", ["Bloemfontein", "Botshabelo", "Thaba Nchu", "Ladybrand"]),
    ("WLK", "Demo Station · Welkom", "Free State", ["Welkom", "Virginia", "Odendaalsrus", "Kroonstad"]),
    ("BTH", "Demo Station · Bethlehem", "Free State", ["Bethlehem", "Harrismith", "Phuthaditjhaba", "Ficksburg"]),
    ("JHB", "Demo Station · Johannesburg Central", "Gauteng", ["Johannesburg", "Soweto", "Sandton", "Randburg"]),
    ("ALB", "Demo Station · Alberton", "Gauteng", ["Alberton", "Germiston", "Boksburg", "Kempton Park"]),
    ("PTA", "Demo Station · Pretoria Central", "Gauteng", ["Pretoria", "Centurion", "Soshanguve", "Mamelodi"]),
    ("VER", "Demo Station · Vereeniging", "Gauteng", ["Vereeniging", "Vanderbijlpark", "Sebokeng", "Meyerton"]),
    ("DBN", "Demo Station · Durban Central", "KwaZulu-Natal", ["Durban", "Umlazi", "Pinetown", "Chatsworth"]),
    ("PMB", "Demo Station · Pietermaritzburg", "KwaZulu-Natal", ["Pietermaritzburg", "Edendale", "Howick", "Mooi River"]),
    ("RCB", "Demo Station · Richards Bay", "KwaZulu-Natal", ["Richards Bay", "Empangeni", "eShowe", "Mtubatuba"]),
    ("NCS", "Demo Station · Newcastle", "KwaZulu-Natal", ["Newcastle", "Madadeni", "Dundee", "Ladysmith"]),
    ("PLK", "Demo Station · Polokwane", "Limpopo", ["Polokwane", "Seshego", "Mokopane", "Lebowakgomo"]),
    ("THY", "Demo Station · Thohoyandou", "Limpopo", ["Thohoyandou", "Makhado", "Musina", "Malamulele"]),
    ("TZN", "Demo Station · Tzaneen", "Limpopo", ["Tzaneen", "Phalaborwa", "Giyani", "Nkowankowa"]),
    ("MBB", "Demo Station · Mbombela", "Mpumalanga", ["Mbombela", "White River", "KaNyamazane", "Barberton"]),
    ("EML", "Demo Station · eMalahleni", "Mpumalanga", ["eMalahleni", "Middelburg", "KwaMhlanga", "Delmas"]),
    ("SEC", "Demo Station · Secunda", "Mpumalanga", ["Secunda", "Ermelo", "Standerton", "Bethal"]),
    ("MHK", "Demo Station · Mahikeng", "North West", ["Mahikeng", "Mmabatho", "Lichtenburg", "Zeerust"]),
    ("RTB", "Demo Station · Rustenburg", "North West", ["Rustenburg", "Brits", "Mogwase", "Phokeng"]),
    ("KLK", "Demo Station · Klerksdorp", "North West", ["Klerksdorp", "Potchefstroom", "Jouberton", "Vryburg"]),
    ("KIM", "Demo Station · Kimberley", "Northern Cape", ["Kimberley", "Galeshewe", "Barkly West", "De Aar"]),
    ("UPT", "Demo Station · Upington", "Northern Cape", ["Upington", "Kuruman", "Kathu", "Postmasburg"]),
    ("SPB", "Demo Station · Springbok", "Northern Cape", ["Springbok", "Port Nolloth", "Calvinia", "Okiep"]),
    ("CPT", "Demo Station · Cape Town Central", "Western Cape", ["Cape Town", "Khayelitsha", "Bellville", "Mitchells Plain"]),
    ("STB", "Demo Station · Stellenbosch", "Western Cape", ["Stellenbosch", "Paarl", "Worcester", "Somerset West"]),
    ("GRG", "Demo Station · George", "Western Cape", ["George", "Mossel Bay", "Knysna", "Oudtshoorn"]),
]

STATION_BY_CODE = {code: (name, prov, towns) for code, name, prov, towns in DEMO_STATIONS}


def towns_by_province() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {p: [] for p in PROVINCES}
    for _, _, prov, towns in DEMO_STATIONS:
        out[prov] += towns
    return out


def jurisdiction_of(town: str | None) -> str | None:
    """Code of the demo station whose jurisdiction covers this town, or None."""
    t = (town or "").strip().lower()
    if not t:
        return None
    for code, _, _, towns in DEMO_STATIONS:
        if t in (x.lower() for x in towns):
            return code
    return None


def route(province: str | None, town: str | None) -> str:
    """Return the station code a report should go to: the station whose jurisdiction covers the town where the
    victim was scammed; otherwise the province's default station."""
    code = jurisdiction_of(town)
    if code:
        return code
    for code, _, prov, _ in DEMO_STATIONS:
        if prov == province:
            return code
    return "JHB"


def jurisdictions() -> list[dict]:
    """Every province with its demo stations and the towns each one covers."""
    return [{"province": p, "stations": [{"code": c, "name": n, "towns": t} for c, n, pr, t in DEMO_STATIONS if pr == p]}
            for p in PROVINCES]
