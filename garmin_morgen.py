#!/usr/bin/env python3
"""
garmin_morgen.py
================
Henter helsedata fra Garmin Connect og genererer et ferdig
dagsform-prompt til AI-trener.

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
    print("Mangler garminconnect. Installer med:")
    print("  pip install garminconnect garth")
    sys.exit(1)

# ──────────────────────────────────────────────
# KONFIGURASJON
# ──────────────────────────────────────────────

TOKENSTI = os.path.expanduser("~/.garth")
DATO     = date.today()
DATO_STR = DATO.isoformat()

BASELINE_HRV     = None
BASELINE_RHR     = None
BASELINE_BB_MORN = None

# ──────────────────────────────────────────────
# INNLOGGING
# ──────────────────────────────────────────────

def logg_inn():
    """
    Logger inn med:
    1. Miljøvariabler (GARMIN_EMAIL + GARMIN_PASSWORD) — brukes av GitHub Actions
    2. Lagret token (~/.garth) — brukes lokalt på Mac etter første innlogging
    3. Manuell innlogging — første gang lokalt
    """
    epost   = os.environ.get("GARMIN_EMAIL")
    passord = os.environ.get("GARMIN_PASSWORD")

    if epost and passord:
        print("🔑 Logger inn med miljøvariabler (GitHub Actions-modus)...")
        api = Garmin(epost, passord)
        api.login()
        print("✅ Innlogget via miljøvariabler")
        return api

    api = Garmin()
    try:
        api.login(TOKENSTI)
        print(f"✅ Innlogget med lagret token ({TOKENSTI})")
        return api
    except Exception:
        pass

    print("Ingen lagret innlogging funnet. Logg inn:")
    epost   = input("Garmin e-post: ").strip()
    passord = getpass("Garmin passord: ")
    api = Garmin(epost, passord)
    api.login()
    api.garth.dump(TOKENSTI)
    print(f"✅ Innlogget og token lagret i {TOKENSTI}")
    return api

# ──────────────────