#!/usr/bin/env python3
import os, sys, json, requests
from datetime import date, timedelta
from pathlib import Path

TP_AUTH_COOKIE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TP_AUTH_COOKIE", "")
ATHLETE_ID = 4974341
BASE = "https://tpapi.trainingpeaks.com"
DATO = date.today().isoformat()
JSON_FIL = f"garmin_data_{DATO}.json"

def hent_token():
    r = requests.get(f"{BASE}/users/v3/token",
        headers={"Cookie": f"Production_tpAuth={TP_AUTH_COOKIE}",
                 "Accept": "application/json",
                 "Origin": "https://app.trainingpeaks.com"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]["access_token"]

def lag_headers(token):
    return {"Authorization": f"Bearer {token}", "Accept": "application/json",
            "Origin": "https://app.trainingpeaks.com"}

def hent_fitness(token, dager=42):
    slutt = date.today()
    start = slutt - timedelta(days=dager)
    url = f"{BASE}/fitness/v1/athletes/{ATHLETE_ID}/reporting/performancedata/{start.isoformat()}/{slutt.isoformat()}"
    body = {"atlConstant": 7, "atlStart": 0, "ctlConstant": 42, "ctlStart": 0, "workoutTypes": []}
    r = requests.post(url, json=body, headers=lag_headers(token), timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        return {"dagens": {"ctl": None, "atl": None, "tsb": None}, "trend_7d": [], "trend_42d": []}
    siste = data[-1]
    return {
        "dagens": {
            "ctl": round(siste["ctl"], 1),
            "atl": round(siste["atl"], 1),
            "tsb": round(siste["tsb"], 1)
        },
        "trend_7d": [{"dato": d["workoutDay"][:10],
                      "ctl": round(d["ctl"], 1),
                      "atl": round(d["atl"], 1),
                      "tsb": round(d["tsb"], 1)} for d in data[-7:]],
        "trend_42d": [{"dato": d["workoutDay"][:10],
                       "ctl": round(d["ctl"], 1),
                       "atl": round(d["atl"], 1),
                       "tsb": round(d["tsb"], 1)} for d in data[::6][-7:]]
    }

def hent_planlagt_okt(token):
    url = f"{BASE}/plans/v1/athletes/{ATHLETE_ID}/appliedplans/{DATO}"
    r = requests.get(url, headers=lag_headers(token), timeout=15)
    if not r.ok:
        return None
    data = r.json()
    if not data:
        return None
    plan = data[0] if isinstance(data, list) else data
    return {
        "navn": plan.get("name") or plan.get("Name") or "Ukjent plan",
        "beskrivelse": str(plan)[:200]
    }

def main():
    if not TP_AUTH_COOKIE:
        print("TP_AUTH_COOKIE ikke satt — hopper over TrainingPeaks")
        return
    print("Henter TrainingPeaks-data...")
    try:
        token = hent_token()
        print("  Token OK")
    except Exception as e:
        print(f"  FEIL token: {e}")
        return

    tp_data = {}

    try:
        fitness = hent_fitness(token)
        tp_data["fitness"] = fitness
        d = fitness["dagens"]
        print(f"  CTL: {d['ctl']} | ATL: {d['atl']} | TSB: {d['tsb']}")
    except Exception as e:
        print(f"  FEIL fitness: {e}")
        tp_data["fitness"] = {"dagens": {"ctl": None, "atl": None, "tsb": None},
                              "trend_7d": [], "trend_42d": []}

    try:
        planlagt = hent_planlagt_okt(token)
        tp_data["planlagt_okt"] = planlagt
        print(f"  Planlagt: {planlagt['navn'] if planlagt else 'ingen'}")
    except Exception as e:
        print(f"  FEIL planlagt: {e}")
        tp_data["planlagt_okt"] = None

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
        print(f"  Lagret {fallback}")

if __name__ == "__main__":
    main()
