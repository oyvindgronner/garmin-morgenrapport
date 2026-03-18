#!/usr/bin/env python3
"""
garmin_morgen.py
================
Henter helsedata fra Garmin Connect og lagrer som JSON.

Avhengigheter:
    pip install garminconnect garth
"""

import json
import os
import sys
from datetime import date
from getpass import getpass

try:
    from garminconnect import Garmin
except ImportError:
    print("Mangler garminconnect. Installer med: pip install garminconnect garth")
    sys.exit(1)

TOKENSTI = os.environ.get("GARMIN_TOKEN_DIR", os.path.expanduser("~/.garth"))
DATO_STR = date.today().isoformat()


def logg_inn():
    """
    Logger inn med:
    1. Lagret token — gjenbrukes mellom kjøringer, unngår rate limit
    2. Miljøvariabler — fallback ved ugyldig token
    3. Manuell innlogging — lokalt på Mac
    """
    import time

    # Forsøk 1: Gjenbruk lagret token (ingen SSO = ingen rate limit)
    if os.path.exists(TOKENSTI):
        try:
            api = Garmin()
            api.login(TOKENSTI)
            print("Innlogget med lagret token")
            return api
        except Exception as e:
            print(f"Lagret token ugyldig: {e}")

    # Forsøk 2: Miljøvariabler (GitHub Actions)
    epost = os.environ.get("GARMIN_EMAIL")
    passord = os.environ.get("GARMIN_PASSWORD")

    if epost and passord:
        for attempt in range(3):
            try:
                print(f"Logger inn med miljovariabler (forsok {attempt + 1}/3)...")
                api = Garmin(epost, passord)
                api.login()
                api.garth.dump(TOKENSTI)
                print(f"Innlogget og token lagret i {TOKENSTI}")
                return api
            except Exception as e:
                if "429" in str(e) or "Too Many" in str(e):
                    wait = 60 * (2 ** attempt)
                    print(f"Rate limit - venter {wait}s...")
                    time.sleep(wait)
                else:
                    raise
        raise Exception("Kunne ikke logge inn etter 3 forsok (rate limit)")

    # Forsøk 3: Manuell innlogging (Mac)
    epost = input("Garmin e-post: ").strip()
    passord = getpass("Garmin passord: ")
    api = Garmin(epost, passord)
    api.login()
    api.garth.dump(TOKENSTI)
    print("Innlogget og token lagret")
    return api


def hent_hrv(api):
    try:
        data     = api.get_hrv_data(DATO_STR)
        summary  = data.get("hrvSummary", {})
        baseline = summary.get("baseline", {})
        return {
            "nattlig_snitt":          summary.get("lastNightAvg"),
            "ukentlig_snitt":         summary.get("weeklyAvg"),
            "5min_hoy":               summary.get("lastNight5MinHigh"),
            "status":                 summary.get("status"),
            "baseline_balansert_lav": baseline.get("balancedLow"),
            "baseline_balansert_hoy": baseline.get("balancedUpper"),
        }
    except Exception as e:
        print(f"HRV feil: {e}")
        return {}


def hent_sovn(api):
    try:
        data   = api.get_sleep_data(DATO_STR)
        daglig = data.get("dailySleepDTO", {})
        return {
            "total_min":   daglig.get("sleepTimeSeconds", 0) // 60,
            "dyp_min":     daglig.get("deepSleepSeconds", 0) // 60,
            "rem_min":     daglig.get("remSleepSeconds", 0) // 60,
            "lett_min":    daglig.get("lightSleepSeconds", 0) // 60,
            "score":       daglig.get("sleepScores", {}).get("overall", {}).get("value"),
            "respiration": daglig.get("averageRespirationValue"),
            "stress_natt": daglig.get("avgSleepStress"),
        }
    except Exception as e:
        print(f"Sovn feil: {e}")
        return {}


def hent_dagsstatus(api):
    try:
        data = api.get_user_summary(DATO_STR)
        return {
            "hvilepuls":    data.get("restingHeartRate"),
            "stress_snitt": data.get("averageStressLevel"),
            "skritt":       data.get("totalSteps"),
        }
    except Exception as e:
        print(f"Dagsstatus feil: {e}")
        return {}


