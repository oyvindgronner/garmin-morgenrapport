import requests
import json
import os
from datetime import date, timedelta

STRYD_AUTH_URL = "https://www.stryd.com/b/email/signin"
STRYD_API_BASE = "https://www.stryd.com/b/api/v1"


def logg_inn(epost: str, passord: str) -> str:
    response = requests.post(
        STRYD_AUTH_URL,
        json={"email": epost, "password": passord},
        timeout=30
    )
    if response.status_code != 200:
        raise Exception(f"Innlogging feilet: {response.status_code} — {response.text}")

    data = response.json()
    token = data.get("token") or data.get("sessionToken") or data.get("access_token")
    if not token:
        raise Exception(f"Fant ikke token i respons: {data.keys()}")

    print(f"✅ Innlogget på Stryd")
    return token


def hent_løperprofil(token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"{STRYD_API_BASE}/users/profile",
        headers=headers,
        timeout=30
    )
    if response.status_code != 200:
        print(f"⚠️ Kunne ikke hente løperprofil: {response.status_code}")
        return {}

    data = response.json()
    return data


def hent_aktiviteter(token: str, dager: int = 14) -> list:
    headers = {"Authorization": f"Bearer {token}"}
    til_dato = date.today()
    fra_dato = til_dato - timedelta(days=dager)

    params = {
        "sAfter": fra_dato.strftime("%Y-%m-%d"),
        "sBefore": til_dato.strftime("%Y-%m-%d"),
        "sortBy": "startTime",
        "sortOrder": "desc"
    }

    response = requests.get(
        f"{STRYD_API_BASE}/activities/calendar",
        headers=headers,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        print(f"⚠️ Kunne ikke hente aktiviteter: {response.status_code}")
        return []

    data = response.json()
    aktiviteter = data if isinstance(data, list) else data.get("activities", [])
    print(f"✅ Hentet {len(aktiviteter)} aktiviteter fra Stryd")
    return aktiviteter


def hent_rss(token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    til_dato = date.today()
    fra_dato = til_dato - timedelta(days=7)

    params = {
        "sAfter": fra_dato.strftime("%Y-%m-%d"),
        "sBefore": til_dato.strftime("%Y-%m-%d"),
    }

    response = requests.get(
        f"{STRYD_API_BASE}/stress",
        headers=headers,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        print(f"⚠️ Kunne ikke hente RSS: {response.status_code}")
        return {}

    return response.json()


def ekstraher_profil(profil_data: dict) -> dict:
    """Trekk ut nøkkelverdier fra løperprofilen."""
    return {
        "ftp": profil_data.get("ftp") or profil_data.get("functionalThresholdPower"),
        "cp": profil_data.get("cp") or profil_data.get("criticalPower"),
        "w_prime": profil_data.get("wPrime") or profil_data.get("w_prime"),
        "vdot": profil_data.get("vdot"),
        "rss_7d": profil_data.get("rss") or profil_data.get("runningStressScore"),
    }


def ekstraher_aktivitet(akt: dict) -> dict:
    """Trekk ut nøkkelverdier fra én aktivitet."""
    dist = akt.get("distance") or 0
    varighet = akt.get("duration") or akt.get("moving_time") or 0

    return {
        "navn": akt.get("name") or akt.get("title") or "–",
        "dato": akt.get("startTime", "")[:10] if akt.get("startTime") else "–",
        "type": akt.get("type") or akt.get("sport") or "–",
        "dist_km": round(dist / 1000, 2) if dist > 100 else round(dist, 2),
        "varighet_min": round(varighet / 60, 1) if varighet > 300 else round(varighet, 1),
        "snitt_watt": akt.get("averagePower") or akt.get("average_power"),
        "maks_watt": akt.get("maxPower") or akt.get("max_power"),
        "rss": akt.get("rss") or akt.get("runningStressScore"),
        "snitt_puls": akt.get("averageHeartRate") or akt.get("average_heartrate"),
        "treningseffekt": akt.get("trainingEffect") or akt.get("workout_type"),
    }


def main():
    print("=" * 55)
    print("  STRYD MORGENRAPPORT –", date.today())
    print("=" * 55)

    epost = os.environ.get("STRYD_EMAIL")
    passord = os.environ.get("STRYD_PASSWORD")

    if not epost or not passord:
        raise Exception("STRYD_EMAIL og STRYD_PASSWORD må være satt som miljøvariabler")

    token = logg_inn(epost, passord)

    print("\n📡 Henter data fra Stryd...")

    profil_raw = hent_løperprofil(token)
    aktiviteter_raw = hent_aktiviteter(token, dager=14)
    rss_raw = hent_rss(token)

    profil = ekstraher_profil(profil_raw)

    # Hent RSS fra profil eller stress-endepunkt
    if not profil.get("rss_7d") and rss_raw:
        rss_verdi = (
            rss_raw.get("totalRSS")
            or rss_raw.get("rss")
            or rss_raw.get("weeklyRSS")
        )
        profil["rss_7d"] = rss_verdi

    aktiviteter = [ekstraher_aktivitet(a) for a in aktiviteter_raw[:5]]

    dato = date.today().strftime("%Y-%m-%d")
    output = {
        "dato": dato,
        "profil": profil,
        "siste_aktiviteter": aktiviteter,
    }

    # Skriv ut sammendrag
    print(f"\n── STRYD NØKKELDATA ──────────────────────────")
    print(f"  FTP          : {profil.get('ftp')} W")
    print(f"  CP           : {profil.get('cp')} W")
    print(f"  W'           : {profil.get('w_prime')} J")
    print(f"  RSS 7 dager  : {profil.get('rss_7d')}")
    if aktiviteter:
        s = aktiviteter[0]
        print(f"  Siste økt    : {s['navn']} ({s['dato']})")
        print(f"  Effekt       : {s['snitt_watt']}W snitt / {s['maks_watt']}W maks")
        print(f"  RSS økt      : {s['rss']}")

    # Lagre JSON
    json_fil = f"stryd_data_{dato}.json"
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Rådata lagret: {json_fil}")
    print("=" * 55)

    return output


if __name__ == "__main__":
    main()
