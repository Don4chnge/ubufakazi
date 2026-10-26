"""Draft statements and bank fraud reports.

Scam statements are ported from the MVP in five languages. Other incident types get a
general statement built from the complainant's own words. Every output is a DRAFT the
complainant must read, correct and sign; translations need review by a fluent speaker.
"""
from __future__ import annotations


from .extract import list_text, money, show_acc, show_phone, TYPE_LABEL

LANG_NAMES = {"en": "English", "zu": "isiZulu", "xh": "isiXhosa", "af": "Afrikaans", "st": "Sesotho"}
MONTHS = {
    "en": ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"],
    "zu": ["Januwari", "Februwari", "Mashi", "Ephreli", "Meyi", "Juni", "Julayi", "Agasti", "Septhemba", "Okthoba", "Novemba", "Disemba"],
    "xh": ["Janyuwari", "Februwari", "Matshi", "Epreli", "Meyi", "Juni", "Julayi", "Agasti", "Septemba", "Okthobha", "Novemba", "Disemba"],
    "af": ["Januarie", "Februarie", "Maart", "April", "Mei", "Junie", "Julie", "Augustus", "September", "Oktober", "November", "Desember"],
    "st": ["Pherekgong", "Hlakola", "Hlakubele", "Mmesa", "Motsheanong", "Phupjane", "Phupu", "Phato", "Lwetse", "Mphalane", "Pudungwana", "Tshitwe"],
}


def fmt_date(d, lang="en"):
    return f"{d.day} {MONTHS.get(lang, MONTHS['en'])[d.month - 1]} {d.year}" if d else None


