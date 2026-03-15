import smtplib
import os
import json
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_epost(json_fil: str, dato: str):
    gmail_user     = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]

    with open(json_fil, "r", encoding="utf-8") as f:
        data = json.load(f)
        json_tekst = json.dumps(data, indent=2, ensure_ascii=False)

    hrv  = data.get("hrv", {})
    dag  = data.get("dag", {})
    bb   = data.get("body_battery", {})
    load = data.get("treningsbelastning", {})
    sovn = data.get("sovn", {})

    # Trafikklys
    poeng = 0
    maks  = 10
    if hrv.get("status") == "BALANCED":
        poeng += 3
    elif hrv.get("status") == "LOW":
        poeng += 1
    bb_maks = bb.get("maks")
    if bb_maks and bb_maks >= 75:
        poeng += 2
    elif bb_maks and bb_maks >= 50:
        poeng += 1
    acwr = load.get("acwr") or 0
    if 0.8 <= acwr <= 1.3:
        poeng += 3
    elif acwr < 0.8:
        poeng += 2
    elif acwr <= 1.5:
        poeng += 1
    status = load.get("status", "")
    if status in ("PRODUCTIVE", "PEAKING", "MAINTAINING"):
        poeng += 2
    elif status in ("RECOVERY", "DETRAINING", "UNPRODUCTIVE"):
        poeng += 1

    ratio = poeng / maks
    if ratio >= 0.75:
        anbefaling = "🟢 Tren som planlagt"
    elif ratio >= 0.45:
        anbefaling = "🟡 Modifiser økten"
    else:
        anbefaling = "🔴 Prioriter hvile"

    sovn_t   = sovn.get("total_min", 0) // 60
    sovn_min = sovn.get("total_min", 0) % 60

    brodtekst = f"""{anbefaling}

Garmin morgendata – {dato}
{'─' * 30}
HRV       : {hrv.get('nattlig_snitt','–')} ms (uke: {hrv.get('ukentlig_snitt','–')}) [{hrv.get('status','–')}]
Hvilepuls : {dag.get('hvilepuls','–')} bpm | Stress: {dag.get('stress_snitt','–')}
BB        : {bb.get('maks','–')}/100 (+{bb.get('ladet','–')})
Søvn      : {sovn_t}t {sovn_min}min | Score: {sovn.get('score','–')}
            Dyp: {sovn.get('dyp_min','–')}min | REM: {sovn.get('rem_min','–')}min
ACWR      : {load.get('acwr','–')} [{load.get('acwr_status','–')}]
Status    : {load.get('status','–')}
VO2max    : {load.get('vo2max','–')}
{'─' * 30}

=== GARMIN JSON DATA ===
{json_tekst}
"""

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = gmail_user
    msg["Subject"] = f"{anbefaling} | Garmin {dato}"

    msg.attach(MIMEText(brodtekst, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)

    print(f"✅ E-post sendt til {gmail_user}")


if __name__ == "__main__":
    dato     = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"
    send_epost(json_fil, dato)
