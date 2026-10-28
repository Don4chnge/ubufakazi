"""Bank branch fraud desks of the fictional Ubuntu Trust Bank (UTB), their regions, and report routing.

Internally these are still called "stations" (the code and database tables keep that name). On screen they are bank
branches: a report goes to the UTB branch fraud desk whose region covers the town where the victim was scammed. The
bank investigates, links the syndicate across branches and escalates to SAPS. Branches and regions are fictional.
"""
from __future__ import annotations

PROVINCES = ["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga",
             "North West", "Northern Cape", "Western Cape"]

# code, name, province, jurisdiction (towns the station covers). The first station listed for a province is the
# province default, used when the town is unknown. Codes of existing stations never change (accounts refer to them).
DEMO_STATIONS = [
    ("MTH", "UTB · Mthatha branch", "Eastern Cape", ["Mthatha", "Ngcobo", "Mqanduli", "Libode"]),
    ("GQB", "UTB · Gqeberha branch", "Eastern Cape", ["Gqeberha", "Kariega", "Jeffreys Bay", "Makhanda"]),
    ("ELN", "UTB · East London branch", "Eastern Cape", ["East London", "Mdantsane", "Qonce", "Komani"]),
    ("BFN", "UTB · Bloemfontein branch", "Free State", ["Bloemfontein", "Botshabelo", "Thaba Nchu", "Ladybrand"]),
    ("WLK", "UTB · Welkom branch", "Free State", ["Welkom", "Virginia", "Odendaalsrus", "Kroonstad"]),
    ("BTH", "UTB · Bethlehem branch", "Free State", ["Bethlehem", "Harrismith", "Phuthaditjhaba", "Ficksburg"]),
    ("JHB", "UTB · Johannesburg Central branch", "Gauteng", ["Johannesburg", "Soweto", "Sandton", "Randburg"]),
    ("ALB", "UTB · Alberton branch", "Gauteng", ["Alberton", "Germiston", "Boksburg", "Kempton Park"]),
    ("PTA", "UTB · Pretoria Central branch", "Gauteng", ["Pretoria", "Centurion", "Soshanguve", "Mamelodi"]),
    ("VER", "UTB · Vereeniging branch", "Gauteng", ["Vereeniging", "Vanderbijlpark", "Sebokeng", "Meyerton"]),
    ("DBN", "UTB · Durban Central branch", "KwaZulu-Natal", ["Durban", "Umlazi", "Pinetown", "Chatsworth"]),
    ("PMB", "UTB · Pietermaritzburg branch", "KwaZulu-Natal", ["Pietermaritzburg", "Edendale", "Howick", "Mooi River"]),
    ("RCB", "UTB · Richards Bay branch", "KwaZulu-Natal", ["Richards Bay", "Empangeni", "eShowe", "Mtubatuba"]),
    ("NCS", "UTB · Newcastle branch", "KwaZulu-Natal", ["Newcastle", "Madadeni", "Dundee", "Ladysmith"]),
    ("PLK", "UTB · Polokwane branch", "Limpopo", ["Polokwane", "Seshego", "Mokopane", "Lebowakgomo"]),
    ("THY", "UTB · Thohoyandou branch", "Limpopo", ["Thohoyandou", "Makhado", "Musina", "Malamulele"]),
    ("TZN", "UTB · Tzaneen branch", "Limpopo", ["Tzaneen", "Phalaborwa", "Giyani", "Nkowankowa"]),
    ("MBB", "UTB · Mbombela branch", "Mpumalanga", ["Mbombela", "White River", "KaNyamazane", "Barberton"]),
    ("EML", "UTB · eMalahleni branch", "Mpumalanga", ["eMalahleni", "Middelburg", "KwaMhlanga", "Delmas"]),
    ("SEC", "UTB · Secunda branch", "Mpumalanga", ["Secunda", "Ermelo", "Standerton", "Bethal"]),
    ("MHK", "UTB · Mahikeng branch", "North West", ["Mahikeng", "Mmabatho", "Lichtenburg", "Zeerust"]),
    ("RTB", "UTB · Rustenburg branch", "North West", ["Rustenburg", "Brits", "Mogwase", "Phokeng"]),
    ("KLK", "UTB · Klerksdorp branch", "North West", ["Klerksdorp", "Potchefstroom", "Jouberton", "Vryburg"]),
    ("KIM", "UTB · Kimberley branch", "Northern Cape", ["Kimberley", "Galeshewe", "Barkly West", "De Aar"]),
    ("UPT", "UTB · Upington branch", "Northern Cape", ["Upington", "Kuruman", "Kathu", "Postmasburg"]),
    ("SPB", "UTB · Springbok branch", "Northern Cape", ["Springbok", "Port Nolloth", "Calvinia", "Okiep"]),
    ("CPT", "UTB · Cape Town Central branch", "Western Cape", ["Cape Town", "Khayelitsha", "Bellville", "Mitchells Plain"]),
    ("STB", "UTB · Stellenbosch branch", "Western Cape", ["Stellenbosch", "Paarl", "Worcester", "Somerset West"]),
    ("GRG", "UTB · George branch", "Western Cape", ["George", "Mossel Bay", "Knysna", "Oudtshoorn"]),
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