def hent_body_battery(api):
    try:
        data = api.get_body_battery(DATO_STR)
        if isinstance(data, list) and data:
            dag     = data[0]
            verdier = dag.get("bodyBatteryValuesArray", [])
            if verdier:
                nivaaer = [v[1] for v in verdier if len(v) > 1]
                return {
                    "maks":  max(nivaaer),
                    "min":   min(nivaaer),
                    "ladet": dag.get("charged"),
                }
        return {}
    except Exception as e:
        print(f"Body Battery feil: {e}")
        return {}


def hent_treningsbelastning(api):
    try:
        data = api.get_training_status(DATO_STR)

        vo2max = (data.get("mostRecentVO2Max", {})
                      .get("generic", {})
                      .get("vo2MaxValue"))

        enheter = (data.get("mostRecentTrainingStatus", {})
                       .get("latestTrainingStatusData", {}))
        enhet   = next(iter(enheter.values()), {}) if enheter else {}
        acwr_dto = enhet.get("acuteTrainingLoadDTO", {})

        balance = (data.get("mostRecentTrainingLoadBalance", {})
                       .get("metricsTrainingLoadBalanceDTOMap", {}))
        bal = next(iter(balance.values()), {}) if balance else {}

        return {
            "status":        enhet.get("trainingStatusFeedbackPhrase"),
            "vo2max":        vo2max,
            "acwr":          acwr_dto.get("dailyAcuteChronicWorkloadRatio"),
            "acwr_status":   acwr_dto.get("acwrStatus"),
            "aerob_lav":     round(bal.get("monthlyLoadAerobicLow", 0), 0),
            "aerob_hoy":     round(bal.get("monthlyLoadAerobicHigh", 0), 0),
            "anaerob":       round(bal.get("monthlyLoadAnaerobic", 0), 0),
            "load_feedback": bal.get("trainingBalanceFeedbackPhrase"),
        }
    except Exception as e:
        print(f"Treningsbelastning feil: {e}")
        return {}


def hent_aktiviteter(api, antall=3):
    try:
        alle     = api.get_activities(0, antall)
        resultat = []

        for a in alle:
            if a.get("activityType", {}).get("typeKey") not in (
                "running", "cycling", "swimming", "trail_running"
            ):
                continue

            avg_speed = a.get("averageSpeed")
            if avg_speed and avg_speed > 0:
                sek         = 1000 / avg_speed
                snitt_tempo = f"{int(sek // 60)}:{int(sek % 60):02d} /km"
            else:
                snitt_tempo = None

            resultat.append({
                "navn":           a.get("activityName"),
                "dato":           a.get("startTimeLocal", "")[:10],
                "type":           a.get("activityType", {}).get("typeKey"),
                "dist_km":        round(a.get("distance", 0) / 1000, 2),
                "varighet_min":   round(a.get("duration", 0) / 60, 1),
                "snitt_tempo":    snitt_tempo,
                "snitt_puls":     a.get("averageHR"),
                "maks_puls":      a.get("maxHR"),
                "load":           round(a.get("activityTrainingLoad", 0), 1),
                "treningseffekt": a.get("trainingEffectLabel"),
                "aerob_effekt":   round(a.get("aerobicTrainingEffect", 0), 1),
                "anaerob_effekt": round(a.get("anaerobicTrainingEffect", 0), 1),
                "vo2max":         a.get("vO2MaxValue"),
                "bb_tap":         a.get("differenceBodyBattery"),
                "kalorier":       a.get("calories"),
                "hoydemeter":     a.get("elevationGain"),
                "bakketid_ms":    round(a["avgGroundContactTime"]) if a.get("avgGroundContactTime") else None,
                "vert_osc_cm":    round(a["avgVerticalOscillation"], 1) if a.get("avgVerticalOscillation") else None,
                "vert_ratio_pst": round(a["avgVerticalRatio"], 1) if a.get("avgVerticalRatio") else None,
                "steglengde_cm":  round(a["avgStrideLength"]) if a.get("avgStrideLength") else None,
                "kadens":         round(a["averageRunningCadenceInStepsPerMinute"]) if a.get("averageRunningCadenceInStepsPerMinute") else None,
                "puls_sone_1":    round(a.get("hrTimeInZone_1", 0)),
                "puls_sone_2":    round(a.get("hrTimeInZone_2", 0)),
                "puls_sone_3":    round(a.get("hrTimeInZone_3", 0)),
                "puls_sone_4":    round(a.get("hrTimeInZone_4", 0)),
                "puls_sone_5":    round(a.get("hrTimeInZone_5", 0)),
            })

        return resultat
    except Exception as e:
        print(f"Aktiviteter feil: {e}")
        return []


