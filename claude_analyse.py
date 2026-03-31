#!/usr/bin/env python3
"""
claude_analyse.py
=================
Genererer coaching-analyse med Claude basert på morgenrapport-data.
"""

import anthropic
import os
import json
import math
from datetime import date, timedelta
from pathlib import Path

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

SISTE ØKT:
Vurder siste økt basert på TSS, IF og EF (effektivitetsfaktor = NP/HR):
- IF < 0.75: restitusjon | 0.75–0.85: rolig aerob | 0.85–0.95: maratonspesifikk | 0.95–1.05: terskel
- EF > 2.0 W/bpm er god løpsøkonomi for dette nivået
- Var TSS og intensitet konsistent med plantype (rolig / maratonspesifikk / terskel)?
- Nevn avvik fra plan og om øktens bidrag var nok, for mye eller for lite.
Maks 3 setninger. Bruk konkrete tall.

BELASTNINGSBILDE:
Bruk akkumulert TSS 7d og 14d, CTL-utvikling og nødvendig daglig TSS mot Hamburg:
- Bygger CTL raskt nok? Vil nødvendig daglig TSS kreve for høy belastning?
- Vurder retning: CTL stigende, flat eller fallende?
- Er TSB i dag gunstig nok for planlagt treningsbelastning fremover?
Maks 4 setninger. Kvantifiser.

HAMBURG-STATUS:
Kun det som konkret mangler eller er på plass for sub 3:00: CTL nå vs mål, TSB race-dag.
Vær ærlig — ikke overdriv. Maks 3 setninger.

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
Én observasjon om responsutvikling siste 7–14 dager (EF-trend, HRV-respons, CTL-retning).
Utelat denne seksjonen hvis det ikke er noe tydelig mønster.

