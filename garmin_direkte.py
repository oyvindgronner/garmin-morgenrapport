#!/usr/bin/env python3
"""
garmin_direkte.py
=================
Henter søvnscore og HRV direkte fra Garmin Connect via garth.
Bruker lagrede OAuth2-tokens (ingen ny innlogging per kjøring = ingen rate limiting).

Auth-oppsett (én gang lokalt):
    python garmin_auth.py        → genererer GARMIN_TOKENS
    gh secret set GARMIN_TOKENS  → legg inn i GitHub

Deretter kjøres dette scriptet automatisk i workflow etter morgen.py.
"""

import json
import os
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)


def main():
    tokens = os.environ.get("GARMIN_TOKENS", "")
    if not tokens:
        print("GARMIN_TOKENS ikke satt — hopper over Garmin direkte")
        return

    try:
        import garth
    except ImportError:
        print("garth ikke installert — hopper over Garmin direkte")
        return

    # Last inn lagrede OAuth2-tokens (ingen ny login)
    try:
        garth.client.loads(tokens)
        print("Garmin: tokens lastet OK")
    except Exception as e:
        print(f"Garmin: kunne ikke laste tokens: {e}")
        return

    dato = date.today().isoformat()
    json_fil = f"garmin_data_{dato}.json"

    if not Path(json_fil).exists():
        print(f"Garmin: finner ikke {json_fil} — hopper over")
        return

    with open(json_fil, encoding="utf-8") as f:
        garmin_data = json.load(f)

    garmin_direkte = {}

    # ── Søvndata ────────────────────────────────────────────
    try:
        from garth.data.sleep import SleepData
        sleep = SleepData.get(dato)
        if sleep and sleep.daily_sleep_dto:
            dto = sleep.daily_sleep_dto
            scores = dto.sleep_scores

            garmin_direkte["sovn"] = {
                "score":          scores.overall.value if scores else None,
                "score_feedback": dto.sleep_score_feedback,
                "score_insight":  dto.sleep_score_insight,
                "dyp_sek":        dto.deep_sleep_seconds,
                "lett_sek":       dto.light_sleep_seconds,
                "rem_sek":        dto.rem_sleep_seconds,
                "vaaken_sek":     dto.awake_sleep_seconds,
                "respirasjonsfrekvens": dto.average_respiration_value,
                "spo2_snitt":     dto.average_sp_o2_value,
            }
            score = scores.overall.value if scores else "–"
            print(f"  Søvnscore: {score}/100 | Feedback: {dto.sleep_score_feedback}")
        else:
            print(f"  Søvndata ikke tilgjengelig for {dato}")
    except Exception as e:
        print(f"  FEIL søvn: {e}")

    # ── HRV ─────────────────────────────────────────────────
    try:
        from garth.data.hrv import HRVData
        hrv = HRVData.get(dato)
        if hrv and hrv.hrv_summary:
            s = hrv.hrv_summary
            garmin_direkte["hrv"] = {
                "siste_natt_snitt": s.last_night_avg,
                "ukentlig_snitt":   s.weekly_avg,
                "5min_topp":        s.last_night_5_min_high,
                "status":           s.status,          # BALANCED / UNBALANCED / LOW / etc.
                "feedback":         s.feedback_phrase,
                "baseline_lav":     s.baseline.low_upper if s.baseline else None,
                "baseline_balansert_lav":  s.baseline.balanced_low if s.baseline else None,
                "baseline_balansert_høy":  s.baseline.balanced_upper if s.baseline else None,
            }
            print(f"  HRV natt: {s.last_night_avg} ms | Status: {s.status}")
        else:
            print(f"  HRV ikke tilgjengelig for {dato}")
    except Exception as e:
        print(f"  FEIL HRV: {e}")

    # ── Merge inn i garmin_data JSON ─────────────────────────
    if garmin_direkte:
        garmin_data["garmin_direkte"] = garmin_direkte

        # Oppdater helsedata med Garmin-score direkte (brukes av dashboard og analyse)
        tp = garmin_data.get("trainingpeaks", {})
        helse = tp.get("helsedata", {})

        if "sovn" in garmin_direkte:
            sovn = garmin_direkte["sovn"]
            if sovn.get("score") is not None:
                helse["sovn_score"] = sovn["score"]
            if sovn.get("respirasjonsfrekvens") is not None:
                helse["respirasjonsfrekvens"] = round(sovn["respirasjonsfrekvens"], 1)
            if sovn.get("spo2_snitt") is not None:
                helse["spo2_snitt"] = round(sovn["spo2_snitt"], 1)

        if "hrv" in garmin_direkte:
            h = garmin_direkte["hrv"]
            if h.get("siste_natt_snitt") is not None:
                helse["hrv_natt"] = h["siste_natt_snitt"]  # mer presist enn morgenmåling
            if h.get("status"):
                helse["hrv_status"] = h["status"]
            if h.get("feedback"):
                helse["hrv_feedback"] = h["feedback"]
            if h.get("baseline_balansert_lav") and h.get("baseline_balansert_høy"):
                helse["hrv_baseline"] = (
                    f"{h['baseline_balansert_lav']}–{h['baseline_balansert_høy']} ms"
                )

        tp["helsedata"] = helse
        garmin_data["trainingpeaks"] = tp

        with open(json_fil, "w", encoding="utf-8") as f:
            json.dump(garmin_data, f, ensure_ascii=False, indent=2)
        print(f"  Merget Garmin-data inn i {json_fil}")
    else:
        print("  Ingen nye Garmin-data å merge")


if __name__ == "__main__":
    main()
