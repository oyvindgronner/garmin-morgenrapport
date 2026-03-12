#!/usr/bin/env python3
"""
garmin_morgen.py
================
Henter helsedata fra Garmin Connect og genererer et ferdig
dagsform-prompt til trener for å vurdere dagsform og om dagens trening bør endres eller om det bør gjøres andre tilpasninger.

Avhengigheter:
    pip install garminconnect garth
"""

import json
import os
import sys
from datetime import date
from getpass import getpass

try:
    from garminconnect import Garmin
except ImportError:
    print("Mangler garminconnect. Installer med:")
    print("  pip install garminconnect garth")
    sys.exit(1)

# ──────────────────────────────────────────────
# KONFIGURASJON
# ──────────────────────────────────────────────

TOKENSTI = os.path.expanduser("~/.garth")
DATO     = date.today()
DATO_STR = DATO.isoformat()

BASELINE_HRV     = None
BASELINE_RHR     = None
BASELINE_BB_MORN = None

# ──────────────────────────────────────────────
# INNLOGGING
# ──────────────────────────────────────────────

def logg_inn():
    """
    Logger inn med:
    1. Miljøvariabler (GARMIN_EMAIL + GARMIN_PASSWORD) — brukes av GitHub Actions
    2. Lagret token (~/.garth) — brukes lokalt på Mac etter første innlogging
    3. Manuell innlogging — første gang lokalt
    """
    epost   = os.environ.get("GARMIN_EMAIL")
    passord = os.environ.get("GARMIN_PASSWORD")

    if epost and passord:
        print("🔑 Logger inn med miljøvariabler (GitHub Actions-modus)...")
        api = Garmin(epost, passord)
        api.login()
        print("✅ Innlogget via miljøvariabler")
        return api

    api = Garmin()
    try:
        api.login(TOKENSTI)
        print(f"✅ Innlogget med lagret token ({TOKENSTI})")
        return api
    except Exception:
        pass

    print("Ingen lagret innlogging funnet. Logg inn:")
    epost   = input("Garmin e-post: ").strip()
    passord = getpass("Garmin passord: ")
    api = Garmin(epost, passord)
    api.login()
    api.garth.dump(TOKENSTI)
    print(f"✅ Innlogget og token lagret i {TOKENSTI}")
    return api

# ──────────────────────────────────────────────
# DATAHENTING
# ──────────────────────────────────────────────

def hent_sovn(api):
    try:
        data = api.get_sleep_data(DATO_STR)
        daglig = data.get("dailySleepDTO", {})
        return {
            "total_min":   daglig.get("sleepTimeSeconds", 0) // 60,
            "dyp_min":     daglig.get("deepSleepSeconds", 0) // 60,
            "rem_min":     daglig.get("remSleepSeconds", 0) // 60,
            "lett_min":    daglig.get("lightSleepSeconds", 0) // 60,
            "score":       daglig.get("sleepScores", {}).get("overall", {}).get("value"),
            "respiration": daglig.get("averageRespirationValue"),
            "spo2":        daglig.get("averageSpO2Value"),
            "stress_natt": daglig.get("avgSleepStress"),
        }
    except Exception as e:
        print(f"⚠️  Søvndata ikke tilgjengelig: {e}")
        return {}

def hent_hrv(api):
    try:
        data = api.get_hrv_data(DATO_STR)
        summary = data.get("hrvSummary", {})
        return {
            "nattlig_snitt":           summary.get("lastNight"),
            "status":                  summary.get("status"),
            "5min_hoy":                summary.get("lastNight5MinHigh"),
            "baseline_balansert_lav":  summary.get("baselineBalancedLow"),
            "baseline_balansert_hoy":  summary.get("baselineBalancedUpper"),
        }
    except Exception as e:
        print(f"⚠️  HRV-data ikke tilgjengelig: {e}")
        return {}

