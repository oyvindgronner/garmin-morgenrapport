import requests
import os
import json
import urllib.parse
from datetime import date


def trafikklys(hrv: dict, bb: dict, load: dict) -> str:
    """
    Beregner treningsanbefaling basert på tre nøkkelsignaler.
    Returnerer emoji + tekst.
    """
    poeng = 0
    maks  = 0

    # HRV — vekt 3
    hrv_status = hrv.get("status", "")
    maks += 3
    if hrv_status == "BALANCED":
        poeng += 3
    elif hrv_status == "LOW":
        poeng += 1

    # Body Battery — vekt 2
    bb_maks = bb.get("maks")
    maks += 2
    if bb_maks is not None:
        if bb_maks >= 75:
            poeng += 2
        elif bb_maks >= 50:
            poeng += 1

    # ACWR — vekt 3
    acwr        = load.get("acwr") or 0
    acwr_status = load.get("acwr_status", "")
    maks += 3
    if acwr_status == "OPTIMAL" or (0.8 <= acwr <= 1.3):
        poeng += 3
    elif acwr_status == "LOW" or acwr < 0.8:
        poeng += 2
    elif acwr <= 1.5:
        poeng += 1

    # Treningsstatus — vekt 2
    status = load.get("status", "")
    maks += 2
    if status in ("PRODUCTIVE", "PEAKING", "MAINTAINING"):
        poeng += 2
    elif status in ("RECOVERY", "DETRAINING", "UNPRODUCTIVE"):
        poeng += 1
    # OVERREACHING gir 0

    ratio = poeng / maks if maks > 0 else 0

    if ratio >= 0.75:
        return "🟢 Tren som planlagt"
    elif ratio >= 0.45:
        return "🟡 Modifiser økten"
    else:
        return "🔴 Prioriter hvile"


def formater_melding(data: dict, dato: str) -> str:
    hrv  = data.get("hrv", {})
    sovn = data.get("sovn", {})
    dag  = data.get("dag", {})
    bb   = data.get("body_battery", {})
    load = data.get("treningsbelastning", {})
    akt  = data.get("siste_aktiviteter", [])

    anbefaling = trafikklys(hrv, bb, load)

    sovn_t   = sovn.get("total_min", 0) // 60
    sovn_min = sovn.get("total_min", 0) % 60

    siste = akt[0] if akt else {}
    siste_linje = (
        f"{siste.get('navn','–')} {siste.get('dist_km','–')}km | "
        f"{siste.get('snitt_tempo','–')} | {siste.get('snitt_puls','–')}bpm"
        if siste else "–"
    )

    melding = f"""{anbefaling}
🏃 Garmin {dato}
{'─' * 26}
❤️ HRV: {hrv.get('nattlig_snitt','–')} ms (uke: {hrv.get('ukentlig_snitt','–')}) [{hrv.get('status','–')}]
💓 Hvilepuls: {dag.get('hvilepuls','–')} bpm | Stress: {dag.get('stress_snitt','–')}
⚡ Body Battery: {bb.get('maks','–')}/100 (+{bb.get('ladet','–')})
😴 Søvn: {sovn_t}t {sovn_min}min | Score: {sovn.get('score','–')}
   Dyp: {sovn.get('dyp_min','–')}min | REM: {sovn.get('rem_min','–')}min
📊 ACWR: {load.get('acwr','–')} [{load.get('acwr_status','–')}]
   Status: {load.get('status','–')}
   VO2max: {load.get('vo2max','–')}
🏅 Siste: {siste_linje}
{'─' * 26}
→ Lim prompt i Claude for analyse"""

    return melding


def send_signal(tekst: str):
    signal_id = os.environ["SIGNAL_ID"]
    api_key   = os.environ["SIGNAL_API_KEY"]

    melding = urllib.parse.quote(tekst)
    url = (
        f"https://signal.callmebot.com/signal/send.php"
        f"?phone={signal_id}&apikey={api_key}&text={melding}"
    )

    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        print("✅ Signal-melding sendt")
    else:
        print(f"❌ Feil: {response.status_code} — {response.text}")
        raise SystemExit(1)


if __name__ == "__main__":
    dato     = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"

    with open(json_fil, "r", encoding="utf-8") as f:
        data = json.load(f)

    melding = formater_melding(data, dato)
    print(melding)
    send_signal(melding)
