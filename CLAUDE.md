# garmin-morgenrapport

Automatisk daglig treningsrapport for Øyvind Grønner.
Henter data fra Garmin Connect, TrainingPeaks og Strava/Stryd,
bygger en JSON-fil og sender rapport til Gmail kl. 07:00 CEST.

---

## Repostruktur
cd ~/Desktop/garmin-repo-temp
git pull
cat > CLAUDE.md << 'EOF'
# garmin-morgenrapport

Automatisk daglig treningsrapport for Øyvind Grønner.
Henter data fra Garmin Connect, TrainingPeaks og Strava/Stryd,
bygger en JSON-fil og sender rapport til Gmail kl. 07:00 CEST.

---

## Repostruktur
```
garmin-morgenrapport/
├── .github/
│   └── workflows/
│       └── morgenrapport.yml   # GitHub Actions — kjører kl. 07:00 UTC daglig
├── garmin_morgen.py            # Datahenting: Garmin Connect (HRV, søvn, BB, aktiviteter)
├── tp_morgen.py                # Datahenting: TrainingPeaks (CTL/ATL/TSB)
├── strava_hent.py              # Datahenting: Strava + Stryd (watt, streams)
├── generate_report.py          # Rapportbygging og Gmail-levering
├── finn_url.py                 # TrainingPeaks cookie/token-hjelper (kjøres lokalt)
└── requirements.txt
```

Output: `garmin_data_DATO.json` — bygges av datascriptene, leses av `generate_report.py`.

---

## Dataflyt
```
garmin_morgen.py  ─┐
tp_morgen.py      ─┼──► garmin_data_DATO.json ──► generate_report.py ──► Gmail
strava_hent.py    ─┘
```

---

## GitHub Secrets (aldri hardkode disse)

| Secret               | Brukes av          | Beskrivelse                          |
|----------------------|--------------------|--------------------------------------|
| GARMIN_OAUTH1        | garmin_morgen.py   | Garmin OAuth1-token (JSON)           |
| GARMIN_OAUTH2        | garmin_morgen.py   | Garmin OAuth2-token (JSON)           |
| GMAIL_USER           | generate_report.py | Gmail-adresse for sending            |
| GMAIL_APP_PASSWORD   | generate_report.py | Gmail app-passord                    |
| STRAVA_CLIENT_ID     | strava_hent.py     | Strava app client ID (211629)        |
| STRAVA_CLIENT_SECRET | strava_hent.py     | Strava app client secret             |
| STRAVA_REFRESH_TOKEN | strava_hent.py     | Strava refresh token                 |
| TP_AUTH_COOKIE       | tp_morgen.py       | TrainingPeaks Production_tpAuth      |

TP-cookie utløper ~12. april 2026. Fornyes via Safari → Web Inspector → Storage →
Cookies → app.trainingpeaks.com. Bruk finn_url.py for å hente gyldig token.

---

## Kjente problemer

### Garmin rate limit (HTTP 429)
- Garmin sin uoffisielle API blokkerer for mange requests i kort tidsvindu.
- Nåværende løsning: OAuth-tokens injisert via GitHub Secrets (GARMIN_OAUTH1/2).
- Ikke legg til retry-loops — det forverrer blokkingen.
- Planlagt løsning: Terra API (tryterra.co) via offisiell push-mekanisme.

### TrainingPeaks API
- To-stegs auth: GET /users/v3/token → Bearer → GET /users/v3/user
- userId ligger under response["user"]["userId"]
- CTL/ATL/TSB: POST til /fitness/v1/athletes/{id}/reporting/performancedata/{start}/{end}
- GET med query-params returnerer 404.

### Strava streams
- Streams returnerer kun de første 10 datapunktene — må fikses.

### Gmail-tidsstempler
- Rapporter sendes i PDT (UTC-7). Kl. 07:00 UTC = kl. 09:00 norsk tid (CEST).

---

## Lokalt oppsett
```
git clone https://github.com/oyvindgronner/garmin-morgenrapport.git
cd garmin-morgenrapport
pip install -r requirements.txt

# TrainingPeaks token-hjelper
python3 ~/Desktop/finn_url.py "$(cat ~/Desktop/cookie.txt)"

# Manuell kjøring
gh workflow run morgenrapport.yml
gh run watch
```

---

## Fysiologiske referanseverdier

Terskelpuls: ~166 bpm | FTP: 327W | VO2max: 56 | Vekt: 73 kg | HRV balansert: 70–98 ms

Pulssoner: S1 <139 / S2 139–148 / S3 149–158 / S4 159–169 / S5 >169 bpm
Wattsoner: S1 <196 / S2 196–245 / S3 246–294 / S4 295–344 / S5 345–392 / S6 >392 W

Rasekalender: Madrid HM 22.03.2026 (gjennomført, ~1:27) | Hamburg Maraton 26.04.2026 (sub 3:00)
Fase: Hamburg-oppbygging. Metode: Norwegian Singles — 2 terskeløkter/uke.

---

## Regler ved kodeendringer

1. Aldri hardkode credentials — bruk GitHub Secrets.
2. Ikke legg til retry-loops mot Garmin API.
3. Ikke endre feltnavn i garmin_data_DATO.json uten å oppdatere alle konsumenter.
4. Rapporten skal være plain text — ikke HTML, ikke vedlegg.
5. Test med gh workflow run før du regner endringen som ferdig.