def hent_dagsstatus(api):
    try:
        data = api.get_user_summary(DATO_STR)
        return {
            "hvilepuls":         data.get("restingHeartRate"),
            "stress_snitt":      data.get("averageStressLevel"),
            "body_battery_maks": data.get("maxBodyBattery"),
            "body_battery_min":  data.get("minBodyBattery"),
            "skritt":            data.get("totalSteps"),
            "treningsevne":      data.get("trainingReadinessScore"),
        }
    except Exception as e:
        print(f"⚠️  Dagsstatus ikke tilgjengelig: {e}")
        return {}

def hent_treningsbelastning(api):
    try:
        data = api.get_training_status(DATO_STR)
        return {
            "status":       data.get("trainingLoadFeedback"),
            "aerob_load":   data.get("aerobicTrainingLoad"),
            "anaerob_load": data.get("anaerobicTrainingLoad"),
            "vo2max":       data.get("vo2MaxValue"),
        }
    except Exception as e:
        print(f"⚠️  Treningsbelastning ikke tilgjengelig: {e}")
        return {}

def hent_siste_aktiviteter(api, antall=5):
    try:
        aktiviteter = api.get_activities(0, antall)
        resultat = []
        for a in aktiviteter:
            if a.get("activityType", {}).get("typeKey") in ("running", "cycling", "swimming", "trail_running"):
                resultat.append({
                    "navn":           a.get("activityName"),
                    "dato":           a.get("startTimeLocal", "")[:10],
                    "type":           a.get("activityType", {}).get("typeKey"),
                    "dist_km":        round(a.get("distance", 0) / 1000, 2),
                    "varighet_min":   round(a.get("duration", 0) / 60, 1),
                    "snitt_puls":     a.get("averageHR"),
                    "maks_puls":      a.get("maxHR"),
                    "load":           round(a.get("activityTrainingLoad", 0), 1),
                    "treningseffekt": a.get("trainingEffectLabel"),
                    "vo2max":         a.get("vO2MaxValue"),
                    "bb_tap":         a.get("differenceBodyBattery"),
                })
        return resultat
    except Exception as e:
        print(f"⚠️  Aktiviteter ikke tilgjengelig: {e}")
        return []

# ──────────────────────────────────────────────
# HJELPEFUNKSJONER
# ──────────────────────────────────────────────

def min_til_tid(minutter):
    if not minutter:
        return "ukjent"
    t = minutter // 60
    m = minutter % 60
    return f"{t}t {m:02d}min"

def hrv_vurdering(hrv_data):
    status  = hrv_data.get("status", "")
    nattlig = hrv_data.get("nattlig_snitt")
    bal_lav = hrv_data.get("baseline_balansert_lav")
    bal_hoy = hrv_data.get("baseline_balansert_hoy")
    if status == "BALANCED":
        return "Normal (innenfor balansert sone)"
    elif status == "UNBALANCED":
        if nattlig and bal_lav and nattlig < bal_lav:
            return f"Lav – under baseline ({nattlig} ms vs. balansert sone {bal_lav}–{bal_hoy})"
        return "Ubalansert"
    elif status == "POOR":
        return "Svak – utenfor normal sone"
    return "Ikke tilgjengelig"

def bb_vurdering(verdi):
    if verdi is None:
        return "ikke tilgjengelig"
    if verdi >= 75:
        return f"{verdi} – God (klar for belastning)"
    elif verdi >= 50:
        return f"{verdi} – Middels (moderat økt)"
    elif verdi >= 25:
        return f"{verdi} – Lav (rolig økt)"
    else:
        return f"{verdi} – Svært lav (vurder hvil)"

def sovn_vurdering(sovn):
    total = sovn.get("total_min", 0)
    score = sovn.get("score")
    if not total:
        return "ikke tilgjengelig"
    tid = min_til_tid(total)
    score_txt = f", score {score}/100" if score else ""
    if total >= 420:
        return f"{tid}{score_txt} – Tilstrekkelig"
    elif total >= 360:
        return f"{tid}{score_txt} – Under anbefalt"
    else:
        return f"{tid}{score_txt} – For lite"

# ──────────────────────────────────────────────
# PROMPT-GENERATOR
# ──────────────────────────────────────────────

