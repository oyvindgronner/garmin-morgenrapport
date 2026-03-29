#!/usr/bin/env python3
"""
sjekk_cookie.py
===============
Sjekker om TP_AUTH_COOKIE utløper snart og varsler på e-post.
"""

import os
import base64
import json
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def les_utlop(cookie: str) -> datetime | None:
    """Dekoder JWT og returnerer utløpstidspunkt."""
    try:
        # JWT har tre deler separert med punktum
        deler = cookie.strip().split(".")
        if len(deler) < 2:
            return None
        # Legg til padding hvis nødvendig
        payload = deler[1]
        payload += "=" * (4 - len(payload) % 4)
        data = json.loads(base64.b64decode(payload))
        exp = data.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
    except Exception:
        return None
    return None


def main():
    cookie = os.environ.get("TP_AUTH_COOKIE", "")
    if not cookie:
        print("TP_AUTH_COOKIE ikke satt")
        return

    utlop = les_utlop(cookie)
    if not utlop:
        print("Kunne ikke lese utløpsdato fra cookie")
        return

    na = datetime.now(tz=timezone.utc)
    dager_igjen = (utlop - na).days

    print(f"Cookie utløper: {utlop.strftime('%Y-%m-%d')} ({dager_igjen} dager igjen)")

    if dager_igjen > 7:
        print("Cookie er gyldig — ingen varsling nødvendig")
        return

    # Send varsel
    gmail_user     = os.environ.get("GMAIL_USER", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")
    if not gmail_user or not gmail_password:
        print("Mangler Gmail-credentials — kan ikke sende varsel")
        return

    brodtekst = f"""⚠️ TrainingPeaks cookie utløper om {dager_igjen} dager ({utlop.strftime('%Y-%m-%d')}).

Gjør dette for å fornye:

1. Gå til app.trainingpeaks.com i Safari og logg inn
2. Åpne Developer Tools: Cmd + Option + I
3. Klikk Nettverk-fanen
4. Last siden på nytt: Cmd + R
5. Klikk på første rad i listen
6. Klikk Hodedeler → finn Cookie: → høyreklikk → Kopier verdi
7. Kjør i Terminal:
   gh secret set TP_AUTH_COOKIE --repo oyvindgronner/garmin-morgenrapport

Lim inn cookie-verdien når du blir spurt.

Morgenrapporten vil slutte å fungere hvis dette ikke gjøres innen {utlop.strftime('%Y-%m-%d')}.
"""

    msg = MIMEMultipart()
    msg["From"]    = gmail_user
    msg["To"]      = gmail_user
    msg["Subject"] = f"⚠️ TrainingPeaks cookie utløper om {dager_igjen} dager"
    msg.attach(MIMEText(brodtekst, "plain", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.send_message(msg)

    print(f"Varsel sendt til {gmail_user}")


if __name__ == "__main__":
    main()
