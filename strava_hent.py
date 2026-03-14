import urllib.request
import urllib.parse
import json
import os
import time
from datetime import datetime, timezone

TOKEN_FILE = os.path.expanduser("~/Desktop/garmin-morgenrapport/strava_tokens.json")
DATA_DIR   = os.path.expanduser(".")

def hent_credentials():
    client_id     = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        if os.path.exists(TOKEN_FILE):
            with open(TOKEN_FILE) as f:
                tokens = json.load(f)
            env_file = os.path.expanduser("~/Desktop/garmin-morgenrapport/.env")
            env = {}
            with open(env_file) as f:
                for linje in f:
                    linje = linje.strip()
                    if linje and not linje.startswith("#") and "=" in linje:
                        k, _, v = linje.partition("=")
                        env[k.strip()] = v.strip()
            return env["STRAVA_CLIENT_ID"], env["STRAVA_CLIENT_SECRET"], tokens["refresh_token"]
        raise Exception("Mangler STRAVA-credentials")

    return client_id, client_secret, refresh_token

def refresh_access_token(client_id, client_secret, refresh_token):
    data = urllib.parse.urlencode({
        "client_id":     client_id,
        "client_secret": client_secret,
        "grant_type":    "refresh_token",
        "refresh_token": refresh_token,
    }).encode()
    req      = urllib.request.Request("https://www.strava.com/oauth/token", data=data, method="POST")
    response = urllib.request.urlopen(req)
    tokens   = json.loads(response.read())
    return tokens["access_token"], tokens["refresh_token"]

def strava_get(url, access_token):
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {access_token}")
    response = urllib.request.urlopen(req)
    return json.loads(response.read())

def hent_aktiviteter(access_token, dager=2):
    etter = int(time.time()) - (dager * 86400)
    url   = f"https://www.strava.com/api/v3/athlete/activities?after={etter}&per_page=30"
    return strava_get(url, access_token)

def hent_aktivitet_detalj(activity_id, access_token):
    url = f"https://www.strava.com/api/v3/activities/{activity_id}"
    return strava_get(url, access_token)

def hent_streams(activity_id, access_token):
    keys = "heartrate,cadence,watts,velocity_smooth,altitude,distance"
    url  = f"https://www.strava.com/api/v3/activities/{activity_id}/streams?keys={keys}&key_by_type=true"
    try:
        return strava_get(url, access_token)
    except Exception:
        return {}

def hent_profil(access_token):
    return strava_get("https://www.strava.com/api/v3/athlete", access_token)

def formater_aktivitet(a, detalj, streams):
    return {
        "id":               a["id"],
        "navn":             a.get("name"),
        "dato":             a.get("start_date_local", "")[:10],
        "type":             a.get("sport_type"),
        "dist_km":          round(a.get("distance", 0) / 1000, 2),
        "varighet_min":     round(a.get("moving_time", 0) / 60, 1),
        "snitt_puls":       a.get("average_heartrate"),
        "maks_puls":        a.get("max_heartrate"),
        "snitt_watt":       detalj.get("average_watts"),
        "normalisert_watt": detalj.get("weighted_average_watts"),
        "snitt_kadens":     a.get("average_cadence"),
        "kalorier":         detalj.get("calories"),
        "hoydemeter":       a.get("total_elevation_gain"),
        "snitt_tempo":      (
            f"{int(1000/a['average_speed']//60)}:{int(1000/a['average_speed']%60):02d} /km"
            if a.get("average_speed") and a["average_speed"] > 0 else None
        ),
        "suffer_score":     a.get("suffer_score"),
        "har_heartrate":    a.get("has_heartrate"),
        "privat":           a.get("private"),
        "streams":          {
            k: v.get("data", [])[:10]
            for k, v in streams.items()
        } if streams else {},
    }

def finn_garmin_fil(dato):
    filnavn = os.path.join(DATA_DIR, f"garmin_data_{dato}.json")
    if os.path.exists(filnavn):
        return filnavn
    return None

def main():
    dato = datetime.now().strftime("%Y-%m-%d")
    print(f"Strava-henting startet: {dato}")

    client_id, client_secret, refresh_token = hent_credentials()
    access_token, _ = refresh_access_token(client_id, client_secret, refresh_token)
    print("OK: Token refreshet.")

    print("Henter profil...")
    profil = hent_profil(access_token)
    print(f"OK: {profil.get('firstname')} {profil.get('lastname')}, FTP: {profil.get('ftp')}")

    print("Henter aktiviteter...")
    aktiviteter = hent_aktiviteter(access_token, dager=2)
    print(f"Fant {len(aktiviteter)} aktivitet(er).")

    strava_aktiviteter = []
    for a in aktiviteter:
        aid = a["id"]
        print(f"  Henter detaljer: {a.get('name')} ({aid})...")
        detalj  = hent_aktivitet_detalj(aid, access_token)
        streams = hent_streams(aid, access_token)
        strava_aktiviteter.append(formater_aktivitet(a, detalj, streams))

    strava_data = {
        "profil": {
            "athlete_id": profil.get("id"),
            "ftp":        profil.get("ftp"),
            "vekt":       profil.get("weight"),
        },
        "aktiviteter": strava_aktiviteter,
        "hentet":      datetime.now(timezone.utc).isoformat(),
    }

    garmin_fil = finn_garmin_fil(dato)
    if garmin_fil:
        print(f"Merger inn i {garmin_fil}...")
        with open(garmin_fil) as f:
            garmin_data = json.load(f)
        garmin_data["strava"] = strava_data
        with open(garmin_fil, "w") as f:
            json.dump(garmin_data, f, indent=2, ensure_ascii=False)
        print(f"OK: Strava-data merget inn i {garmin_fil}")
    else:
        ut_fil = os.path.join(DATA_DIR, f"strava_data_{dato}.json")
        with open(ut_fil, "w") as f:
            json.dump(strava_data, f, indent=2, ensure_ascii=False)
        print(f"OK: Lagret som {ut_fil}")

if __name__ == "__main__":
    main()
