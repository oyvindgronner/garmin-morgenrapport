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

    tp       = data.get("trainingpeaks", {})
    tp_d     = tp.get("fitness", {}).get("dagens", {})
    helse    = tp.get("helsedata", {})
    strava   = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", []) or data.get("siste_aktiviteter", [])

    # Hent nøkkelverdier
    hrv       = helse.get("hrv_nattlig_snitt")
    hvilepuls = helse.get("hvilepuls")
    bb_maks   = helse.get("bb_maks")
    bb_min    = helse.get("bb_min")
    sovn_min  = helse.get("sovn_min", 0)
    dyp_min   = helse.get("dyp_sovn_min", 0)
    rem_min   = helse.get("rem_sovn_min", 0)
    stress    = helse.get("stress_snitt")
    ctl       = tp_d.get("ctl")
    atl       = tp_d.get("atl")
    tsb       = tp_d.get("tsb")

    sovn_t   = sovn_min // 60
    sovn_r   = sovn_min % 60

    # HRV-status
    if hrv is not None:
        if hrv >= 70:
            hrv_status = "BALANSERT"
        elif hrv >= 60:
            hrv_status = "LAV"
        else:
            hrv_status = "SVÆRT LAV"
    else:
        hrv_status = "–"

    # Anbefaling basert på HRV + TSB + BB
    poeng = 0
    maks  = 9
    if hrv is not None:
        if hrv >= 70:
            poeng += 3
        elif hrv >= 60:
            poeng += 1
    if bb_maks is not None:
        if bb_maks >= 75:
            poeng += 3
        elif bb_maks >= 50:
            poeng += 2
        else:
            poeng += 1
    if tsb is not None:
        if tsb >= 5:
            poeng += 3
        elif tsb >= -10:
            poeng += 2
        else:
            poeng += 1

    ratio = poeng / maks
    if ratio >= 0.75:
        anbefaling = "🟢 Tren som planlagt"
    elif ratio >= 0.45:
        anbefaling = "🟡 Modifiser økten"
    else:
        anbefaling = "🔴 Prioriter hvile"

    # Siste aktivitet
    siste_okt = ""
    if aktiviteter:
        s = aktiviteter[0]
        siste_okt = f"""
Siste økt ({s.get('dato','–')}):
  {s.get('navn','–')} | {s.get('type','–')}
  Dist    : {s.get('dist_km','–')} km | {s.get('varighet_min','–')} min
  Tempo   : {s.get('snitt_tempo','–')}
  Puls    : {s.get('snitt_puls','–')} bpm (maks: {s.get('maks_puls','–')})
  Watt    : {s.get('snitt_watt','–')}W snitt / {s.get('normalisert_watt','–')}W NP
  Suffer  : {s.get('suffer_score','–')}"""

    brodtekst = f"""{anbefaling}

Morgendata – {dato}
{'─' * 40}
HELSE (via TrainingPeaks/Garmin):
  HRV       : {hrv if hrv else '–'} ms [{hrv_status}]
  Hvilepuls : {hvilepuls if hvilepuls else '–'} bpm
  Body Batt : {bb_maks if bb_maks else '–'}/100 (min: {bb_min if bb_min else '–'})
  Søvn      : {sovn_t}t {sovn_r}min (dyp: {dyp_min}min | REM: {rem_min}min)
  Stress    : {stress if stress else '–'}
{'─' * 40}
FORM (TrainingPeaks):
  CTL       : {ctl if ctl else '–'}
  ATL       : {atl if atl else '–'}
  TSB       : {tsb if tsb else '–'}
{'─' * 40}
AKTIVITET (Strava):{siste_okt}
{'─' * 40}
"""

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = gmail_user
    msg["Subject"] = f"{anbefaling} | Morgen {dato}"

    msg.attach(MIMEText(brodtekst, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)

    print(f"E-post sendt til {gmail_user}")


if __name__ == "__main__":
    dato     = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"
    send_epost(json_fil, dato)