REGLER:
- Maks 320 ord
- Norsk språk
- Kvantifiser alltid: bpm, watt, km, min, TSS, IF
- Balanser — si bare det som faktisk er sant
- Ikke finn på problemer som ikke finnes
- Ikke finn på positiver som ikke er der
- Bruk belastningsbalanse, ikke ACWR
- Hvis CTL er under 55 og det er under 20 dager til Hamburg: alltid anbefal å legge på last med mindre HRV er under 65 ms eller TSB er under -20"""


OKT_LOGG_FIL = Path("okt_logg.json")


def les_okt_logg() -> list:
    if OKT_LOGG_FIL.exists():
        with open(OKT_LOGG_FIL, encoding="utf-8") as f:
            return json.load(f)
    return []


def lagre_okt_kommentar(dato: str, okt_navn: str, kommentar: str):
    """Legg til kommentar i okt_logg.json. Oppdaterer eksisterende post for samme dato."""
    logg = les_okt_logg()
    for post in logg:
        if post.get("dato") == dato:
            post["kommentar"] = kommentar
            post["okt_navn"] = okt_navn
            break
    else:
        logg.append({"dato": dato, "okt_navn": okt_navn, "kommentar": kommentar})
    # Behold kun siste 60 poster
    logg = sorted(logg, key=lambda x: x["dato"])[-60:]
    with open(OKT_LOGG_FIL, "w", encoding="utf-8") as f:
        json.dump(logg, f, ensure_ascii=False, indent=2)


def bygg_kommentar_kontekst() -> str:
    """Hent kommentarer fra siste 14 dager for kontekst i analysen."""
    logg = les_okt_logg()
    if not logg:
        return ""
    grense = (date.today() - timedelta(days=14)).isoformat()
    relevante = [p for p in logg if p.get("dato", "") >= grense and p.get("kommentar")]
    if not relevante:
        return ""
    linjer = [f"- {p['dato'][5:]} ({p.get('okt_navn', '–')}): {p['kommentar']}" for p in relevante[-7:]]
    return "\n".join(linjer)


def bygg_prompt(data: dict) -> str:
    tp = data.get("trainingpeaks", {})
    helse = tp.get("helsedata", {})
    fitness = tp.get("fitness", {}).get("dagens", {})
    trend_7d = tp.get("fitness", {}).get("trend_7d", [])
    trend_90d = tp.get("fitness", {}).get("trend_90d", [])
    helse_90d = tp.get("helsedata_90d", [])
    strava = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", [])
    historikk = strava.get("historikk_90d", [])

    today_iso = date.today().isoformat()
    grense_7d = (date.today() - timedelta(days=7)).isoformat()
    grense_14d = (date.today() - timedelta(days=14)).isoformat()

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

    # ── TSS / IF / EF for siste økt ──────────────────────────
    FTP = 327
    np_siste = siste.get("normalisert_watt")
    varighet_sek = (siste.get("varighet_min") or 0) * 60
    hr_siste = siste.get("snitt_puls")

    if np_siste and varighet_sek and np_siste > 0:
        if_siste = round(np_siste / FTP, 2)
        tss_siste = round((varighet_sek * np_siste * if_siste) / (FTP * 3600) * 100, 0)
    else:
        if_siste = None
        tss_siste = None

    ef_siste = round(np_siste / hr_siste, 2) if (np_siste and hr_siste) else None

    # IF-sone tekst
    if if_siste is not None:
        if if_siste < 0.75:
            if_sone = "restitusjon"
        elif if_siste < 0.85:
            if_sone = "rolig aerob (S1–S2)"
        elif if_siste < 0.95:
            if_sone = "maratonspesifikk (S2–S3)"
        elif if_siste < 1.05:
            if_sone = "terskel (S4)"
        else:
            if_sone = "VO2max (S5)"
    else:
        if_sone = "–"

    # ── Daglig TL (TSS) beregnet fra ATL-delta ───────────────
    # TL_i = (ATL_i - ATL_{i-1} * k7) / (1 - k7)  — PMC-matematikk
    k7 = math.exp(-1 / 7)
    tl_per_dag = []
    for i in range(1, len(trend_90d)):
        atl_prev = trend_90d[i - 1].get("atl") or 0
        atl_curr = trend_90d[i].get("atl") or 0
        tl = max(0.0, (atl_curr - atl_prev * k7) / (1 - k7))
        tl_per_dag.append({"dato": trend_90d[i]["dato"], "tl": round(tl, 1)})

    tl_7d = [e["tl"] for e in tl_per_dag if grense_7d < e["dato"] <= today_iso]
    tl_14d = [e["tl"] for e in tl_per_dag if grense_14d < e["dato"] <= today_iso]

    tss_sum_7d = round(sum(tl_7d)) if tl_7d else None
    tss_snitt_7d = round(sum(tl_7d) / len(tl_7d), 1) if tl_7d else None
    tss_sum_14d = round(sum(tl_14d)) if tl_14d else None
    tss_snitt_14d = round(sum(tl_14d) / len(tl_14d), 1) if tl_14d else None

    tl_7d_linje = " → ".join([
        f"{e['dato'][5:]}: {int(e['tl'])}"
        for e in tl_per_dag if grense_7d < e["dato"] <= today_iso
    ])

    # ── CTL historikk og projeksjon ──────────────────────────
    ctl_naa = fitness.get("ctl") or 0
    ctl_7d_ago = next((d["ctl"] for d in trend_90d if d["dato"] == grense_7d), None)
    ctl_14d_ago = next((d["ctl"] for d in trend_90d if d["dato"] == grense_14d), None)

    # Nødvendig gjennomsnittlig daglig TSS for å nå CTL 62 innen 12. april
    # CTL_n = CTL_0 * k42^n + TL * (1 - k42^n)  →  TL = (CTL_n - CTL_0 * k42^n) / (1 - k42^n)
    k42 = math.exp(-1 / 42)
    ctl_maal = 62
    dager_til_apr12 = (date(2026, 4, 12) - date.today()).days
    if dager_til_apr12 > 0 and ctl_naa:
        k42n = k42 ** dager_til_apr12
        tl_nodvendig = round((ctl_maal - ctl_naa * k42n) / (1 - k42n)) if k42n < 1 else None
    else:
        tl_nodvendig = None

    # NP-snitt siste terskeløkter for intensitetsreferanse
    np_verdier = [a.get("normalisert_watt") for a in historikk[-14:]
                  if a.get("normalisert_watt") and a.get("normalisert_watt", 0) > 200]
    np_snitt = round(sum(np_verdier) / len(np_verdier)) if np_verdier else None

    ukeplan = data.get("ukeplan", {})
    ukeplan_linjer = ""
    if ukeplan and ukeplan.get("okter"):
        linjer = []
        for o in ukeplan["okter"]:
            tag = " ← I DAG" if o["dato"] == today_iso else ""
            linjer.append(
                f"- {o['dato'][5:]} {o['type']}: {o['beskrivelse']} | "
                f"{o.get('dist_km', '–')} km | {o.get('tempo_min_km', '–')}/km | "
                f"{o.get('varighet_min', '–')} min{tag}"
            )
        ukeplan_linjer = "\n".join(linjer)

    kommentar_kontekst = bygg_kommentar_kontekst()
    kommentar_seksjon = f"\n\nSUBJEKTIVE TILBAKEMELDINGER SISTE 14 DAGER:\n{kommentar_kontekst}" if kommentar_kontekst else ""

    prompt = f"""MORGENDATA {data.get('dato', '')}
