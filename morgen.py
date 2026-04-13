#!/usr/bin/env python3
"""
morgen.py
=========
Morgenrapport basert på TrainingPeaks (HRV, søvn, BB, CTL/ATL/TSB) og Strava.
Inkluderer 90 dagers historikk for full kontekst i analyse.
"""

import json
import os
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

    # Historikk siste 90 dager — kun nøkkeldata (henter alle sider)
    etter_90d = int(time.time()) - (90 * 86400)
    alle_raw = []
    page = 1
    while True:
        side = strava_get(
            f"https://www.strava.com/api/v3/athlete/activities?after={etter_90d}&per_page=100&page={page}",
            token
        )
        if not side:
            break
        alle_raw.extend(side)
        if len(side) < 100:
            break
        page += 1

    # Siste 3 aktiviteter = de nyeste fra 90-dagershistorikken (unngår tidsbegrenset vindu)
    siste_raw = sorted(alle_raw, key=lambda a: a.get("start_date", ""), reverse=True)[:3]

    def formater_full(a):
        detalj = strava_get(f"https://www.strava.com/api/v3/activities/{a['id']}", token)
        try:
            streams = strava_get(
                f"https://www.strava.com/api/v3/activities/{a['id']}/streams?keys=heartrate,watts,cadence,velocity_smooth&key_by_type=true",
                token
            )
        except Exception:
            streams = {}
        dist = a.get("distance", 0)
        fart = a.get("average_speed", 0)
        return {
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
            "streams": {k: v.get("data", []) for k, v in streams.items()} if streams else {},
        }

    def formater_lett(a):
        dist = a.get("distance", 0)
        fart = a.get("average_speed", 0)
        return {
            "dato":         a.get("start_date_local", "")[:10],
            "navn":         a.get("name"),
            "type":         a.get("sport_type"),
            "dist_km":      round(dist / 1000, 2),
            "varighet_min": round(a.get("moving_time", 0) / 60, 1),
            "snitt_tempo":  f"{int(1000/fart//60)}:{int(1000/fart%60):02d} /km" if fart > 0 else None,
            "snitt_puls":   a.get("average_heartrate"),
            "suffer_score": a.get("suffer_score"),
        }

    aktiviteter = [formater_full(a) for a in siste_raw[:3]]
    historikk = [formater_lett(a) for a in alle_raw]

    print(f"  OK: {len(aktiviteter)} aktivitet(er) | {len(historikk)} historiske (90d)")
    return {
        "profil": {"ftp": profil.get("ftp"), "vekt": profil.get("weight")},
        "aktiviteter": aktiviteter,
        "historikk_90d": historikk,
        "hentet": datetime.now(timezone.utc).isoformat(),
    }

# ─── TRAININGPEAKS ─────────────────────────────────────────

def hent_tp_token(cookie):
    r = requests.get("https://tpapi.trainingpeaks.com/users/v3/token",
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

    # CTL / ATL / TSB siste 90 dager
    try:
        slutt = date.today()
        start = slutt - timedelta(days=90)
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
            "trend_90d": [{"dato": d["workoutDay"][:10], "ctl": round(d["ctl"],1),
                           "atl": round(d["atl"],1), "tsb": round(d["tsb"],1)} for d in data],
        }
        d = tp_data["fitness"]["dagens"]
        print(f"  CTL: {d['ctl']} | ATL: {d['atl']} | TSB: {d['tsb']}")
    except Exception as e:
        print(f"  FEIL fitness: {e}")
        tp_data["fitness"] = {"dagens": {"ctl": None, "atl": None, "tsb": None},
                              "trend_7d": [], "trend_90d": []}

    # Helsedata siste 90 dager
    try:
        slutt = date.today().isoformat()
        start = (date.today() - timedelta(days=90)).isoformat()
        url = f"{BASE}/metrics/v3/athletes/{ATHLETE_ID}/consolidatedtimedmetrics/{start}/{slutt}"
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        mdata = r.json()

        historikk_helse = []
        helsedata_dagens = {}

        for dag in mdata:
            dato = dag.get("timeStamp", "")[:10]
            hrv = hvile = bb_maks = bb_min = sovn = dyp = rem = stress = sovn_score = None
            for felt in dag.get("details", []):
                label = felt.get("label")
                value = felt.get("value")
                if label == "HRV": hrv = value
                elif label == "Pulse": hvile = value
                elif label == "Body Battery" and isinstance(value, list):
                    bb_min = value[0]; bb_maks = value[1]
                elif label == "Sleep Hours": sovn = round(value * 60)
                elif label == "Time in Deep Sleep": dyp = round(value * 60)
                elif label == "Time in REM Sleep": rem = round(value * 60)
                elif label == "Stress Level" and isinstance(value, list):
                    stress = round(value[2], 1)
                elif label == "Sleep Score": sovn_score = round(value)

            rad = {"dato": dato, "hrv": hrv, "hvilepuls": hvile,
                   "bb_maks": bb_maks, "bb_min": bb_min,
                   "sovn_min": sovn, "dyp_sovn_min": dyp,
                   "rem_sovn_min": rem, "stress_snitt": stress,
                   "sovn_score": sovn_score}
            historikk_helse.append(rad)
            if dato == DATO:
                helsedata_dagens = rad

        tp_data["helsedata"] = helsedata_dagens
        tp_data["helsedata_90d"] = historikk_helse
        print(f"  HRV: {helsedata_dagens.get('hrv','–')} ms | "
              f"Hvilepuls: {helsedata_dagens.get('hvilepuls','–')} bpm | "
              f"BB: {helsedata_dagens.get('bb_maks','–')} | "
              f"Søvn: {helsedata_dagens.get('sovn_min','–')} min")
    except Exception as e:
        print(f"  FEIL helsedata: {e}")
        tp_data["helsedata"] = {}
        tp_data["helsedata_90d"] = []

    return tp_data

# ─── UKEPLAN ───────────────────────────────────────────────

def hent_ukeplan():
    if os.path.exists("ukeplan.json"):
        with open("ukeplan.json", encoding="utf-8") as f:
            return json.load(f)
    return {}

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

    data["ukeplan"] = hent_ukeplan()
    if data["ukeplan"]:
        antall = len(data["ukeplan"].get("okter", []))
        print(f"Ukeplan lastet: {antall} økt(er) (uke {data['ukeplan'].get('uke', '–')})")

    with open(JSON_FIL, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nJSON lagret: {JSON_FIL}")

if __name__ == "__main__":
    main()
