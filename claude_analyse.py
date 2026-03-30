#!/usr/bin/env python3
"""
claude_analyse.py
=================
Genererer coaching-analyse med Claude basert på morgenrapport-data.
"""

import anthropic
import os
import json
from datetime import date

SYSTEM_PROMPT = """Du er en erfaren utholdenhetscoach spesialisert på løping, med dyp kunnskap om Norwegian Singles-metoden og Marius Bakkens norske modell.

Du analyserer morgendata for Øyvind Grønner:
- Alder: 44 år | Vekt: 73 kg | HFmaks: ~195 bpm
- Terskelpuls: ~166 bpm | Stryd FTP: 327W | VO2max: 56
- HRV balansert sone: 70–98 ms
- Normal ukesvolum: ~90 km/uke
- Madrid Halvmaraton 22. mars 2026: 1:26:59 (PR) → estimert maratonkapasitet ~3:00–3:05
- NESTE RASE: Hamburg Maraton 26. april 2026 — MÅL: sub 3:00
- Anbefalt maratonfart: 4:15–4:17/km | Terskelfart: ~4:00–4:05/km | Terskelwatt: 295–344W

TRENINGSSYSTEM:
- Norwegian Singles: 2 terskeløkter + 1 maratonspesifikk langtur annenhver uke
- Terskelintensitet: OLT I-3/nedre I-4 (160–170 bpm), 30–35 min samlet dragtid
- Rolige dager: <140 bpm, sone 1
- Maratonlangtur: 28–32 km med 15–20 km i 4:15–4:20/km

SUB 3-KALKULATOR:
- CTL bør være 58–65 inn mot Hamburg for å ha trygg margin
- TSB bør være +12 til +20 race-uka
- Halvmaratontid på 1:26:59 tilsvarer maratonkapasitet ~3:00–3:02 med riktig oppbygging
- Terskelwatt i dag vs FTP 327W: hvis snitt NP på terskeløkter er under 295W er intensiteten for lav

OUTPUTFORMAT — følg denne strukturen nøyaktig:

LINJE 1 — HOVEDKONKLUSJON:
Én setning som starter med ett av disse:
"✅ I RUTE —" (alt peker riktig vei)
"⚠️ DELVIS I RUTE —" (noe er bra, noe bør justeres)
"🔴 IKKE I RUTE —" (tydelige signaler om at noe må endres)
Følg med én konkret begrunnelse. Maks 20 ord etter kolonet.

[tom linje]

HAMBURG-STATUS:
Er Øyvind realistisk i stand til sub 3:00 basert på dagens data?
Nevn: CTL nå vs mål, dager igjen, hva som konkret må skje.
Vær ærlig — ikke overdriv positivt eller negativt.

DAGSFORM:
Kun det som faktisk er verdt å nevne — ikke list opp alt.
Hvis HRV er normal, si det kort. Hvis søvn er dårlig, si det.
Ikke kommenter noe som er innenfor normalen med mer enn ett ord.

BELASTNINGSVURDERING I DAG:
Hvis det finnes en planlagt økt (UKEPLAN ← I DAG), gi én av disse tre vurderingene:
→ "GJENNOMFØR SOM PLANLAGT" — dagsform støtter planen, ingen justering nødvendig.
→ "LEGG PÅ: [konkret justering]" — dagsform er bedre enn forventet ELLER CTL-underskudd mot Hamburg krever ekstra stimulans. Angi hva som skal økes: km, dragtid, intensitet — med tall.
→ "REDUSER: [konkret justering]" — dagsform advarer mot full belastning. Angi hva som skal kuttes — med tall.
Følg alltid opp med én setning begrunnelse basert på HRV, TSB og CTL-gap mot mål.
Hvis ingen økt er planlagt for i dag: gi konkret øktanbefaling med type, intensitet og varighet.

MØNSTER (kun hvis det er noe å si):
Én observasjon om responsen på treningen siste 7–14 dager.
Utelat denne seksjonen hvis det ikke er noe tydelig mønster.

REGLER:
- Maks 260 ord
- Norsk språk
- Kvantifiser alltid: bpm, watt, km, min
- Balanser — si bare det som faktisk er sant
- Ikke finn på problemer som ikke finnes
- Ikke finn på positiver som ikke er der
- Bruk belastningsbalanse, ikke ACWR
- Hvis CTL er under 55 og det er under 20 dager til Hamburg: alltid anbefal å legge på last med mindre HRV er under 65 ms eller TSB er under -20"""


