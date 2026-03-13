import requests
import json
import os
from datetime import date, timedelta, datetime

STRYD_AUTH_URL = "https://www.stryd.com/b/email/signin"
STRYD_API_BASE = "https://www.stryd.com/b/api/v1"


def logg_inn(epost: str, passord: str) -> tuple[str, str]:
    response = requests.post(
        STRYD_AUTH_URL,
        json={"email": epost, "password": passord},
        timeout=30
    )
    if response.status_code != 200:
        raise Exception(f"Innlogging feilet: {response.status_code}")

    data = response.json()
    token = data.get("token")
    user_id = str(data.get("id", ""))
    print(f"✅ Innlogget | user_id: {user_id}")
    return token, user_id


def hent_aktiviteter(token: str, dager: int = 14) -> list:
    headers = {"Authorization": f"Bearer: {token}"}
    til_dato = date.today() + timedelta(days=1)
    fra_dato = til_dato - timedelta(days=dager)

    # Parametere kun i URL — ikke som params-dict (unngår 430)
    url = (
        f"{STRYD_API_BASE}/activities/calendar"
        f"?srtDate={fra_dato.strftime('%m-%d-%Y')}"
        f"&endDate={til_dato.strftime('%m-%d-%Y')}"
        f"&sortBy=StartDate"
    )

    print(f"  Henter: {url}")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"  Status: {response.status_code}")

    if response.status_code != 200:
        print(f"  Feilmelding: {response.text[:200]}")
        return []

    data = response.json()
    print(f"  Respons-nøkler: {list(data.keys()) if isinstance(data, dict) else 'liste'}")

    aktiviteter = data.get("activities", []) if isinstance(data, dict) else data
    print(f"✅ Hentet {len(aktiviteter)} aktiviteter")
    return aktiviteter


def ekstraher_aktivitet(akt: dict) -> dict:
    # FTP og RSS ligger direkte per aktivitet
    dist = akt.get("distance") or 0
    varighet = akt.get("duration") or 0
    tidspunkt = akt.get("timestamp")

    if tidspunkt:
        try:
            dato = datetime.fromtimestamp(tidspunkt).strftime("%Y-%m-%d")
        except Exception:
            dato = "–"
    else:
        dato = (akt.get("startTime") or "")[:10] or "–"

    return {
        "navn": akt.get("name") or akt.get("title") or "–",
        "dato": dato,
        "dist_km": round(float(dist or 0), 2),
        "varighet_min": round(float(varighet or 0) / 60, 1) if varighet > 300 else round(float(varighet or 0), 1),
        "snitt_watt": akt.get("averagePower") or akt.get("average_power"),
        "maks_watt": akt.get("maxPower") or akt.get("max_power"),
        "ftp": akt.get("ftp"),
        "rss": akt.get("stress") or akt.get("rss"),
        "snitt_puls": akt.get("averageHeartRate") or akt.get("average_heartrate"),
    }


def beregn_rss_7d(aktiviteter: list) -> float | None:
    grense = date.today() - timedelta(days=7)
    total = 0
    talt = 0
    for a in aktiviteter:
        dato_str = a.get("dato", "")
        try:
            if dato_str and dato_str != "–" and date.fromisoformat(dato_str) >= grense:
                total += a.get("rss") or 0
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
    aktiviteter_raw = hent_aktiviteter(token, dager=14)

    # Debug: vis første aktivitet rå
    if aktiviteter_raw:
        print(f"\n🔍 FØRSTE AKTIVITET RÅ:")
        print(json.dumps(aktiviteter_raw[0], indent=2, ensure_ascii=False)[:800])

    aktiviteter = [ekstraher_aktivitet(a) for a in aktiviteter_raw[:5]]
    rss_7d = beregn_rss_7d(aktiviteter)

    # FTP fra siste aktivitet
    ftp = next((a.get("ftp") for a in aktiviteter if a.get("ftp")), None)
    cp = ftp

    dato = date.today().strftime("%Y-%m-%d")
    output = {
        "dato": dato,
        "profil": {
            "ftp": ftp,
            "cp": cp,
            "rss_7d": rss_7d,
        },
        "siste_aktiviteter": aktiviteter,
    }

    print(f"\n── STRYD NØKKELDATA ──────────────────────────")
    print(f"  FTP        : {ftp} W")
    print(f"  RSS 7 dager: {rss_7d}")
    if aktiviteter:
        s = aktiviteter[0]
        print(f"  Siste økt  : {s['navn']} ({s['dato']})")
        print(f"  Effekt     : {s['snitt_watt']}W snitt / {s['maks_watt']}W maks")
        print(f"  RSS økt    : {s['rss']}")

    json_fil = f"stryd_data_{dato}.json"
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Rådata lagret: {json_fil}")
    print("=" * 55)


if __name__ == "__main__":
    main()
