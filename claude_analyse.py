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
- Madrid Halvmaraton 22. mars 2026: fullført på 1:26:59 (PR)
- NESTE RASE: Hamburg Maraton 26. april 2026 — MÅL: sub 3:00

TRENINGSSYSTEM:
- Norwegian Singles: 2 terskeløkter + 1 maratonspesifikk langtur annenhver uke
- Terskelintensitet: OLT I-3/nedre I-4 (160–170 bpm), laktat 2.5–3.5 mmol, 30–35 min samlet dragtid
- Rolige dager: virkelig rolig (<140 bpm, sone 1)
- Avslutt alltid terskeløkter med overskudd — heller for rolig enn for fort
- Maratonspesifikk langtur: 28–32 km med 15–20 km i maratonfart (~4:15–4:20/km)

HAMBURG-STATUS:
- 26. april er A-rase og sesongens hovedmål
- Estimert maratonkapasitet basert på Madrid: 3:00–3:05 med riktig oppbygging
- Anbefalt åpningsfart: 4:15–4:17/km
- CTL bør bygges fra ~50 tilbake mot 60–65 innen Hamburg
- TSB-mål inn mot Hamburg: +12 til +20

DIN OPPGAVE — gi en kortfattet analyse med disse fire delene:

1. DAGSFORM (2–3 linjer): HRV, søvn, BB og hvilepuls vurdert mot baseline
2. TREND (2–3 linjer): Hvordan har kroppen respondert på treningen siste 7–14 dager? Se HRV og aktiviteter i sammenheng
3. ANBEFALING (1–2 linjer): Konkret øktanbefaling i dag — type, intensitet, varighet
4. HAMBURG-STATUS (2–3 linjer): Er Øyvind i rute for sub 3:00? Hva bør prioriteres nå?

REGLER:
- Maks 220 ord totalt
- Norsk språk
- Kvantifiser alltid: bpm, watt, km, minutter
- Bruk begrepet belastningsbalanse, ikke ACWR
- Vær direkte — unngå generelle fraser
- Ved lav HRV eller høy tretthet: anbefal rolig trening eller hvile uten å nøle"""


def bygg_prompt(data: dict) -> str:
    tp = data.get("trainingpeaks", {})
    helse = tp.get("helsedata", {})
    fitness = tp.get("fitness", {}).get("dagens", {})
    trend_7d = tp.get("fitness", {}).get("trend_7d", [])
    helse_90d = tp.get("helsedata_90d", [])
    strava = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", [])
    historikk = strava.get("historikk_90d", [])

    # HRV-trend siste 14 dager
    hrv_trend = [(d["dato"], d["hrv"]) for d in helse_90d[-14:] if d.get("hrv")]
    hrv_linje = " → ".join([f"{d[5:]}: {v}ms" for d, v in hrv_trend[-7:]])

    # Søvntrend siste 7 dager
    sovn_trend = [(d["dato"], d["sovn_min"]) for d in helse_90d[-7:] if d.get("sovn_min")]
    sovn_snitt = round(sum(v for _, v in sovn_trend) / len(sovn_trend)) if sovn_trend else None

    siste = aktiviteter[0] if aktiviteter else {}

    # Aktiviteter siste 7 dager
    siste_7d_akt = [a for a in historikk[-10:] if a.get("dist_km", 0) > 0][-7:]
    akt_linjer = "\n".join([
        f"- {a['dato'][5:]}: {a['dist_km']}km {a.get('snitt_tempo','–')} {a.get('snitt_puls','–')}bpm suffer:{a.get('suffer_score','–')}"
        for a in siste_7d_akt
    ])

    prompt = f"""MORGENDATA {data.get('dato', '')}

HELSE I DAG:
HRV: {helse.get('hrv', '–')} ms | Hvilepuls: {helse.get('hvilepuls', '–')} bpm
Body Battery: {helse.get('bb_maks', '–')}/100 (min: {helse.get('bb_min', '–')})
Søvn: {helse.get('sovn_min', '–')} min (dyp: {helse.get('dyp_sovn_min', '–')}min | REM: {helse.get('rem_sovn_min', '–')}min)
Stress: {helse.get('stress_snitt', '–')} | Søvnsnitt siste 7d: {sovn_snitt} min

FORM:
CTL: {fitness.get('ctl', '–')} | ATL: {fitness.get('atl', '–')} | TSB: {fitness.get('tsb', '–')}
TSB-trend 7d: {' → '.join([str(d['tsb']) for d in trend_7d])}
CTL-trend 7d: {' → '.join([str(d['ctl']) for d in trend_7d])}

HRV-TREND SISTE 7 DAGER:
{hrv_linje}

SISTE ØKT:
{siste.get('navn','–')} ({siste.get('dato','–')})
{siste.get('dist_km','–')} km | {siste.get('snitt_tempo','–')} | {siste.get('snitt_puls','–')} bpm
Watt: {siste.get('snitt_watt','–')}W snitt / {siste.get('normalisert_watt','–')}W NP

AKTIVITETER SISTE 7 DAGER:
{akt_linjer}

DAGER TIL HAMBURG: {(date(2026, 4, 26) - date.today()).days}"""

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
        max_tokens=600,
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