DAGER TIL HAMBURG: {(date(2026, 4, 26) - date.today()).days}

HELSE I DAG:
HRV: {helse.get('hrv', '–')} ms (balansert sone: 70–98 ms)
Hvilepuls: {helse.get('hvilepuls', '–')} bpm
Body Battery: {helse.get('bb_maks', '–')}/100 (min: {helse.get('bb_min', '–')})
Søvn: {helse.get('sovn_min', '–')} min (dyp: {helse.get('dyp_sovn_min', '–')} min | REM: {helse.get('rem_sovn_min', '–')} min)
Garmin søvnscore: {helse.get('sovn_score', '–')}/100
HRV status: {helse.get('hrv_status', '–')} | Baseline: {helse.get('hrv_baseline', '–')}
Søvnsnitt siste 7d: {sovn_snitt} min | Stress: {helse.get('stress_snitt', '–')}

FORM (PMC):
CTL: {ctl_14d_ago or '–'} (14d) → {ctl_7d_ago or '–'} (7d) → {ctl_naa} (i dag) [mål inn mot 12.4: {ctl_maal}]
ATL: {fitness.get('atl', '–')} | TSB: {fitness.get('tsb', '–')}
TSB-trend 7d: {' → '.join([str(d['tsb']) for d in trend_7d])}

SISTE ØKT — DETALJER:
{siste.get('navn', '–')} ({siste.get('dato', '–')})
Distanse: {siste.get('dist_km', '–')} km | Varighet: {siste.get('varighet_min', '–')} min | Tempo: {siste.get('snitt_tempo', '–')}
NP: {np_siste or '–'} W | Snitt: {siste.get('snitt_watt', '–')} W | IF: {if_siste or '–'} → {if_sone}
Estimert TSS: {tss_siste or '–'} | Suffer: {siste.get('suffer_score', '–')}
Puls: {hr_siste or '–'} bpm snitt / {siste.get('maks_puls', '–')} bpm maks
EF (NP/HR): {ef_siste or '–'} W/bpm | NP-snitt siste 14d løpeøkter: {np_snitt or '–'} W

BELASTNINGSAKKUMULERING (TSS fra ATL-beregning):
Daglig TSS siste 7d: {tl_7d_linje or '–'}
Sum TSS 7d: {tss_sum_7d or '–'} (snitt {tss_snitt_7d or '–'}/dag) | Sum TSS 14d: {tss_sum_14d or '–'} (snitt {tss_snitt_14d or '–'}/dag)
Nødvendig snitt-TSS frem til 12. april for å nå CTL {ctl_maal}: ~{tl_nodvendig or '–'} TSS/dag

HRV-TREND SISTE 7 DAGER:
{hrv_linje}

AKTIVITETER SISTE 7 DAGER:
{akt_linjer}

PLANLAGT UKE (ukeplan.json):
{ukeplan_linjer if ukeplan_linjer else "Ingen ukeplan registrert"}{kommentar_seksjon}"""

    return prompt


def main():
    dato = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"

    if not os.path.exists(json_fil):
        print(f"Finner ikke {json_fil}")
        return

    with open(json_fil, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Lagre eventuell kommentar fra trigger (knyttet til dagens dato / siste økt)
    okt_kommentar = os.environ.get("OKT_KOMMENTAR", "").strip()
    if okt_kommentar:
        strava = data.get("strava", {})
        aktiviteter = strava.get("aktiviteter", [])
        siste_okt_navn = aktiviteter[0].get("navn", "Ukjent økt") if aktiviteter else "Ukjent økt"
        lagre_okt_kommentar(dato, siste_okt_navn, okt_kommentar)
        print(f"Kommentar lagret: {okt_kommentar}")

    prompt = bygg_prompt(data)

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    melding = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
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
