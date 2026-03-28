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

    garmin_status = data.get("_garmin_status", "")
    garmin_mangler = bool(garmin_status)

    hrv   = data.get("hrv", {})
    dag   = data.get("dag", {})
    bb    = data.get("body_battery", {})
    load  = data.get("treningsbelastning", {})
    sovn  = data.get("sovn", {})
    tp    = data.get("trainingpeaks", {})
    tp_d  = tp.get("fitness", {}).get("dagens", {})
    strava = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", []) or data.get("siste_aktiviteter", [])

    # Anbefaling basert på tilgjengelig data
    if garmin_mangler:
        tsb = tp_d.get("tsb")
        if tsb is not None:
            if tsb >= 8:
                anbefaling = "🟢 Tren som planlagt"
            elif tsb >= -10:
                anbefaling = "🟡 Modifiser økten"
            else:
                anbefaling = "🔴 Prioriter hvile"
        else:
            anbefaling = "⚪ Utilstrekkelig data"
    else:
        poeng = 0
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
        ratio = poeng / 10
        if ratio >= 0.75:
            anbefaling = "🟢 Tren som planlagt"
        elif ratio >= 0.45:
            anbefaling = "🟡 Modifiser økten"
        else:
            anbefaling = "🔴 Prioriter hvile"

    sovn_t   = sovn.get("total_min", 0) // 60
    sovn_min = sovn.get("total_min", 0) % 60

    # Siste aktivitet fra Strava
    siste_okt = ""
    if aktiviteter:
        s = aktiviteter[0]
        siste_okt = f"""
Siste økt ({s.get('dato','–')}):
  {s.get('navn','–')} | {s.get('type','–')}
  Dist     : {s.get('dist_km','–')} km | {s.get('varighet_min','–')} min
  Tempo    : {s.get('snitt_tempo','–')}
  Puls     : {s.get('snitt_puls','–')} bpm (maks: {s.get('maks_puls','–')})
  Watt     : {s.get('snitt_watt','–')}W snitt / {s.get('normalisert_watt','–')}W NP
  Suffer   : {s.get('suffer_score','–')}"""

    garmin_varsling = ""
    if garmin_mangler:
        garmin_varsling = f"""
⚠️  GARMIN DATA MANGLER
{garmin_status}
HRV, søvn, Body Battery og treningsbelastning er ikke tilgjengelig.
Rapport basert på Strava og TrainingPeaks.
{'─' * 40}
"""

    brodtekst = f"""{anbefaling}

Morgendata – {dato}
{'─' * 40}{garmin_varsling}
GARMIN-DATA:
  HRV       : {'–' if garmin_mangler else f"{hrv.get('nattlig_snitt','–')} ms (uke: {hrv.get('ukentlig_snitt','–')}) [{hrv.get('status','–')}]"}
  Hvilepuls : {'–' if garmin_mangler else f"{dag.get('hvilepuls','–')} bpm"}
  BB        : {'–' if garmin_mangler else f"{bb.get('maks','–')}/100 (+{bb.get('ladet','–')})"}
  Søvn      : {'–' if garmin_mangler else f"{sovn_t}t {sovn_min}min | Score: {sovn.get('score','–')}"}
  ACWR      : {'–' if garmin_mangler else f"{load.get('acwr','–')} [{load.get('acwr_status','–')}]"}
  Status    : {'–' if garmin_mangler else load.get('status','–')}
{'─' * 40}
TRAININGPEAKS:
  CTL       : {tp_d.get('ctl','–')}
  ATL       : {tp_d.get('atl','–')}
  TSB       : {tp_d.get('tsb','–')}
{'─' * 40}
STRAVA / STRYD:{siste_okt}
{'─' * 40}

=== JSON DATA ===
{json_tekst}
"""

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = gmail_user
    msg["Subject"] = f"{anbefaling} | Garmin {dato}{'  ⚠️ Garmin utilgjengelig' if garmin_mangler else ''}"

    msg.attach(MIMEText(brodtekst, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)

    print(f"E-post sendt til {gmail_user}")


if __name__ == "__main__":
    dato     = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"
    send_epost(json_fil, dato)
