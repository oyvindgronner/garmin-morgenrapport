#!/usr/bin/env python3
"""
morgen.py
=========
Morgenrapport basert på TrainingPeaks (HRV, søvn, BB, CTL/ATL/TSB) og Strava.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.parse
import requests
from datetime import date, timedelta, datetime, timezone

DATO = date.today().isoformat()
JSON_FIL = f"garmin_data_{DATO}.json"

# ─── STRAVA ────────────────────────────────────────────────

def strava_refresh_token():
    data = urllib.parse.urlencode({
        "client_id":     os.environ["STRAVA_CLIENT_ID"],
        "client_secret": os.environ["STRAVA_CLIENT_SECRET"],
        "grant_type":    "refresh_token",
        "refresh_token": os.environ["STRAVA_REFRESH_TOKEN"],
    }).encode()
    req = urllib.request.Request("https://www.strava.com/oauth/token", data=data, method="POST")
    return json.loads(urllib.request.urlopen(req).read())["access_token"]

def strava_get(url, token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    return json.loads(urllib.request.urlopen(req).read())

def hent_strava():
    print("Henter Strava-data...")
    token = strava_refresh_token()
    profil = strava_get("https://www.strava.com/api/v3/athlete", token)
    etter = int(time.time()) - (3 * 86400)
    aktiviteter_raw = strava_get(
        f"https://www.strava.com/api/v3/athlete/activities?after={etter}&per_page=10",
        token
    )
    aktiviteter = []
    for a in aktiviteter_raw[:3]:
        aid = a["id"]
        detalj = strava_get(f"https://www.strava.com/api/v3/activities/{aid}", token)
        try:
            streams = strava_get(
                f"https://www.strava.com/api/v3/activities/{aid}/streams?keys=heartrate,watts,cadence,velocity_smooth&key_by_type=true",
                token
            )
        except Exception:
            streams = {}
        dist = a.get("distance", 0)
        fart = a.get("average_speed", 0)
        aktiviteter.append({
            "navn":             a.get("name"),
            "dato":             a.get("start_date_local", "")[:10],
            "type":             a.get("sport_type"),
            "dist_km":          round(dist / 1000, 2),
            "varighet_min":     round(a.get("moving_time", 0) / 60, 1),
            "snitt_tempo":      f"{int(1000/fart//60)}:{int(1000/fart%60):02d} /km" if fart > 0 else None,
            "snitt_puls":       a.get("average_heartrate"),
            "maks_puls":        a.get("max_heartrate"),
            "snitt_watt":       detalj.get("average_watts"),
            "normalisert_watt": detalj.get("weighted_average_watts"),
            "suffer_score":     a.get("suffer_score"),
            "kalorier":         detalj.get("calories"),
            "hoydemeter":       a.get("total_elevation_gain"),
            "streams": {k: v.get("data", [])[:10] for k, v in streams.items()} if streams else {},
        })
    print(f"  OK: {len(aktiviteter)} aktivitet(er)")
    return {
        "profil": {"ftp": profil.get("ftp"), "vekt": profil.get("weight")},
        "aktiviteter": aktiviteter,
        "hentet": datetime.now(timezone.utc).isoformat(),
    }

# ─── TRAININGPEAKS ─────────────────────────────────────────

def hent_tp_token(cookie):
    BASE = "https://tpapi.trainingpeaks.com"
    r = requests.get(f"{BASE}/users/v3/token",
        headers={"Cookie": f"Production_tpAuth={cookie}",
                 "Accept": "application/json",
                 "Origin": "https://app.trainingpeaks.com"}, timeout=15)
    r.raise_for_status()
    return r.json()["token"]["access_token"]

def hent_trainingpeaks():
    cookie = os.environ.get("TP_AUTH_COOKIE", "")
    if not cookie:
        print("  TP_AUTH_COOKIE ikke satt — hopper over")
        return {}

    print("Henter TrainingPeaks-data...")
    ATHLETE_ID = 4974341
    BASE = "https://tpapi.trainingpeaks.com"

    try:
        token = hent_tp_token(cookie)
        print("  Token OK")
    except Exception as e:
        print(f"  FEIL token: {e}")
        return {}

    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/json",
               "Origin": "https://app.trainingpeaks.com"}

    tp_data = {}

    # CTL / ATL / TSB
    try:
        slutt = date.today()
        start = slutt - timedelta(days=42)
        url = f"{BASE}/fitness/v1/athletes/{ATHLETE_ID}/reporting/performancedata/{start.isoformat()}/{slutt.isoformat()}"
        body = {"atlConstant": 7, "atlStart": 0, "ctlConstant": 42, "ctlStart": 0, "workoutTypes": []}
        r = requests.post(url, json=body, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        siste = data[-1] if data else {}
        tp_data["fitness"] = {
            "dagens": {
                "ctl": round(siste.get("ctl", 0), 1),
                "atl": round(siste.get("atl", 0), 1),
                "tsb": round(siste.get("tsb", 0), 1),
            },
            "trend_7d": [{"dato": d["workoutDay"][:10], "ctl": round(d["ctl"],1),
                          "atl": round(d["atl"],1), "tsb": round(d["tsb"],1)} for d in data[-7:]],
        }
        d = tp_data["fitness"]["dagens"]
        print(f"  CTL: {d['ctl']} | ATL: {d['atl']} | TSB: {d['tsb']}")
    except Exception as e:
        print(f"  FEIL fitness: {e}")
        tp_data["fitness"] = {"dagens": {"ctl": None, "atl": None, "tsb": None}, "trend_7d": []}

    # HRV, søvn, Body Battery, hvilepuls, stress
    try:
        url = f"{BASE}/metrics/v3/athletes/{ATHLETE_ID}/consolidatedtimedmetrics/{DATO}/{DATO}"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        mdata = r.json()
        dagens = next((d for d in mdata if d.get("timeStamp", "").startswith(DATO)), None)
        helsedata = {}
        if dagens:
            for felt in dagens.get("details", []):
                label = felt.get("label")
                value = felt.get("value")
                if label == "HRV":
                    helsedata["hrv_nattlig_snitt"] = value
                elif label == "Sleep Hours":
                    helsedata["sovn_min"] = round(value * 60)
                elif label == "Time in Deep Sleep":
                    helsedata["dyp_sovn_min"] = round(value * 60)
                elif label == "Time in REM Sleep":
                    helsedata["rem_sovn_min"] = round(value * 60)
                elif label == "Time in Light Sleep":
                    helsedata["lett_sovn_min"] = round(value * 60)
                elif label == "Body Battery":
                    if isinstance(value, list) and len(value) >= 2:
                        helsedata["bb_min"] = value[0]
                        helsedata["bb_maks"] = value[1]
                elif label == "Stress Level":
                    if isinstance(value, list) and len(value) >= 3:
                        helsedata["stress_snitt"] = round(value[2], 1)
                elif label == "Pulse":
                    helsedata["hvilepuls"] = value
        tp_data["helsedata"] = helsedata
        print(f"  HRV: {helsedata.get('hrv_nattlig_snitt','–')} ms | "
              f"Hvilepuls: {helsedata.get('hvilepuls','–')} bpm | "
              f"BB: {helsedata.get('bb_maks','–')} | "
              f"Søvn: {helsedata.get('sovn_min','–')} min")
    except Exception as e:
        print(f"  FEIL helsedata: {e}")
        tp_data["helsedata"] = {}

    return tp_data

# ─── HOVEDPROGRAM ──────────────────────────────────────────

def main():
    print(f"Morgenrapport – {DATO}")
    print("=" * 45)

    data = {
        "dato": DATO,
        "siste_aktiviteter": [],
        "strava": {},
        "trainingpeaks": {},
    }

    try:
        data["strava"] = hent_strava()
        data["siste_aktiviteter"] = data["strava"].get("aktiviteter", [])
    except Exception as e:
        print(f"  FEIL Strava: {e}")

    try:
        data["trainingpeaks"] = hent_trainingpeaks()
    except Exception as e:
        print(f"  FEIL TrainingPeaks: {e}")

    with open(JSON_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nJSON lagret: {JSON_FIL}")

if __name__ == "__main__":
    main()
