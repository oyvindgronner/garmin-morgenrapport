#!/usr/bin/env python3
"""
garmin_auth.py  —  KUN kjøres lokalt, én gang
==============================================
Logger inn med brukernavn/passord og lagrer OAuth2-tokens.
Tokens settes deretter som GitHub Secret og brukes av garmin_direkte.py
uten noen ny innlogging (unngår rate limiting).

Bruk:
    python garmin_auth.py
    → Oppgir e-post og passord
    → Skriver ut token-streng
    → Kjør: gh secret set GARMIN_TOKENS --body "<token-streng>"

Tokens varer typisk 90 dager. Kjør dette scriptet på nytt ved utløp.
"""

import getpass
import sys


def main():
    try:
        import garth
    except ImportError:
        print("Installer garth: pip install garth")
        sys.exit(1)

    print("=== Garmin Connect token-generator ===")
    print("Tokens lagres IKKE lokalt — kopieres direkte til GitHub Secret\n")

    epost  = input("Garmin e-post: ").strip()
    passord = getpass.getpass("Garmin passord: ")

    print("\nLogger inn på Garmin Connect...")
    try:
        garth.login(epost, passord)
    except Exception as e:
        print(f"Innlogging feilet: {e}")
        sys.exit(1)

    token_str = garth.client.dumps()
    print("\n✅ Innlogging vellykket!\n")
    print("=" * 60)
    print("Kjør denne kommandoen for å lagre tokens som GitHub Secret:")
    print("=" * 60)
    print(f'\ngh secret set GARMIN_TOKENS --body \'{token_str}\' --repo oyvindgronner/garmin-morgenrapport\n')
    print("=" * 60)
    print("\nTokens varer ~90 dager. Kjør garmin_auth.py på nytt ved utløp.")


if __name__ == "__main__":
    main()
