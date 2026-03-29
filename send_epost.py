import smtplib
import os
import json
import re
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_epost(json_fil: str, dato: str):
    gmail_user     = os.environ["GMAIL_USER"]
    gmail_password = os.environ["GMAIL_APP_PASSWORD"]

    with open(json_fil, "r", encoding="utf-8") as f:
        data = json.load(f)

    tp          = data.get("trainingpeaks", {})
    tp_d        = tp.get("fitness", {}).get("dagens", {})
    trend_7d    = tp.get("fitness", {}).get("trend_7d", [])
    helse       = tp.get("helsedata", {})
    helse_90d   = tp.get("helsedata_90d", [])
    strava      = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", []) or data.get("siste_aktiviteter", [])
    analyse     = data.get("claude_analyse", "")

    hrv       = helse.get("hrv")
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

    sovn_t = sovn_min // 60
    sovn_r = sovn_min % 60

    if hrv is not None:
        hrv_status = "BALANSERT" if hrv >= 70 else "LAV" if hrv >= 60 else "SVÆRT LAV"
    else:
        hrv_status = "–"

    # HRV-trend siste 7 dager
    hrv_trend = [(d["dato"][5:], d["hrv"]) for d in helse_90d[-7:] if d.get("hrv")]
    hrv_linje = " → ".join([f"{d}: {v}" for d, v in hrv_trend])

    # TSB-trend
    tsb_linje = " → ".join([str(d["tsb"]) for d in trend_7d])

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

    claude_seksjon = ""
    if analyse:
        claude_seksjon = f"""
{'─' * 40}
COACHING-ANALYSE:
{analyse}"""

    brodtekst = f"""Morgendata – {dato}
{'─' * 40}
HELSE (via TrainingPeaks/Garmin):
  HRV       : {hrv or '–'} ms [{hrv_status}]
  HRV-trend : {hrv_linje}
  Hvilepuls : {hvilepuls or '–'} bpm
  Body Batt : {bb_maks or '–'}/100 (min: {bb_min or '–'})
  Søvn      : {sovn_t}t {sovn_r}min (dyp: {dyp_min}min | REM: {rem_min}min)
  Stress    : {stress or '–'}
{'─' * 40}
FORM (TrainingPeaks):
  CTL       : {ctl or '–'}
  ATL       : {atl or '–'}
  TSB       : {tsb or '–'}
  TSB-trend : {tsb_linje}
{'─' * 40}
AKTIVITET (Strava):{siste_okt}{claude_seksjon}
{'─' * 40}
"""

    # Emnelinje: hent første linje fra Claude-analysen hvis mulig
    if analyse:
        forste_linje = analyse.strip().split("\n")[0][:80]
        emne = f"Morgen {dato} | {forste_linje}"
    else:
        emne = f"Morgen {dato}"

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = gmail_user
    msg["Subject"] = emne
    msg.attach(MIMEText(brodtekst, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)

    print(f"E-post sendt til {gmail_user}")


if __name__ == "__main__":
    dato     = date.today().strftime("%Y-%m-%d")
    json_fil = f"garmin_data_{dato}.json"
    send_epost(json_fil, dato)
