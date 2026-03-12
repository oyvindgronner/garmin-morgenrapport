import requests
import os
import json
import urllib.parse
from datetime import date


def formater_melding(data: dict, dato: str) -> str:
    hrv = data.get("hrv", {})
    sovn = data.get("sovn", {})
    dag = data.get("dag", {})
    bb = data.get("body_battery", {})
    belastning = data.get("treningsbelastning", {})
    aktiviteter = data.get("siste_aktiviteter", [])

    # HRV
    hrv_snitt = hrv.get("nattlig_snitt", "–")
    hrv_uke = hrv.get("ukentlig_snitt", "–")
    hrv_status = hrv.get("status", "–")

    # Søvn
    sovn_timer = round(sovn.get("total_min", 0) / 60, 1)
    sovn_score = sovn.get("score", "–")
    dyp_min = sovn.get("dyp_min", "–")
    rem_min = sovn.get("rem_min", "–")

    # Puls og stress
    hvile_puls = dag.get("hvilepuls", "–")
    stress = dag.get("stress_snitt", "–")

    # Body Battery
    bb_morgen = bb.get("maks", "–")
    bb_ladet = bb.get("ladet", "–")

    # Treningsbelastning
    vo2 = belastning.get("vo2max", "–")
    acwr = belastning.get("acwr", "–")
    acwr_status = belastning.get("acwr_status", "–")
    tr_status = belastning.get("status", "–")

    # Siste økt
    siste = aktiviteter[0] if aktiviteter else {}
    siste_navn = siste.get("navn", "–")
    siste_km = siste.get("dist_km", "–")
    siste_puls = siste.get("snitt_puls", "–")
    siste_load = siste.get("load", "–")

    melding = f"""🏃 Garmin {dato}
{'─' * 26}
❤️ HRV: {hrv_snitt} ms (uke: {hrv_uke}) [{hrv_status}]
💓 Hvilepuls: {hvile_puls} bpm | Stress: {stress}
⚡ Body Battery: {bb_morgen}/100 (+{bb_ladet})
😴 Søvn: {sovn_timer}t | Score: {sovn_score}
   Dyp: {dyp_min}min | REM: {rem_min}min
📊 ACWR: {acwr} [{acwr_status}]
   Status: {tr_status}
   VO2max: {vo2}
🏅 Siste: {siste_navn} {siste_km}km | {siste_puls}bpm | load {siste_load}
{'─' * 26}
→ Lim prompt i Claude for analyse"""

    return melding


def send_signal(tekst: str):
    signal_id = os.environ["SIGNAL_ID"]
    api_key = os.environ["SIGNAL_API_KEY"]

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
    dato = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"

    with open(json_fil, "r", encoding="utf-8") as f:
        data = json.load(f)

    melding = formater_melding(data, dato)
    print(melding)
    send_signal(melding)
