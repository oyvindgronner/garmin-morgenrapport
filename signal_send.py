import requests
import os
import json
import urllib.parse
from datetime import date


def formater_melding(data: dict, dato: str) -> str:
    hrv = data.get("hrv", {})
    sovn = data.get("sovn", {})
    dagsstatus = data.get("dagsstatus", {})
    bb = data.get("body_battery", {})
    belastning = data.get("treningsbelastning", {})
    aktiviteter = data.get("siste_aktiviteter", [])

    # HRV
    hrv_snitt = hrv.get("lastNightAvg") or hrv.get("hrv_natt") or "–"
    hrv_uke = hrv.get("weeklyAvg") or hrv.get("hrv_uke") or "–"
    hrv_status = hrv.get("status", "–")

    # Søvn
    total_sek = sovn.get("totalSleepSeconds") or sovn.get("total_sekunder") or 0
    dyp_sek = sovn.get("deepSleepSeconds") or sovn.get("dyp_sekunder") or 0
    rem_sek = sovn.get("remSleepSeconds") or sovn.get("rem_sekunder") or 0
    sovn_score = sovn.get("sleepScore") or sovn.get("score") or "–"
    sovn_timer = round(total_sek / 3600, 1) if total_sek else "–"
    dyp_min = round(dyp_sek / 60) if dyp_sek else "–"
    rem_min = round(rem_sek / 60) if rem_sek else "–"

    # Puls og stress
    hvile_puls = dagsstatus.get("restingHeartRate") or dagsstatus.get("hvilepuls") or "–"
    stress = dagsstatus.get("averageStressLevel") or dagsstatus.get("stress") or "–"

    # Body Battery
    bb_morgen = bb.get("max") or bb.get("morgen") or "–"
    bb_ladet = bb.get("charged") or bb.get("ladet") or "–"

    # Treningsbelastning
    vo2 = belastning.get("vo2max") or belastning.get("mostRecentVO2Max") or "–"
    acwr = belastning.get("acwr") or "–"
    acwr_status = belastning.get("acwrStatus") or "–"
    tr_status = belastning.get("trainingStatus") or belastning.get("treningsstatus") or "–"

    # Siste økt
    siste = aktiviteter[0] if aktiviteter else {}
    siste_navn = siste.get("navn") or siste.get("name") or "–"
    siste_km = round(siste.get("distanse") or siste.get("distance", 0) / 1000, 2) if siste else "–"
    siste_puls = siste.get("snitt_puls") or siste.get("averageHR") or "–"

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
🏅 Siste: {siste_navn} {siste_km}km | {siste_puls}bpm
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