S = {
    "en": dict(
        title="COMPLAINANT STATEMENT (DRAFT)", nameph="[your full name]", conj="and",
        intro=lambda n: f"I, {n}, state the following:",
        l1=lambda d, a, ph: f'1. On {d}, I was contacted by a person using the name "{a}"' + (f" and the number{'s' if ph[0] > 1 else ''} {ph[1]}" if ph else "") + ".",
        offer={"job": "offered me a job and told me I had been selected", "marketplace": "offered to sell me an item",
               "romance": "built a relationship with me and then asked me for money", "investment": "offered me an investment with high returns",
               "parcel": "told me a parcel was being held and needed a fee to be released", "sars": "told me I was due a tax refund from SARS",
               "other": "made me an offer"},
        l2=lambda o: f"2. This person {o}.",
        acc=lambda a: (a["bank"] + " " if a.get("bank") else "") + "account " + show_acc(a["value"]),
        l3=lambda t: f"3. They asked me to make payment into {t}." if t else "3. They asked me to make a payment.",
        l4=lambda amt, d: f"4. I paid a total of {amt}" + (f" on {d}" if d else "") + ".",
        outcome={"job": "I never received the job, and the person stopped responding", "marketplace": "I never received the item, and the person stopped responding",
                 "romance": "the person kept asking for more money and then stopped responding", "investment": "I never received any returns or my money back, and the person stopped responding",
                 "parcel": "no parcel was delivered, and the person stopped responding", "sars": "I never received any refund",
                 "other": "I did not receive what was promised, and the person stopped responding"},
        l5=lambda o: f"5. After I paid, {o}.",
        l6=lambda t: f"6. They also sent me a link to {t}.",
        not_known="I did not know this person and I did not give them permission to keep my money.",
        attach=lambda r: f"I attach the evidence listed in Ubufakazi report {r}. Each file has a SHA-256 fingerprint so that any later change to it can be detected.",
        request="I request that this matter be investigated as fraud.",
        sign="Signature: ______________________     Date: ______________",
        amountph="[amount]", dateph="[date]", aliasph="[name]",
        g_intro=lambda d, p: f"1. On {d}" + (f", at or near {p}" if p else "") + ", the following happened:",
        g_ev=lambda r: f"2. I attach the evidence listed in Ubufakazi report {r}. Each file has a SHA-256 fingerprint so that any later change to it can be detected.",
        g_request="I request that this matter be investigated.",
    ),
    "zu": dict(
        title="ISITATIMENDE SOMMANGALELI (OKUSALUNGISWA)", nameph="[igama lakho]", conj="no-",
        intro=lambda n: f"Mina, {n}, ngithi:",
        l1=lambda d, a, ph: f'1. Ngomhla ka-{d}, ngathintwa umuntu ozibiza ngokuthi ngu-"{a}"' + (f", esebenzisa inombolo {ph[1]}" if ph else "") + ".",
        offer={"job": "wangethembisa umsebenzi wathi ngikhethiwe", "marketplace": "wathi uzongithengisela impahla",
               "romance": "wakha ubudlelwano nami wabe esecela imali", "investment": "wangethembisa ukutshala imali okuzongizuzisa kakhulu",
               "parcel": "wathi kukhona iphasela elibanjiwe okudingeka likhokhelwe ukuze likhishwe", "sars": "wathi ngizobuyiselwa imali yentela yi-SARS",
               "other": "wangethembisa okuthile"},
        l2=lambda o: f"2. Lo muntu {o}.",
        acc=lambda a: "akhawunti " + ("yase-" + a["bank"] + " " if a.get("bank") else "") + show_acc(a["value"]),
        l3=lambda t: f"3. Wangicela ukuthi ngikhokhe imali ku-{t}." if t else "3. Wangicela ukuthi ngikhokhe imali.",
        l4=lambda amt, d: f"4. Ngakhokha isamba esingu-{amt}" + (f" ngomhla ka-{d}" if d else "") + ".",
        outcome={"job": "Angizange ngiwuthole umsebenzi, futhi lo muntu wayeka ukuphendula", "marketplace": "Angizange ngiyithole impahla, futhi lo muntu wayeka ukuphendula",
                 "romance": "Lo muntu waqhubeka ecela imali eyengeziwe wabe eseyeka ukuphendula", "investment": "Angizange ngithole nzuzo noma imali yami ibuyiswe, futhi lo muntu wayeka ukuphendula",
                 "parcel": "Alikho iphasela elalethwa, futhi lo muntu wayeka ukuphendula", "sars": "Angizange ngiyithole imali ebuyiselwayo",
                 "other": "Angizange ngikuthole engakuthenjiswa, futhi lo muntu wayeka ukuphendula"},
        l5=lambda o: f"5. {o}.",
        l6=lambda t: f"6. Wangithumelela nesixhumanisi (link) esiya ku-{t}.",
        not_known="Angimazi lo muntu, futhi angizange ngimnike imvume yokugcina imali yami.",
        attach=lambda r: f"Nginamathisele ubufakazi obubhalwe embikweni we-Ubufakazi {r}. Ifayela ngalinye linesigxivizo sedijithali (SHA-256), ukuze noma yiluphi ushintsho lubonakale.",
        request="Ngicela ukuthi lolu daba luphenywe njengokukhwabanisa (fraud).",
        sign="Isiginesha: ______________________     Usuku: ______________",
        amountph="[isamba]", dateph="[usuku]", aliasph="[igama]",
        g_intro=lambda d, p: f"1. Ngomhla ka-{d}" + (f", e-{p}" if p else "") + ", kwenzeka lokhu okulandelayo:",
        g_ev=lambda r: f"2. Nginamathisele ubufakazi obubhalwe embikweni we-Ubufakazi {r}. Ifayela ngalinye linesigxivizo sedijithali (SHA-256).",
        g_request="Ngicela ukuthi lolu daba luphenywe.",
    ),
    "xh": dict(
        title="INGXELO YOMMANGALELI (ULUHLAZA)", nameph="[igama lakho]", conj="kunye",
        intro=lambda n: f"Mna, {n}, ndithi:",
        l1=lambda d, a, ph: f'1. Ngomhla we-{d}, ndaqhagamshelwa ngumntu osebenzisa igama elithi "{a}"' + (f", nenombolo {ph[1]}" if ph else "") + ".",
        offer={"job": "wandithembisa umsebenzi wathi ndikhethiwe", "marketplace": "wathi uza kundithengisela into", "romance": "wakha ubudlelwane nam waza wacela imali",
               "investment": "wandithembisa utyalo-mali olunenzuzo ephezulu", "parcel": "wathi kukho ipasile ebanjiweyo ekufuneka ihlawulelwe ukuze ikhululwe",
               "sars": "wathi ndiza kubuyiselwa imali yerhafu yi-SARS", "other": "wandithembisa into ethile"},
        l2=lambda o: f"2. Lo mntu {o}.",
        acc=lambda a: "akhawunti " + ("yase" + a["bank"] + " " if a.get("bank") else "") + show_acc(a["value"]),
        l3=lambda t: f"3. Wandicela ukuba ndihlawule imali kwi-{t}." if t else "3. Wandicela ukuba ndihlawule imali.",
        l4=lambda amt, d: f"4. Ndahlawula imali eyi-{amt}" + (f" ngomhla we-{d}" if d else "") + ".",
        outcome={"job": "Andizange ndiwufumane umsebenzi, kwaye lo mntu wayeka ukuphendula", "marketplace": "Andizange ndiyifumane loo nto, kwaye lo mntu wayeka ukuphendula",
                 "romance": "Lo mntu waqhubeka ecela imali engakumbi waza wayeka ukuphendula", "investment": "Andizange ndifumane nzuzo okanye imali yam ibuyiselwe, kwaye lo mntu wayeka ukuphendula",
                 "parcel": "Akukho pasile yafika, kwaye lo mntu wayeka ukuphendula", "sars": "Andizange ndiyifumane imali ebuyiselwayo",
                 "other": "Andizange ndikufumane endakuthenjiswayo, kwaye lo mntu wayeka ukuphendula"},
        l5=lambda o: f"5. {o}.",
        l6=lambda t: f"6. Wandithumelela nekhonkco (link) eliya ku-{t}.",
        not_known="Andimazi lo mntu, kwaye andizange ndimnike imvume yokugcina imali yam.",
        attach=lambda r: f"Ndincamathisela ubungqina obudweliswe kwingxelo ye-Ubufakazi {r}. Ifayile nganye inesitampu sedijithali (SHA-256), ukuze naluphi na utshintsho lubonakale.",
        request="Ndicela ukuba lo mba uphandwe njengobuqhophololo (fraud).",
        sign="Utyikityo: ______________________     Umhla: ______________",
        amountph="[isixa]", dateph="[umhla]", aliasph="[igama]",
        g_intro=lambda d, p: f"1. Ngomhla we-{d}" + (f", e-{p}" if p else "") + ", kwenzeka oku kulandelayo:",
        g_ev=lambda r: f"2. Ndincamathisela ubungqina obudweliswe kwingxelo ye-Ubufakazi {r}. Ifayile nganye inesitampu sedijithali (SHA-256).",
        g_request="Ndicela ukuba lo mba uphandwe.",
    ),
    "af": dict(
        title="VERKLARING VAN KLAGER (KONSEP)", nameph="[jou volle naam]", conj="en",
        intro=lambda n: f"Ek, {n}, verklaar soos volg:",
        l1=lambda d, a, ph: f'1. Op {d} is ek gekontak deur \'n persoon wat die naam "{a}"' + (f" en die nommer{'s' if ph[0] > 1 else ''} {ph[1]}" if ph else "") + " gebruik.",
        offer={"job": "my 'n werk aangebied en gesê dat ek gekies is", "marketplace": "aangebied om 'n item aan my te verkoop",
               "romance": "'n verhouding met my opgebou en my toe vir geld gevra", "investment": "my 'n belegging met hoë opbrengste aangebied",
               "parcel": "gesê dat 'n pakkie teruggehou word en dat 'n fooi betaal moet word om dit vry te stel",
               "sars": "gesê dat ek 'n belastingterugbetaling van SARS sou ontvang", "other": "my 'n aanbod gemaak"},
        l2=lambda o: f"2. Hierdie persoon het {o}.",
        acc=lambda a: "rekening " + show_acc(a["value"]) + (" by " + a["bank"] if a.get("bank") else ""),
        l3=lambda t: f"3. Hulle het my gevra om betaling te maak in {t}." if t else "3. Hulle het my gevra om 'n betaling te maak.",
        l4=lambda amt, d: f"4. Ek het 'n totaal van {amt} betaal" + (f" op {d}" if d else "") + ".",
        outcome={"job": "het ek nooit die werk gekry nie, en die persoon het opgehou om te antwoord", "marketplace": "het ek nooit die item ontvang nie, en die persoon het opgehou om te antwoord",
                 "romance": "het die persoon aangehou om meer geld te vra en toe opgehou om te antwoord", "investment": "het ek geen opbrengs of my geld terug ontvang nie, en die persoon het opgehou om te antwoord",
                 "parcel": "is geen pakkie afgelewer nie, en die persoon het opgehou om te antwoord", "sars": "het ek geen terugbetaling ontvang nie",
                 "other": "het ek nie ontvang wat belowe is nie, en die persoon het opgehou om te antwoord"},
        l5=lambda o: f"5. Nadat ek betaal het, {o}.",
        l6=lambda t: f"6. Hulle het my ook 'n skakel na {t} gestuur.",
        not_known="Ek het nie hierdie persoon geken nie en het hulle nie toestemming gegee om my geld te hou nie.",
        attach=lambda r: f"Ek heg die bewyse aan wat in Ubufakazi-verslag {r} gelys word. Elke lêer het 'n SHA-256-vingerafdruk sodat enige latere verandering opgespoor kan word.",
        request="Ek versoek dat hierdie saak as bedrog ondersoek word.",
        sign="Handtekening: ______________________     Datum: ______________",
        amountph="[bedrag]", dateph="[datum]", aliasph="[naam]",
        g_intro=lambda d, p: f"1. Op {d}" + (f", by of naby {p}" if p else "") + ", het die volgende gebeur:",
        g_ev=lambda r: f"2. Ek heg die bewyse aan wat in Ubufakazi-verslag {r} gelys word. Elke lêer het 'n SHA-256-vingerafdruk.",
        g_request="Ek versoek dat hierdie saak ondersoek word.",
    ),
    "st": dict(
        title="POLELO YA MMELAEDI (MOHLALA)", nameph="[lebitso la hao]", conj="le",
        intro=lambda n: f"Nna, {n}, ke re:",
        l1=lambda d, a, ph: f'1. Ka la {d}, motho ya sebedisang lebitso la "{a}"' + (f" le nomoro {ph[1]}" if ph else "") + " o ile a ikopanya le nna.",
        offer={"job": "o ile a ntshepisa mosebetsi mme a re ke kgethilwe", "marketplace": "o ile a re o tla nthekisetsa thepa", "romance": "o ile a aha kamano le nna mme a nkopa tjhelete",
               "investment": "o ile a ntshepisa peeletso e nang le phaello e hodimo", "parcel": "o ile a re ho na le phasela e tshwerweng e hlokang ho lefellwa hore e lokollwe",
               "sars": "o ile a re ke tla busetswa tjhelete ya lekgetho ke SARS", "other": "o ile a ntshepisa ho itseng"},
        l2=lambda o: f"2. Motho enwa {o}.",
        acc=lambda a: "akhaontong " + ("ya " + a["bank"] + " " if a.get("bank") else "") + show_acc(a["value"]),
        l3=lambda t: f"3. O ile a nkopa hore ke lefe tjhelete {t}." if t else "3. O ile a nkopa hore ke lefe tjhelete.",
        l4=lambda amt, d: f"4. Ke lefile kakaretso ya {amt}" + (f" ka la {d}" if d else "") + ".",
        outcome={"job": "Ha ke a ka ka fumana mosebetsi, mme motho enwa o ile a kgaotsa ho araba", "marketplace": "Ha ke a ka ka fumana thepa, mme motho enwa o ile a kgaotsa ho araba",
                 "romance": "Motho enwa o ile a tswela pele ho kopa tjhelete e eketsehileng mme a kgaotsa ho araba", "investment": "Ha ke a ka ka fumana phaello kapa tjhelete ya ka e busetswa, mme motho enwa o ile a kgaotsa ho araba",
                 "parcel": "Ha ho phasela e ileng ya fihla, mme motho enwa o ile a kgaotsa ho araba", "sars": "Ha ke a ka ka fumana tjhelete e busetswang",
                 "other": "Ha ke a ka ka fumana se neng se tshepisitswe, mme motho enwa o ile a kgaotsa ho araba"},
        l5=lambda o: f"5. {o}.",
        l6=lambda t: f"6. O ile a nthomella le lehokela (link) le yang ho {t}.",
        not_known="Ha ke mo tsebe motho enwa, mme ha ke a mo fa tumello ya ho boloka tjhelete ya ka.",
        attach=lambda r: f"Ke kenya bopaki bo thathamisitsweng tlalehong ya Ubufakazi {r}. Faele ka nngwe e na le setempe sa dijithale (SHA-256), hore phetoho efe kapa efe e bonahale.",
        request="Ke kopa hore taba ena e batlisiswe jwalo ka bomenemene (fraud).",
        sign="Tshaeno: ______________________     Letsatsi: ______________",
        amountph="[kakaretso]", dateph="[letsatsi]", aliasph="[lebitso]",
        g_intro=lambda d, p: f"1. Ka la {d}" + (f", ho {p}" if p else "") + ", ho etsahetse se latelang:",
        g_ev=lambda r: f"2. Ke kenya bopaki bo thathamisitsweng tlalehong ya Ubufakazi {r}. Faele ka nngwe e na le setempe sa dijithale (SHA-256).",
        g_request="Ke kopa hore taba ena e batlisiswe.",
    ),
}

