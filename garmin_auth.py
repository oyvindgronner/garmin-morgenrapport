#!/usr/bin/env python3
"""
garmin_auth.py  —  KUN kjøres lokalt, én gang
==============================================
Logger inn med brukernavn/passord, henter OAuth2-tokens og setter
GitHub Secret direkte via subprocess — ingen copy-paste, ingen escaping-feil.

Bruk:
    python garmin_auth.py

Tokens varer typisk 90 dager. Kjør dette scriptet på nytt ved utløp.
"""

import getpass
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

REPO = "oyvindgronner/garmin-morgenrapport"


def main():
    try:
        import garth
    except ImportError:
        print("Installer garth: pip install garth")
        sys.exit(1)

    print("=== Garmin Connect token-generator ===\n")

    epost   = input("Garmin e-post: ").strip()
    passord = getpass.getpass("Garmin passord: ")

    print("\nLogger inn på Garmin Connect...")
    try:
        garth.login(epost, passord)
    except Exception as e:
        print(f"Innlogging feilet: {e}")
        sys.exit(1)

    token_str = garth.client.dumps()
    print("✅ Innlogging vellykket!")

    # Sett secret direkte via subprocess (unngår shell-escaping av base64)
    print(f"\nSetter GARMIN_TOKENS i {REPO}...")
    try:
        result = subprocess.run(
            ["gh", "secret", "set", "GARMIN_TOKENS",
             "--body", token_str,
             "--repo", REPO],
            capture_output=True, text=True, check=True
        )
        print("✅ GARMIN_TOKENS satt!")
        print(f"\nTokens varer ~90 dager. Kjør garmin_auth.py på nytt ved utløp.")
    except subprocess.CalledProcessError as e:
        print(f"Feil ved setting av secret: {e.stderr}")
        print("\nAlternativt — lagre token til fil og bruk:")
        with open("/tmp/garmin_tokens.txt", "w") as f:
            f.write(token_str)
        print('  gh secret set GARMIN_TOKENS < /tmp/garmin_tokens.txt --repo ' + REPO)


if __name__ == "__main__":
    main()
