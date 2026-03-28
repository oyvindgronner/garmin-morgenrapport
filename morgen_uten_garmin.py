#!/usr/bin/env python3
"""
morgen_uten_garmin.py
=====================
Midlertidig morgenrapport basert på Strava, Stryd og TrainingPeaks.
Garmin-data mangler inntil rate limit er løst.
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
        "profil": {
            "ftp":   profil.get("ftp"),
            "vekt":  profil.get("weight"),
        },
        "aktiviteter": aktiviteter,
        "hentet": datetime.now(timezone.utc).isoformat(),
    }

# ─── TRAININGPEAKS ─────────────────────────────────────────

def hent_trainingpeaks():
    cookie = os.environ.get("TP_AUTH_COOKIE", "")
    if not cookie:
        print("  TP_AUTH_COOKIE ikke satt — hopper over")
        return {"fitness": {"dagens": {"ctl": None, "atl": None, "tsb": None}, "trend_7d": [], "trend_42d": []}, "planlagt_okt": None}

    print("Henter TrainingPeaks-data...")
    ATHLETE_ID = 4974341
    BASE = "https://tpapi.trainingpeaks.com"

    r = requests.get(f"{BASE}/users/v3/token",
        headers={"Cookie": f"Production_tpAuth={cookie}", "Accept": "application/json", "Origin": "https://app.trainingpeaks.com"},
        timeout=15)
    if not r.ok:
        print(f"  FEIL token: {r.status_code}")
        return {"fitness": {"dagens": {"ctl": None, "atl": None, "tsb": None}, "trend_7d": [], "trend_42d": []}, "planlagt_okt": None}

    token = r.json()["token"]["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Origin": "https://app.trainingpeaks.com"}

    slutt = date.today()
    start = slutt - timedelta(days=42)
    url = f"{BASE}/fitness/v1/athletes/{ATHLETE_ID}/reporting/performancedata/{start.isoformat()}/{slutt.isoformat()}"
    body = {"atlConstant": 7, "atlStart": 0, "ctlConstant": 42, "ctlStart": 0, "workoutTypes": []}

    r = requests.post(url, json=body, headers=headers, timeout=15)
    if not r.ok:
        print(f"  FEIL fitness: {r.status_code}")
        return {"fitness": {"dagens": {"ctl": None, "atl": None, "tsb": None}, "trend_7d": [], "trend_42d": []}, "planlagt_okt": None}

    data = r.json()
    siste = data[-1] if data else {}
    fitness = {
        "dagens": {
            "ctl": round(siste.get("ctl", 0), 1),
            "atl": round(siste.get("atl", 0), 1),
            "tsb": round(siste.get("tsb", 0), 1),
        },
        "trend_7d": [{"dato": d["workoutDay"][:10], "ctl": round(d["ctl"],1), "atl": round(d["atl"],1), "tsb": round(d["tsb"],1)} for d in data[-7:]],
        "trend_42d": [{"dato": d["workoutDay"][:10], "ctl": round(d["ctl"],1), "atl": round(d["atl"],1), "tsb": round(d["tsb"],1)} for d in data[::6][-7:]],
    }
    d = fitness["dagens"]
    print(f"  CTL: {d['ctl']} | ATL: {d['atl']} | TSB: {d['tsb']}")
    return {"fitness": fitness, "planlagt_okt": None}

# ─── HOVEDPROGRAM ──────────────────────────────────────────

def main():
    print(f"Morgenrapport (uten Garmin) – {DATO}")
    print("=" * 45)

    # Bygg JSON med tomme Garmin-felter
    data = {
        "dato": DATO,
        "_garmin_status": "UTILGJENGELIG – rate limit aktiv. Garmin-data mangler.",
        "hrv": {},
        "sovn": {},
        "dag": {},
        "body_battery": {},
        "treningsbelastning": {},
        "siste_aktiviteter": [],
        "strava": {},
        "trainingpeaks": {},
    }

    # Strava
    try:
        data["strava"] = hent_strava()
        if data["strava"]["aktiviteter"]:
            data["siste_aktiviteter"] = data["strava"]["aktiviteter"]
    except Exception as e:
        print(f"  FEIL Strava: {e}")

    # TrainingPeaks
    try:
        data["trainingpeaks"] = hent_trainingpeaks()
    except Exception as e:
        print(f"  FEIL TrainingPeaks: {e}")

    # Lagre JSON
    with open(JSON_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nJSON lagret: {JSON_FIL}")

if __name__ == "__main__":
    main()