def lag_prompt(sovn, hrv, dag, load, aktiviteter):
    siste = aktiviteter[0] if aktiviteter else {}
    aktivitet_tekst = ""
    if siste:
        aktivitet_tekst = (
            f"  - {siste.get('navn', 'ukjent')} ({siste.get('dato')}): "
            f"{siste.get('dist_km')} km, {siste.get('varighet_min')} min, "
            f"snittspuls {siste.get('snitt_puls')} bpm, "
            f"load {siste.get('load')}, effekt: {siste.get('treningseffekt', 'ukjent')}"
        )
    else:
        aktivitet_tekst = "  - Ingen nylig aktivitet"

    historikk = ""
    for a in aktiviteter[:3]:
        historikk += (
            f"\n  - {a.get('dato')}: {a.get('navn')} | "
            f"{a.get('dist_km')} km | {a.get('varighet_min')} min | "
            f"load {a.get('load')} | puls snitt {a.get('snitt_puls')}"
        )

    prompt = f"""## DAGLIG DAGSFORM-ANALYSE – {DATO_STR}

### ROLLE
Du er en ekspert AI-treningscoach spesialisert på utholdenhetsidrett med fokus på
halvmaraton, helmaraton og stiløping. Analyser helsedata fra natten og gi en konkret
anbefaling for dagens trening.

---

### HELSEDATA FRA NATTEN OG MORGENEN

**HRV (Heart Rate Variability)**
- Nattlig snitt: {hrv.get('nattlig_snitt', 'ikke tilgjengelig')} ms
- 5-min maks: {hrv.get('5min_hoy', 'ikke tilgjengelig')} ms
- Status: {hrv_vurdering(hrv)}
- Balansert sone: {hrv.get('baseline_balansert_lav', '?')}–{hrv.get('baseline_balansert_hoy', '?')} ms

**Puls og stress**
- Hvilepuls: {dag.get('hvilepuls', 'ikke tilgjengelig')} bpm
- Gjennomsnittlig stressnivå: {dag.get('stress_snitt', 'ikke tilgjengelig')}/100

**Body Battery**
- Morgenverdi (maks i dag): {bb_vurdering(dag.get('body_battery_maks'))}
- Minimumverdi: {dag.get('body_battery_min', 'ikke tilgjengelig')}

**Søvn**
- Total søvn: {sovn_vurdering(sovn)}
- Dyp søvn: {min_til_tid(sovn.get('dyp_min'))}
- REM-søvn: {min_til_tid(sovn.get('rem_min'))}
- Lett søvn: {min_til_tid(sovn.get('lett_min'))}
- Nattlig respirasjonsrate: {sovn.get('respiration', 'ikke tilgjengelig')} ånd/min
- SpO2: {sovn.get('spo2', 'ikke tilgjengelig')} %
- Nattlig stressnivå: {sovn.get('stress_natt', 'ikke tilgjengelig')}

**Treningsstatus**
- Treningsevne (Training Readiness): {dag.get('treningsevne', 'ikke tilgjengelig')} / 100
- VO2max: {load.get('vo2max', 'ikke tilgjengelig')}
- Treningsbelastning status: {load.get('status', 'ikke tilgjengelig')}
- Aerob belastning: {load.get('aerob_load', 'ikke tilgjengelig')}
- Anaerob belastning: {load.get('anaerob_load', 'ikke tilgjengelig')}

---

### SISTE AKTIVITET
{aktivitet_tekst}

### TRENINGSHISTORIKK (siste 3 økter)
{historikk}

---

### PLANLAGT TRENINGSØKT I DAG
[FYLL INN: beskriv dagens planlagte økt – type, varighet, intensitet, soner]

---

### ANALYSE-INSTRUKSJONER
1. Vurder dagsformen helhetlig basert på alle målinger
2. Identifiser avvik fra det som er normalt (HRV, RHR, BB, søvn)
3. Gi en DAGSFORM-SCORE fra 1–10
4. Gi én klar anbefaling: Gjennomfør som planlagt / Modifiser / Hvil
5. Hvis modifiser: beskriv konkret hva som skal endres
6. Flagg mønstre som krever oppmerksomhet over tid
7. Gi 1–2 råd for restitusjon, søvn eller ernæring hvis relevant

---

### OUTPUT-FORMAT

**DAGSFORM:** [score/10] – [Svak / Under middels / Middels / God / Utmerket]

**SIGNAL-SAMMENDRAG:**
- HRV: [Lav/Normal/Høy] → [kort tolkning]
- Hvilepuls: [Lav/Normal/Høy] → [kort tolkning]
- Body Battery: [verdi] → [kort tolkning]
- Søvn: [kort tolkning]
- Treningsevne: [verdi] → [kort tolkning]

**ANBEFALING:** [Gjennomfør som planlagt / Modifiser / Hvil]

**KONKRET ØKTJUSTERING (hvis aktuelt):**
[Beskriv hva som endres og hvorfor]

**LANGSIKTIG MØNSTER:**
[Eventuelle trender å være obs på]

**COACH-MELDING:**
[Kort, motiverende avslutning]
"""
    return prompt

