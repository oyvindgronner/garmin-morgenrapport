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
        raise Exception(f"Fant ikke token i respons: {list(data.keys())}")

    print(f"✅ Innlogget på Stryd")
    return token


def hent_aktiviteter(token: str, dager: int = 14) -> list:
    headers = {"Authorization": f"Bearer: {token}"}
    til_dato = date.today() + timedelta(days=1)
    fra_dato = til_dato - timedelta(days=dager)

    url = (
        f"{STRYD_API_BASE}/activities/calendar"
        f"?srtDate={fra_dato.strftime('%m-%d-%Y')}"
        f"&endDate={til_dato.strftime('%m-%d-%Y')}"
        f"&sortBy=StartDate"
    )

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"⚠️ Kunne ikke hente aktiviteter: {response.status_code} — {response.text[:200]}")
        return []

    data = response.json()
    aktiviteter = data.get("activities", []) if isinstance(data, dict) else data
    print(f"✅ Hentet {len(aktiviteter)} aktiviteter fra Stryd")
    return aktiviteter


def hent_løperprofil(token: str) -> dict:
    headers = {"Authorization": f"Bearer: {token}"}

    # Prøv flere kjente endepunkter
    endepunkter = [
        "/users/profile",
        "/athlete/profile",
        "/trainingplans/profile",
    ]

    for ep in endepunkter:
        response = requests.get(
            f"{STRYD_API_BASE}{ep}",
            headers=headers,
            timeout=30
        )
        if response.status_code == 200:
            print(f"✅ Hentet løperprofil fra {ep}")
            return response.json()
        else:
            print(f"⚠️ {ep} → {response.status_code}")

    return {}


def ekstraher_profil(data: dict, aktiviteter: list) -> dict:
    """Hent FTP/CP fra profil eller fra siste aktivitet."""
    ftp = (
        data.get("ftp")
        or data.get("functionalThresholdPower")
        or data.get("critical_power")
        or data.get("cp")
    )
    cp = data.get("cp") or data.get("criticalPower") or ftp

    # Fallback: hent fra siste aktivitet
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
        "type": akt.get("type") or akt.get("sport") or "–",
        "dist_km": round(dist / 1000, 2) if dist > 100 else round(float(dist), 2),
        "varighet_min": round(varighet / 60, 1) if varighet > 300 else round(float(varighet), 1),
        "snitt_watt": akt.get("averagePower") or akt.get("average_power"),
        "maks_watt": akt.get("maxPower") or akt.get("max_power"),
        "rss": akt.get("rss") or akt.get("runningStressScore"),
        "snitt_puls": akt.get("averageHeartRate") or akt.get("average_heartrate"),
        "ftp": akt.get("ftp") or akt.get("cp"),
    }


def beregn_rss_7d(aktiviteter: list) -> float | None:
    """Summer RSS fra siste 7 dager."""
    grense = date.today() - timedelta(days=7)
    total = 0
    talt = 0
    for a in aktiviteter:
        dato_str = (a.get("startTime") or a.get("start_time") or "")[:10]
        if not dato_str:
            continue
        try:
            dato = date.fromisoformat(dato_str)
        except ValueError:
            continue
        if dato >= grense:
            rss = a.get("rss") or a.get("runningStressScore") or 0
            total += rss
            talt += 1
    return round(total, 1) if talt > 0 else None


def main():
    print("=" * 55)
    print("  STRYD MORGENRAPPORT –", date.today())
    print("=" * 55)

    epost = os.environ.get("STRYD_EMAIL")
    passord = os.environ.get("STRYD_PASSWORD")

    if not epost or not passord:
        raise Exception("STRYD_EMAIL og STRYD_PASSWORD må være satt")

    token = logg_inn(epost, passord)

    print("\n📡 Henter data fra Stryd...")

    aktiviteter_raw = hent_aktiviteter(token, dager=14)
    profil_raw = hent_løperprofil(token)

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
    print(f"  FTP          : {profil.get('ftp')} W")
    print(f"  CP           : {profil.get('cp')} W")
    print(f"  W'           : {profil.get('w_prime')} J")
    print(f"  RSS 7 dager  : {rss_7d}")
    if aktiviteter:
        s = aktiviteter[0]
        print(f"  Siste økt    : {s['navn']} ({s['dato']})")
        print(f"  Effekt       : {s['snitt_watt']}W snitt / {s['maks_watt']}W maks")
        print(f"  RSS økt      : {s['rss']}")

    # Skriv rådata for debugging
    print(f"\n── RÅ PROFIL-DATA ────────────────────────────")
    print(json.dumps(profil_raw, indent=2, ensure_ascii=False)[:500])

    json_fil = f"stryd_data_{dato}.json"
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Rådata lagret: {json_fil}")
    print("=" * 55)

    return output


if __name__ == "__main__":
    main()