def hent_planlagt_okt(api):
    try:
        workouts = api.get_workouts(0, 20)
        if not workouts:
            return None

        for w in workouts:
            scheduled = w.get("scheduledDate", "")[:10]
            if scheduled == DATO_STR:
                workout_id = w.get("workoutId")
                detalj = api.get_workout_by_id(workout_id)

                steps = []
                for step in detalj.get("workoutSegments", [{}])[0].get("workoutSteps", []):
                    step_type = step.get("type", "")
                    if step_type == "ExecutableStepDTO":
                        intensity = step.get("intensity", "")
                        duration  = step.get("endCondition", {})
                        target    = step.get("targetType", {})
                        steps.append({
                            "type":      intensity,
                            "varighet":  duration.get("conditionTypeKey"),
                            "verdi":     duration.get("conditionValue"),
                            "mal_type":  target.get("conditionTypeKey"),
                            "mal_fra":   step.get("targetValueOne"),
                            "mal_til":   step.get("targetValueTwo"),
                        })
                    elif step_type == "RepeatGroupDTO":
                        repeats = step.get("numberOfIterations", 1)
                        for substep in step.get("workoutSteps", []):
                            intensity = substep.get("intensity", "")
                            duration  = substep.get("endCondition", {})
                            target    = substep.get("targetType", {})
                            steps.append({
                                "type":      intensity,
                                "repeats":   repeats,
                                "varighet":  duration.get("conditionTypeKey"),
                                "verdi":     duration.get("conditionValue"),
                                "mal_type":  target.get("conditionTypeKey"),
                                "mal_fra":   substep.get("targetValueOne"),
                                "mal_til":   substep.get("targetValueTwo"),
                            })

                return {
                    "navn":        detalj.get("workoutName"),
                    "type":        detalj.get("sportType", {}).get("sportTypeKey"),
                    "dato":        scheduled,
                    "beskrivelse": detalj.get("description"),
                    "steg":        steps,
                }

        return None

    except Exception as e:
        print(f"Planlagt okt feil: {e}")
        return None


def main():
    print(f"Garmin morgendata - {DATO_STR}")
    api = logg_inn()

    planlagt = hent_planlagt_okt(api)
    if planlagt:
        print(f"Planlagt okt: {planlagt.get('navn')}")
    else:
        print("Ingen planlagt okt funnet for i dag")

    data = {
        "dato":               DATO_STR,
        "hrv":                hent_hrv(api),
        "sovn":               hent_sovn(api),
        "dag":                hent_dagsstatus(api),
        "body_battery":       hent_body_battery(api),
        "treningsbelastning": hent_treningsbelastning(api),
        "siste_aktiviteter":  hent_aktiviteter(api, antall=3),
        "planlagt_okt":       planlagt,
    }

    hrv  = data["hrv"]
    dag  = data["dag"]
    bb   = data["body_battery"]
    load = data["treningsbelastning"]
    sovn = data["sovn"]

    print(f"\n── SAMMENDRAG ────────────────────────")
    print(f"  HRV     : {hrv.get('nattlig_snitt')} ms [{hrv.get('status')}] (uke: {hrv.get('ukentlig_snitt')})")
    print(f"  Puls    : {dag.get('hvilepuls')} bpm | Stress: {dag.get('stress_snitt')}")
    print(f"  BB      : {bb.get('maks')}/100 (+{bb.get('ladet')})")
    print(f"  Sovn    : {sovn.get('total_min')} min (score: {sovn.get('score')})")
    print(f"  ACWR    : {load.get('acwr')} [{load.get('acwr_status')}]")
    print(f"  Status  : {load.get('status')}")
    if data["siste_aktiviteter"]:
        s = data["siste_aktiviteter"][0]
        print(f"  Siste   : {s['navn']} {s['dist_km']}km | {s['snitt_tempo']} | {s['snitt_puls']}bpm | load {s['load']}")
    if planlagt:
        print(f"  I dag   : {planlagt['navn']} ({len(planlagt['steg'])} steg)")

    json_fil = f"garmin_data_{DATO_STR}.json"
    with open(json_fil, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\nLagret: {json_fil}")


if __name__ == "__main__":
    main()