DRAFT_NOTE = {
    "en": "DRAFT prepared by Ubufakazi from your report. Read it carefully, correct anything that is wrong, and sign only at the police station.",
    "zu": "OKUSALUNGISWA: kulungiswe yi-Ubufakazi. Kufunde kahle, ulungise okungalungile, usayine esiteshini samaphoyisa kuphela.",
    "xh": "ULUHLAZA: lulungiswe yi-Ubufakazi. Lufunde kakuhle, ulungise okungachanekanga, utyikitye kwisikhululo samapolisa kuphela.",
    "af": "KONSEP deur Ubufakazi opgestel. Lees dit noukeurig, korrigeer enige foute en teken slegs by die polisiekantoor.",
    "st": "MOHLALA o lokisitsweng ke Ubufakazi. O bale ka hloko, o lokise se fosahetseng, mme o tekene seteisheneng sa sepolesa feela.",
}


def scam_statement(lang: str, *, reference: str, name: str | None, analysis: dict, scam_type: str) -> str:
    L = S.get(lang, S["en"])
    ex, msgs = analysis["ex"], analysis["msgs"]
    first = next((m for m in msgs if m["date"]), None)
    pay_dates = []
    for p in ex["paid"]:
        m = next((m for m in msgs if m["i"] == p["msg"]), None)
        if m and m["date"]:
            pay_dates.append(m["date"])
    phones = [show_phone(p["value"]) for p in ex["phones"]]
    dates = list(dict.fromkeys(fmt_date(d, lang) for d in pay_dates))
    t = scam_type if scam_type in L["offer"] else "other"
    lines = [
        L["title"], "", L["intro"](name or L["nameph"]), "",
        L["l1"](fmt_date(first["date"], lang) if first else L["dateph"], analysis["scammer"] or L["aliasph"],
                (len(phones), list_text(phones, L["conj"])) if phones else None),
        L["l2"](L["offer"][t]),
        L["l3"](list_text([L["acc"](a) for a in ex["accounts"]], L["conj"]) if ex["accounts"] else ""),
        L["l4"](money(ex["total_paid"]) if ex["total_paid"] is not None else L["amountph"], list_text(dates, L["conj"]) if dates else ""),
        L["l5"](L["outcome"][t]),
        L["l6"](list_text(ex["domains"], L["conj"])) if ex["domains"] else None,
        "", L["not_known"], L["attach"](reference), "", L["request"], "", L["sign"], "", DRAFT_NOTE.get(lang, DRAFT_NOTE["en"]),
    ]
    return "\n".join(l for l in lines if l is not None)


