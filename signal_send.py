import requests
import os
import json
import urllib.parse
from datetime import date


def formater_melding(data: dict, dato: str) -> str:
    hrv = data.get("hrv", {})
    sovn = data.get("sovn", {})
    status = data.get("dagsstatus", {})
    bb = data.get("body_battery", {})
    belastning = data.get("treningsbelastning", {})

    hrv_snitt = hrv.get("lastNightAvg", "–")
    hrv_status = hrv.get("status", "–")
    hrv_ukesnitt = hrv.get("weeklyAvg", "–")

    sovn_timer = round(sovn.get("totalSleepSeconds", 0) / 3600, 1)
    sovn_score = sovn.get("sleepScore", "–")
    dyp_min = round(sovn.get("deepSleepSeconds", 0) / 60)
    rem_min = round(sovn.get("remSleepSeconds", 0) / 60)

    hvile_puls = status.get("restingHeartRate", "–")
    stress = status.get("averageStressLevel", "–")

    bb_morgen = bb.get("max", "–")
    bb_ladet = bb.get("charged", "–")

    vo2max = belastning.get("vo2max", "–")
    acwr = belastning.get("acwr", "–")
    acwr_status = belastning.get("acwrStatus", "–")
    trening_status = belastning.get("trainingStatus", "–")

    melding = f"""🏃 Garmin morgenrapport {dato}
{'─' * 28}
❤️ HRV
  Natt: {hrv_snitt} ms | Uke: {hrv_ukesnitt} ms
  Status: {hrv_status}

😴 Søvn
  {sovn_timer}t | Score: {sovn_score}/100
  Dyp: {dyp_min}min | REM: {rem_min}min

⚡ Body Battery
  Morgen: {bb_morgen}/100 | Ladet: {bb_ladet}

💓 Hvilepuls
  {hvile_puls} bpm | Stress: {stress}

📊 Treningsbelastning
  VO2max: {vo2max}
  ACWR: {acwr} [{acwr_status}]
  Status: {trening_status}
{'─' * 28}
Lim inn prompt i Claude for analyse."""

    return melding


def send_signal(tekst: str):
    telefon = os.environ["SIGNAL_PHONE"]
    api_key = os.environ["SIGNAL_API_KEY"]

    melding = urllib.parse.quote(tekst)
    url = (
        f"https://api.callmebot.com/signal/send.php"
        f"?phone={telefon}&apikey={api_key}&text={melding}"
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