def bygg_prompt(data: dict) -> str:
    tp = data.get("trainingpeaks", {})
    helse = tp.get("helsedata", {})
    fitness = tp.get("fitness", {}).get("dagens", {})
    trend_7d = tp.get("fitness", {}).get("trend_7d", [])
    helse_90d = tp.get("helsedata_90d", [])
    strava = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", [])
    historikk = strava.get("historikk_90d", [])

    hrv_trend = [(d["dato"], d["hrv"]) for d in helse_90d[-14:] if d.get("hrv")]
    hrv_linje = " → ".join([f"{d[5:]}: {v}ms" for d, v in hrv_trend[-7:]])

    sovn_trend = [d["sovn_min"] for d in helse_90d[-7:] if d.get("sovn_min")]
    sovn_snitt = round(sum(sovn_trend) / len(sovn_trend)) if sovn_trend else None

    siste = aktiviteter[0] if aktiviteter else {}

    siste_7d_akt = [a for a in historikk[-10:] if a.get("dist_km", 0) > 0][-7:]
    akt_linjer = "\n".join([
        f"- {a['dato'][5:]}: {a['dist_km']}km {a.get('snitt_tempo','–')} {a.get('snitt_puls','–')}bpm suffer:{a.get('suffer_score','–')}"
        for a in siste_7d_akt
    ])

    # Beregn NP-snitt siste terskeløkter for å vurdere intensitet
    np_verdier = [a.get("normalisert_watt") for a in historikk[-14:] if a.get("normalisert_watt") and a.get("normalisert_watt", 0) > 200]
    np_snitt = round(sum(np_verdier) / len(np_verdier)) if np_verdier else None

    ukeplan = data.get("ukeplan", {})
    ukeplan_linjer = ""
    if ukeplan and ukeplan.get("okter"):
        today = date.today().isoformat()
        linjer = []
        for o in ukeplan["okter"]:
            tag = " ← I DAG" if o["dato"] == today else ""
            linjer.append(
                f"- {o['dato'][5:]} {o['type']}: {o['beskrivelse']} | "
                f"{o.get('dist_km', '–')} km | {o.get('tempo_min_km', '–')}/km | "
                f"{o.get('varighet_min', '–')} min{tag}"
            )
        ukeplan_linjer = "\n".join(linjer)

    prompt = f"""MORGENDATA {data.get('dato', '')}
DAGER TIL HAMBURG: {(date(2026, 4, 26) - date.today()).days}

HELSE I DAG:
HRV: {helse.get('hrv', '–')} ms (balansert sone: 70–98 ms)
Hvilepuls: {helse.get('hvilepuls', '–')} bpm
Body Battery: {helse.get('bb_maks', '–')}/100 (min: {helse.get('bb_min', '–')})
Søvn: {helse.get('sovn_min', '–')} min (dyp: {helse.get('dyp_sovn_min', '–')}min | REM: {helse.get('rem_sovn_min', '–')}min)
Søvnsnitt siste 7d: {sovn_snitt} min
Stress: {helse.get('stress_snitt', '–')}

FORM:
CTL: {fitness.get('ctl', '–')} (mål inn mot Hamburg: 58–65)
ATL: {fitness.get('atl', '–')} | TSB: {fitness.get('tsb', '–')}
TSB-trend 7d: {' → '.join([str(d['tsb']) for d in trend_7d])}
CTL-trend 7d: {' → '.join([str(d['ctl']) for d in trend_7d])}

HRV-TREND SISTE 7 DAGER:
{hrv_linje}

SISTE ØKT:
{siste.get('navn','–')} ({siste.get('dato','–')})
{siste.get('dist_km','–')} km | {siste.get('snitt_tempo','–')} | {siste.get('snitt_puls','–')} bpm
Watt: {siste.get('snitt_watt','–')}W snitt / {siste.get('normalisert_watt','–')}W NP
(Terskelwatt sone 4: 295–344W | NP-snitt siste 14d løpeøkter: {np_snitt}W)

AKTIVITETER SISTE 7 DAGER:
{akt_linjer}

PLANLAGT UKE (Pacepilot → ukeplan.json):
{ukeplan_linjer if ukeplan_linjer else "Ingen ukeplan registrert"}"""

    return prompt


def main():
    dato = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"

    if not os.path.exists(json_fil):
        print(f"Finner ikke {json_fil}")
        return

    with open(json_fil, "r", encoding="utf-8") as f:
        data = json.load(f)

    prompt = bygg_prompt(data)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    melding = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=700,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )

    analyse = melding.content[0].text
    print(analyse)

    data["claude_analyse"] = analyse
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return analyse


if __name__ == "__main__":
    main()
