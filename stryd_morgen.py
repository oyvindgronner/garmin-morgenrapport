import requests
import json
import os
from datetime import date, timedelta

STRYD_AUTH_URL = "https://www.stryd.com/b/email/signin"
STRYD_API_BASE = "https://www.stryd.com/b/api/v1"


def logg_inn(epost: str, passord: str) -> tuple[str, str]:
    response = requests.post(
        STRYD_AUTH_URL,
        json={"email": epost, "password": passord},
        timeout=30
    )
    if response.status_code != 200:
        raise Exception(f"Innlogging feilet: {response.status_code} — {response.text}")

    data = response.json()
    print(f"🔍 Innloggingsrespons-nøkler: {list(data.keys())}")

    token = data.get("token") or data.get("sessionToken") or data.get("access_token")
    user_id = data.get("id") or data.get("userId") or data.get("user_id")

    if not token:
        raise Exception(f"Fant ikke token i respons")

    print(f"✅ Innlogget på Stryd | user_id: {user_id}")
    return token, str(user_id) if user_id else ""


def hent_aktiviteter(token: str, user_id: str, dager: int = 14) -> list:
    headers = {"Authorization": f"Bearer: {token}"}
    til_dato = date.today() + timedelta(days=1)
    fra_dato = til_dato - timedelta(days=dager)

    urls = [
        f"{STRYD_API_BASE}/users/{user_id}/activities/calendar?srtDate={fra_dato.strftime('%m-%d-%Y')}&endDate={til_dato.strftime('%m-%d-%Y')}&sortBy=StartDate",
        f"{STRYD_API_BASE}/users/{user_id}/activities",
        f"{STRYD_API_BASE}/powercenter/activities?srtDate={fra_dato.strftime('%m-%d-%Y')}&endDate={til_dato.strftime('%m-%d-%Y')}",
        f"{STRYD_API_BASE}/activities",
    ]

    for url in urls:
        response = requests.get(url, headers=headers, timeout=30)
        kort = url.split('/b/api/v1')[1][:60]
        print(f"  {kort} → {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            aktiviteter = data.get("activities", []) if isinstance(data, dict) else data
            print(f"✅ Hentet {len(aktiviteter)} aktiviteter")
            return aktiviteter

    print("⚠️ Ingen aktiviteter hentet")
    return []


def hent_løperprofil(token: str, user_id: str) -> dict:
    headers = {"Authorization": f"Bearer: {token}"}

    endepunkter = [
        f"/users/{user_id}/profile",
        f"/users/{user_id}",
        f"/athletes/{user_id}",
        "/users/profile",
        "/athlete",
    ]

    for ep in endepunkter:
        response = requests.get(f"{STRYD_API_BASE}{ep}", headers=headers, timeout=30)
        print(f"  {ep} → {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Hentet profil fra {ep}")
            return response.json()

    return {}


def ekstraher_profil(data: dict, aktiviteter: list) -> dict:
    ftp = (
        data.get("ftp")
        or data.get("functionalThresholdPower")
        or data.get("critical_power")
        or data.get("cp")
        or data.get("functional_threshold_power")
    )
    cp = data.get("cp") or data.get("criticalPower") or ftp

    if not ftp and aktiviteter:
        ftp = aktiviteter[0].get("ftp") or aktiviteter[0].get("cp")

    return {
        "ftp": ftp,
        "cp": cp,
        "w_prime": data.get("wPrime") or data.get("w_prime"),
        "vdot": data.get("vdot"),
    }


def ekstraher_aktivitet(akt: dict) -> dict:
    dist = akt.get("distance") or 0
    varighet = akt.get("duration") or akt.get("moving_time") or 0

    return {
        "navn": akt.get("name") or akt.get("title") or "–",
        "dato": (akt.get("startTime") or akt.get("start_time") or "")[:10],
        "dist_km": round(dist / 1000, 2) if dist > 100 else round(float(dist or 0), 2),
        "varighet_min": round(varighet / 60, 1) if varighet > 300 else round(float(varighet or 0), 1),
        "snitt_watt": akt.get("averagePower") or akt.get("average_power"),
        "maks_watt": akt.get("maxPower") or akt.get("max_power"),
        "rss": akt.get("rss") or akt.get("runningStressScore"),
        "snitt_puls": akt.get("averageHeartRate") or akt.get("average_heartrate"),
        "ftp": akt.get("ftp") or akt.get("cp"),
    }


def beregn_rss_7d(aktiviteter: list) -> float | None:
    grense = date.today() - timedelta(days=7)
    total = 0
    talt = 0
    for a in aktiviteter:
        dato_str = (a.get("startTime") or a.get("start_time") or "")[:10]
        try:
            if dato_str and date.fromisoformat(dato_str) >= grense:
                total += a.get("rss") or a.get("runningStressScore") or 0
                talt += 1
        except ValueError:
            continue
    return round(total, 1) if talt > 0 else None


def main():
    print("=" * 55)
    print("  STRYD MORGENRAPPORT –", date.today())
    print("=" * 55)

    epost = os.environ.get("STRYD_EMAIL")
    passord = os.environ.get("STRYD_PASSWORD")

    if not epost or not passord:
        raise Exception("STRYD_EMAIL og STRYD_PASSWORD må være satt")

    token, user_id = logg_inn(epost, passord)

    print("\n📡 Henter aktiviteter...")
    aktiviteter_raw = hent_aktiviteter(token, user_id, dager=14)

    print("\n📡 Henter løperprofil...")
    profil_raw = hent_løperprofil(token, user_id)

    print(f"\n🔍 RÅ PROFILDATA:")
    print(json.dumps(profil_raw, indent=2, ensure_ascii=False)[:1000])

    profil = ekstraher_profil(profil_raw, aktiviteter_raw)
    aktiviteter = [ekstraher_aktivitet(a) for a in aktiviteter_raw[:5]]
    rss_7d = beregn_rss_7d(aktiviteter_raw)

    dato = date.today().strftime("%Y-%m-%d")
    output = {
        "dato": dato,
        "profil": {**profil, "rss_7d": rss_7d},
        "siste_aktiviteter": aktiviteter,
    }

    print(f"\n── STRYD NØKKELDATA ──────────────────────────")
    print(f"  FTP        : {profil.get('ftp')} W")
    print(f"  CP         : {profil.get('cp')} W")
    print(f"  W'         : {profil.get('w_prime')} J")
    print(f"  RSS 7 dager: {rss_7d}")
    if aktiviteter:
        s = aktiviteter[0]
        print(f"  Siste økt  : {s['navn']} ({s['dato']})")
        print(f"  Effekt     : {s['snitt_watt']}W snitt / {s['maks_watt']}W maks")

    json_fil = f"stryd_data_{dato}.json"
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Rådata lagret: {json_fil}")
    print("=" * 55)


if __name__ == "__main__":
    main()
