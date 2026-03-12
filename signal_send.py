import requests
import os
import urllib.parse
from datetime import date


def send_signal(tekst: str):
    telefon = os.environ["SIGNAL_PHONE"]
    api_key = os.environ["SIGNAL_API_KEY"]

    melding = urllib.parse.quote(tekst)
    url = (
        f"https://api.callmebot.com/signal/send.php"
        f"?phone={telefon}&apikey={api_key}&text={melding}"
    )

    response = requests.get(url, timeout=30)

    if response.status_code == 200:
        print("✅ Signal-melding sendt")
    else:
        print(f"❌ Feil ved sending: {response.status_code} — {response.text}")
        raise SystemExit(1)


if __name__ == "__main__":
    dato = date.today().strftime("%Y-%m-%d")

    with open("claude_analyse.txt", "r", encoding="utf-8") as f:
        analyse = f.read()

    header = f"🏃 Treningsanalyse {dato}\n{'─'*30}\n"
    send_signal(header + analyse)
