#!/usr/bin/env python3
"""
tp_morgen.py — Henter CTL/ATL/TSB, trender, planlagt økt og Stryd-wattdata
fra TrainingPeaks og merger inn i garmin_data_DATO.json
"""

import os
import json
import requests
from datetime import date, timedelta
from pathlib import Path


TP_AUTH_COOKIE = os.environ.get("TP_AUTH_COOKIE", "")
TPAPI_URL = "https://tpapi.trainingpeaks.com"

DATO = date.today().isoformat()
JSON_FIL = f"garmin_data_{DATO}.json"


def hent_token_og_id():
    # Steg 1: Hent access token
    url = f"{TPAPI_URL}/users/v3/token"
    headers = {
        "Cookie": f"Production_tpAuth={TP_AUTH_COOKIE}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://app.trainingpeaks.com",
        "Referer": "https://app.trainingpeaks.com/",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()
    token_dict = data.get("token", {})
    access_token = token_dict.get("access_token", "")

    # Steg 2: Hent userId fra /users/v3/user — ligger nestet under "user"
    r2 = requests.get(
        f"{TPAPI_URL}/users/v3/user",
        headers={
            "Cookie": f"Production_tpAuth={TP_AUTH_COOKIE}",
            "Accept": "application/json",
            "Origin": "https://app.trainingpeaks.com",
            "Referer": "https://app.trainingpeaks.com/",
        },
        timeout=15
    )
    r2.raise_for_status()
    user_data = r2.json()

    # userId ligger under "user"-nøkkelen
    user_obj = user_data.get("user", user_data)
    athlete_id = (
        user_obj.get("userId")
        or user_obj.get("athleteId")
        or user_obj.get("Id")
        or user_obj.get("id")
    )
    print(f"  userId hentet: {athlete_id}")
    return access_token, athlete_id


def lag_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://app.trainingpeaks.com",
        "Referer": "https://app.trainingpeaks.com/",
    }


def hent_fitness_trend(athlete_id, token, dager=42):
    slutt = date.today()
    start = slutt - timedelta(days=dager)
    url = (
        f"{TPAPI_URL}/fitness/v3/athletes/{athlete_id}/metrics"
        f"?startDate={start.isoformat()}&endDate={slutt.isoformat()}"
    )
    r = requests.get(url, headers=lag_headers(token), timeout=15)
    r.raise_for_status()
    data = r.json()

    if not isinstance(data, list) or not data:
        return {"dagens": {"ctl": None, "atl": None, "tsb": None}, "trend_7d": [], "trend_42d": []}

    def parse_dag(d):
        return {
            "dato": d.get("date") or d.get("Date") or "",
            "ctl": round(float(d.get("ctl") or d.get("Ctl") or 0), 1),
            "atl": round(float(d.get("atl") or d.get("Atl") or 0), 1),
            "tsb": round(float(d.get("tsb") or d.get("Tsb") or 0), 1),
        }

    alle = [parse_dag(d) for d in data]
    siste = alle[-1]

    return {
        "dagens": {"ctl": siste["ctl"], "atl": siste["atl"], "tsb": siste["tsb"]},
        "trend_7d": alle[-7:],
        "trend_42d": alle[::6][-7:],
    }


def hent_planlagt_okt(athlete_id, token):
    url = (
        f"{TPAPI_URL}/workouts/v1/athletes/{athlete_id}/workouts"
        f"?startDate={DATO}&endDate={DATO}"
    )
    r = requests.get(url, headers=lag_headers(token), timeout=15)
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


def hent_stryd_okter(athlete_id, token, dager=14):
    slutt = date.today()
    start = slutt - timedelta(days=dager)
    url = (
        f"{TPAPI_URL}/workouts/v1/athletes/{athlete_id}/workouts"
        f"?startDate={start.isoformat()}&endDate={slutt.isoformat()}"
    )
    r = requests.get(url, headers=lag_headers(token), timeout=15)
    r.raise_for_status()
    data = r.json()

    okter = data if isinstance(data, list) else data.get("workouts", [])

    lopeokt = [
        o for o in okter
        if (o.get("Completed") or o.get("completed"))
        and (
            "run" in str(o.get("WorkoutTypeValueId") or o.get("workoutType") or "").lower()
            or o.get("WorkoutTypeValueId") in [1, 3, 25]
        )
    ]

    resultat = []
    for o in lopeokt[:5]:
        np_watt = o.get("NormalizedPower") or o.get("normalizedPower")
        avg_watt = o.get("Power") or o.get("power") or o.get("AvgPower") or o.get("avgPower")
        tss = o.get("Tss") or o.get("tss")
        if_val = o.get("IntensityFactor") or o.get("intensityFactor")

        resultat.append({
            "dato": o.get("WorkoutDay") or o.get("workoutDay") or o.get("date") or "",
            "navn": o.get("Title") or o.get("title") or "Løpeøkt",
            "dist_km": round((o.get("Distance") or o.get("distance") or 0) / 1000, 2),
            "varighet_min": round((o.get("TotalTime") or o.get("totalTime") or 0) / 60, 1),
            "tss": round(float(tss), 1) if tss else None,
            "np_watt": round(float(np_watt), 0) if np_watt else None,
            "avg_watt": round(float(avg_watt), 0) if avg_watt else None,
            "if": round(float(if_val), 3) if if_val else None,
        })

    return resultat


def main():
    if not TP_AUTH_COOKIE:
        print("TP_AUTH_COOKIE ikke satt — hopper over TrainingPeaks")
        return

    print("Henter TrainingPeaks-data...")

    try:
        token, athlete_id = hent_token_og_id()
        print(f"  Athlete ID: {athlete_id}")
    except Exception as e:
        print(f"  FEIL token/ID: {e}")
        return

    if not athlete_id:
        print("  FEIL: Athlete ID er None — avbryter")
        return

    tp_data = {}

    try:
        fitness = hent_fitness_trend(athlete_id, token, dager=42)
        tp_data["fitness"] = fitness
        d = fitness["dagens"]
        print(f"  CTL: {d['ctl']} | ATL: {d['atl']} | TSB: {d['tsb']}")
        print(f"  Trend 7d: {len(fitness['trend_7d'])} dager")
        print(f"  Trend 42d: {len(fitness['trend_42d'])} snapshots")
    except Exception as e:
        print(f"  FEIL fitness: {e}")
        tp_data["fitness"] = {
            "dagens": {"ctl": None, "atl": None, "tsb": None},
            "trend_7d": [],
            "trend_42d": [],
        }

    try:
        planlagt = hent_planlagt_okt(athlete_id, token)
        tp_data["planlagt_okt"] = planlagt
        if planlagt:
            print(f"  Planlagt: {planlagt['navn']} ({planlagt['varighet_min']} min, TSS: {planlagt['tss_planlagt']})")
        else:
            print("  Ingen planlagt økt i dag")
    except Exception as e:
        print(f"  FEIL planlagt økt: {e}")
        tp_data["planlagt_okt"] = None

    try:
        stryd = hent_stryd_okter(athlete_id, token, dager=14)
        tp_data["stryd_okter"] = stryd
        print(f"  Stryd-økter hentet: {len(stryd)} stk")
        for o in stryd:
            print(f"    {o['dato']} — TSS: {o['tss']} | NP: {o['np_watt']}W | IF: {o['if']}")
    except Exception as e:
        print(f"  FEIL Stryd-økter: {e}")
        tp_data["stryd_okter"] = []

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