# ──────────────────────────────────────────────
# HOVEDPROGRAM
# ──────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"  GARMIN MORGENRAPPORT – {DATO_STR}")
    print(f"{'='*55}\n")

    api = logg_inn()
    print()

    print("📡 Henter data fra Garmin Connect...")
    sovn        = hent_sovn(api)
    hrv         = hent_hrv(api)
    dag         = hent_dagsstatus(api)
    load        = hent_treningsbelastning(api)
    aktiviteter = hent_siste_aktiviteter(api, antall=5)

    print("\n── RÅ HELSEDATA ──────────────────────────")
    print(f"  HRV nattlig snitt : {hrv.get('nattlig_snitt', '?')} ms  [{hrv.get('status', '?')}]")
    print(f"  Hvilepuls         : {dag.get('hvilepuls', '?')} bpm")
    print(f"  Body Battery morn : {dag.get('body_battery_maks', '?')} / 100")
    print(f"  Søvn total        : {min_til_tid(sovn.get('total_min'))}  (score: {sovn.get('score', '?')})")
    print(f"  Dyp søvn          : {min_til_tid(sovn.get('dyp_min'))}")
    print(f"  REM               : {min_til_tid(sovn.get('rem_min'))}")
    print(f"  Treningsevne      : {dag.get('treningsevne', '?')} / 100")
    print(f"  VO2max            : {load.get('vo2max', '?')}")
    print(f"  Treningsstatus    : {load.get('status', '?')}")
    if aktiviteter:
        print(f"\n  Siste økt: {aktiviteter[0].get('navn')} ({aktiviteter[0].get('dato')})")
        print(f"  {aktiviteter[0].get('dist_km')} km | {aktiviteter[0].get('varighet_min')} min | "
              f"puls {aktiviteter[0].get('snitt_puls')} bpm | load {aktiviteter[0].get('load')}")

    prompt = lag_prompt(sovn, hrv, dag, load, aktiviteter)

    prompt_fil = os.path.expanduser(f"~/garmin_prompt_{DATO_STR}.txt")
    with open(prompt_fil, "w", encoding="utf-8") as f:
        f.write(prompt)

    print(f"\n{'='*55}")
    print(f"  ✅ FERDIG!")
    print(f"{'='*55}")
    print(f"\n📋 Prompt lagret til: {prompt_fil}")
    print("\n── CLAUDE-PROMPT ──────────────────────────\n")
    print(prompt)
    print("\n───────────────────────────────────────────")

    json_fil = os.path.expanduser(f"~/garmin_data_{DATO_STR}.json")
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump({
            "dato": DATO_STR,
            "sovn": sovn,
            "hrv": hrv,
            "dag": dag,
            "treningsbelastning": load,
            "siste_aktiviteter": aktiviteter,
        }, f, ensure_ascii=False, indent=2)
    print(f"💾 Rådata lagret: {json_fil}\n")

if __name__ == "__main__":
    main()
