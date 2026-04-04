# garmin-morgenrapport

Treningsdashboard og morgenrapport for Øyvind Grønner — Hamburg Maraton 26. april 2026 (mål: sub 3:00).

---

## Repostruktur

```
garmin-morgenrapport/
├── .github/workflows/morgenrapport.yml   # Workflow — kun manuell trigger (workflow_dispatch)
├── morgen.py                             # Datahenting: Strava + TrainingPeaks → garmin_data_DATO.json
├── claude_analyse.py                     # Coaching-analyse via Claude API + lagrer kommentarer
├── generer_dashboard.py                  # Genererer docs/index.html (kryptert AES-256-GCM)
├── send_epost.py                         # Rapportbygging og Gmail-levering
├── sjekk_cookie.py                       # Varsler på e-post hvis TP-cookie utløper om ≤7 dager
├── ukeplan.json                          # Treningsprogram frem til Hamburg — redigeres direkte
├── okt_logg.json                         # Persistent kommentarhistorikk (siste 10 følger med i analyse)
├── docs/index.html                       # Ferdig kryptert dashboard (GitHub Pages)
└── requirements.txt
```

---

## Dataflyt

### 1. GitHub Actions (workflow_dispatch)
```
morgen.py ──► garmin_data_DATO.json ──► git push
```

### 2. Lokalt i Claude Code
```
Les siste garmin_data_DATO.json
    ↓
Coaching-analyse genereres her i Claude Code
    ↓
generer_dashboard.py ──► docs/index.html (kryptert, GitHub Pages)
    ↓
git commit + push
```

**Trigger:** Kun manuell — `workflow_dispatch` (knapp "Hent ferske data" på dashboardet, eller `gh workflow run morgenrapport.yml`).

---

## Dashboard

- **URL:** https://oyvindgronner.github.io/garmin-morgenrapport/
- **Passord:** hamburg26
- **Design:** Blå #0075be, gull #c9a227, Open Sans, Hamburg-skyline
- **Kryptering:** AES-256-GCM — `generer_dashboard.py` krypterer payload, nøkkel er passordet
- Knappen "Hent ferske data" sender `workflow_dispatch` + poller GitHub Actions for fremdrift, reloader automatisk når ferdig

---

## Treningsplan — ukeplan.json

**Dette er den eneste filen som redigeres for treningsplanendringer.**

Skjema for én økt:
```json
{
  "dato": "2026-04-07",        // ISO-dato, PÅKREVD
  "type": "Maratonspesifikk",  // Se gyldige typer under
  "beskrivelse": "...",        // Fritekst, detaljert
  "dist_km": 17.0,             // Desimaltall
  "tempo_min_km": "4:16–4:12", // Streng, valgfri
  "varighet_min": 90,          // Heltall
  "puls_sone": "S3–S4"         // Streng, valgfri
}
```

**Gyldige økt-typer:** Rolig | Terskel | Intervall | Langtur | Maratonspesifikk | Ski+Løp | Ski | Styrke | Rase | Hvile

**Når bruker sier:** "flytt løpet fra tirsdag til onsdag", "endre X til Y", "legg til ny økt", "marker X som gjennomført" → rediger `ukeplan.json` direkte, commit og push.

---

## GitHub Secrets

| Secret                 | Brukes av                                   |
|------------------------|---------------------------------------------|
| STRAVA_CLIENT_ID       | morgen.py (workflow)                        |
| STRAVA_CLIENT_SECRET   | morgen.py (workflow)                        |
| STRAVA_REFRESH_TOKEN   | morgen.py (workflow)                        |
| TP_AUTH_COOKIE         | morgen.py (workflow), sjekk_cookie.py       |
| GMAIL_USER             | send_epost.py, sjekk_cookie.py (manuelt)    |
| GMAIL_APP_PASSWORD     | send_epost.py, sjekk_cookie.py (manuelt)    |
| DASHBOARD_GITHUB_TOKEN | generer_dashboard.py (lokalt, inn i HTML)   |
| DASHBOARD_PASSWORD     | generer_dashboard.py (lokalt, krypteringsnøkkel) |

Garmin-data hentes IKKE direkte — søvn, HRV og Body Battery hentes via TrainingPeaks sin
helsedata-API (`consolidatedtimedmetrics`) som speiler Garmin-data.

TP-cookie fornyes: Safari → Web Inspector → Nettverk → kopier Cookie-header →
`gh secret set TP_AUTH_COOKIE --repo oyvindgronner/garmin-morgenrapport`

---

## Fysiologiske referanseverdier

| Parameter        | Verdi                          |
|------------------|-------------------------------|
| Terskelpuls      | ~166 bpm                      |
| FTP              | 327W                          |
| VO2max           | 56                            |
| Vekt             | 73 kg                         |
| HRV balansert    | 70–98 ms                      |

Pulssoner: S1 <139 / S2 139–148 / S3 149–158 / S4 159–169 / S5 >169 bpm
Wattsoner: S1 <196 / S2 196–245 / S3 246–294 / S4 295–344 / S5 345–392 / S6 >392 W

Dragtempo maratonfart: 4:16–4:12/km
Terskelfart: 4:02–3:58/km

---

## Treningsstrategi frem til Hamburg

- Metode: Norwegian Singles — minimal terskelvolum, maratonspesifikk belastning
- Én terskeløkt totalt: 14. april
- Nøkkeløkt: 28 km langtur 12. april (16 km i maratonfart)
- Påskeuka 1.–5. april: ski + lett løp, ingen kvalitetsøkter
- Taper starter 19. april
- CTL-mål inn mot Hamburg: 58–65
- TSB race-uka: +12 til +20
- Gel race-dag: ca. hver 30–35 min

Rasekalender: Madrid HM 22.03.2026 (1:26:59, PR) | Hamburg Maraton 26.04.2026

---

## Regler ved kodeendringer

1. Aldri hardkode credentials — bruk GitHub Secrets (workflow) eller `.env` (lokalt).
2. Ikke legg til retry-loops mot eksterne API-er.
3. Ikke endre feltnavn i `garmin_data_DATO.json` uten å oppdatere alle konsumenter (`generer_dashboard.py`).
4. Test workflow med `gh workflow run morgenrapport.yml` + `gh run watch` før endringen regnes som ferdig.
5. `docs/index.html` skal aldri redigeres direkte — genereres alltid av `generer_dashboard.py`.
