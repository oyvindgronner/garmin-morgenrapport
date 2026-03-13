#!/usr/bin/env python3
"""
tp_morgen.py — Henter CTL/ATL/TSB og planlagt økt fra TrainingPeaks
og merger dataene inn i garmin_data_DATO.json
"""

import os
import json
import requests
from datetime import date, timedelta
from pathlib import Path


TP_AUTH_COOKIE = os.environ.get("TP_AUTH_COOKIE", "")
BASE_URL = "https://tpapi.trainingpeaks.com"

DATO = date.today().isoformat()
JSON_FIL = f"garmin_data_{DATO}.json"


def lag_headers():
    return {
        "Cookie": f"Production_tpAuth={TP_AUTH_COOKIE}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://app.trainingpeaks.com",
        "Referer": "https://app.trainingpeaks.com/",
    }


def hent_bruker_id():
    url = f"{BASE_URL}/users/v3/user"
    r = requests.get(url, headers=lag_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()
    return data.get("userId") or data.get("Id")


def hent_fitness(athlete_id, dager=3):
    slutt = date.today()
    start = slutt - timedelta(days=dager)
    url = (
        f"{BASE_URL}/fitness/v3/athletes/{athlete_id}/metrics"
        f"?startDate={start.isoformat()}&endDate={slutt.isoformat()}"
    )
    r = requests.get(url, headers=lag_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, list) and data:
        siste = data[-1]
        return {
            "ctl": round(siste.get("ctl") or siste.get("Ctl") or 0, 1),
            "atl": round(siste.get("atl") or siste.get("Atl") or 0, 1),
            "tsb": round(siste.get("tsb") or siste.get("Tsb") or 0, 1),
        }
    return {"ctl": None, "atl": None, "tsb": None}


def hent_planlagt_okt(athlete_id):
    url = (
        f"{BASE_URL}/workouts/v1/athletes/{athlete_id}/workouts"
        f"?startDate={DATO}&endDate={DATO}"
    )
    r = requests.get(url, headers=lag_headers(), timeout=15)
    r.raise_for_status()
    data = r.json()

    okter = data if isinstance(data, list) else data.get("workouts", [])
    planlagte = [o for o in okter if not o.get("Completed") and not o.get("completed")]

    if not planlagte:
        return None

    o = planlagte[0]
    return {
        "navn": o.get("Title") or o.get("title") or "Ukjent økt",
        "type": o.get("WorkoutTypeValueId") or o.get("workoutType") or "",
        "varighet_min": round((o.get("TotalTime") or o.get("totalTime") or 0) / 60, 0),
        "tss_planlagt": o.get("Tss") or o.get("tss"),
        "beskrivelse": (o.get("Description") or o.get("description") or "")[:300],
    }


def main():
    if not TP_AUTH_COOKIE:
        print("TP_AUTH_COOKIE ikke satt — hopper over TrainingPeaks")
        return

    print("Henter TrainingPeaks-data...")

    try:
        athlete_id = hent_bruker_id()
        print(f"  Athlete ID: {athlete_id}")
    except Exception as e:
        print(f"  FEIL: Kunne ikke hente bruker-ID: {e}")
        return

    tp_data = {}

    try:
        fitness = hent_fitness(athlete_id)
        tp_data["fitness"] = fitness
        print(f"  CTL: {fitness['ctl']} | ATL: {fitness['atl']} | TSB: {fitness['tsb']}")
    except Exception as e:
        print(f"  FEIL fitness: {e}")
        tp_data["fitness"] = {"ctl": None, "atl": None, "tsb": None}

    try:
        planlagt = hent_planlagt_okt(athlete_id)
        tp_data["planlagt_okt"] = planlagt
        if planlagt:
            print(f"  Planlagt: {planlagt['navn']} ({planlagt['varighet_min']} min)")
        else:
            print("  Ingen planlagt økt i dag")
    except Exception as e:
        print(f"  FEIL planlagt økt: {e}")
        tp_data["planlagt_okt"] = None

    # Merge inn i eksisterende Garmin-JSON
    json_path = Path(JSON_FIL)
    if json_path.exists():
        with open(json_path) as f:
            garmin_data = json.load(f)
        garmin_data["trainingpeaks"] = tp_data
        with open(json_path, "w") as f:
            json.dump(garmin_data, f, ensure_ascii=False, indent=2)
        print(f"  Merget inn i {JSON_FIL}")
    else:
        fallback = f"tp_data_{DATO}.json"
        with open(fallback, "w") as f:
            json.dump({"dato": DATO, "trainingpeaks": tp_data}, f, ensure_ascii=False, indent=2)
        print(f"  Garmin-fil ikke funnet — lagret {fallback}")


if __name__ == "__main__":
    main()