def general_statement(lang: str, *, reference: str, name: str | None, when: str | None, place: str | None,
                      description: str) -> str:
    L = S.get(lang, S["en"])
    lines = [L["title"], "", L["intro"](name or L["nameph"]), "",
             L["g_intro"](when or L["dateph"], place), "", (description or "").strip() or "[...]", "",
             L["g_ev"](reference), "", L["g_request"], "", L["sign"], "", DRAFT_NOTE.get(lang, DRAFT_NOTE["en"])]
    return "\n".join(lines)


def bank_report(*, reference: str, name: str | None, analysis: dict, scam_type: str) -> str:
    ex, msgs = analysis["ex"], analysis["msgs"]
    times = []
    for p in ex["paid"]:
        m = next((m for m in msgs if m["i"] == p["msg"]), None)
        if m and m["date"]:
            times.append(fmt_date(m["date"]) + " " + m["date"].strftime("%H:%M"))
    return "\n".join([
        "To: Fraud department, [your bank]",
        "Subject: Fraud report: request to trace and stop funds",
        "",
        "I am reporting payment(s) I made to a person I believe is a fraudster.",
        "",
        f"Amount paid: {money(ex['total_paid']) if ex['total_paid'] is not None else '[amount]'}",
        f"Date(s) and time(s): {'; '.join(times) if times else '[date and time of each payment]'}",
        "Paid into: " + ("; ".join((a.get('bank') or '[bank]') + ', account ' + show_acc(a['value']) for a in ex['accounts'])
                          if ex['accounts'] else "[receiving bank and account number]"),
        f"Name the other person used: {analysis['scammer'] or '[name]'}",
        f"Their phone number(s): {', '.join(show_phone(p['value']) for p in ex['phones']) or '[number]'}",
        f"Type of scam: {TYPE_LABEL.get(scam_type, 'Scam')}",
        "SAPS case number: [add once SAPS has registered the case]",
        f"Ubufakazi report: {reference}",
        "",
        "Please investigate the receiving account and stop or freeze the funds where possible. The evidence pack is attached.",
        "",
        name or "[your name]",
        "[your account number] · [your phone number]",
        "",
        "Prepared by Ubufakazi from the evidence you provided. Details are extracted automatically and must be checked before sending.",
    ])
