# garmin-morgenrapport

Automatisk daglig treningsrapport for Øyvind Grønner.
Henter data fra TrainingPeaks og Strava, genererer coaching-analyse med Claude,
og sender rapport til Gmail kl. 07:00 UTC (09:00 CEST).

---

## Repostruktur

```
garmin-morgenrapport/
├── .github/
│   └── workflows/
│       └── morgenrapport.yml   # GitHub Actions — kjører kl. 07:00 UTC daglig
├── morgen.py                   # Datahenting: Strava + TrainingPeaks → garmin_data_DATO.json
├── claude_analyse.py           # Coaching-analyse via Claude API, skriver til JSON
├── send_epost.py               # Rapportbygging og Gmail-levering
├── sjekk_cookie.py             # Varsler på e-post hvis TP-cookie utløper om ≤7 dager
├── strava_hent.py              # Eldre standalone Strava-skript (ikke i workflow)
├── tp_morgen.py                # Eldre standalone TP-skript (ikke i workflow)
└── requirements.txt
```

Output: `garmin_data_DATO.json` — bygges av `morgen.py`, suppleres av `claude_analyse.py`.

---

## Dataflyt

```
morgen.py ──► garmin_data_DATO.json ──► claude_analyse.py ──► send_epost.py ──► Gmail
               (Strava + TrainingPeaks)    (legger til          (leser JSON,
                                            claude_analyse-felt)  bygger e-post)
```

Workflow-rekkefølge:
1. `sjekk_cookie.py` — varsler hvis TP-cookie utløper snart
2. `morgen.py` — henter Strava-aktiviteter + TrainingPeaks helse/fitness
3. `claude_analyse.py` — kaller Claude API og skriver analyse til JSON
4. `send_epost.py` — sender ferdig rapport

---

## GitHub Secrets

| Secret               | Brukes av                        | Beskrivelse                        |
|----------------------|----------------------------------|------------------------------------|
| STRAVA_CLIENT_ID     | morgen.py                        | Strava app client ID (211629)      |
| STRAVA_CLIENT_SECRET | morgen.py                        | Strava app client secret           |
| STRAVA_REFRESH_TOKEN | morgen.py                        | Strava refresh token               |
| TP_AUTH_COOKIE       | morgen.py, sjekk_cookie.py       | TrainingPeaks Production_tpAuth    |
| ANTHROPIC_API_KEY    | claude_analyse.py                | Claude API-nøkkel                  |
| GMAIL_USER           | send_epost.py, sjekk_cookie.py   | Gmail-adresse for sending          |
| GMAIL_APP_PASSWORD   | send_epost.py, sjekk_cookie.py   | Gmail app-passord                  |

Garmin-data hentes IKKE direkte. HRV, søvn og Body Battery hentes fra
TrainingPeaks sin helsedata-API (`consolidatedtimedmetrics`), som speiler Garmin-data.

TP-cookie fornyes via Safari → Web Inspector → Nettverk-fane → kopier Cookie-header
→ `gh secret set TP_AUTH_COOKIE --repo oyvindgronner/garmin-morgenrapport`

---

## Kjente problemer / begrensninger

### TrainingPeaks cookie
- Utløper typisk ~12 måneder etter siste innlogging.
- `sjekk_cookie.py` sender e-postvarsel når det er ≤7 dager igjen.
- Fornyes manuelt ved å hente ny `Production_tpAuth`-verdi fra Safari.

### Strava streams
- Full stream hentes nå (alle datapunkter). Tidligere bug med `[:10]` er fikset.

### Gmail-tidsstempler
- Rapporter sendes kl. 07:00 UTC = 09:00 norsk tid (CEST).

---

## Lokalt oppsett

```bash
git clone https://github.com/oyvindgronner/garmin-morgenrapport.git
cd garmin-morgenrapport
pip install requests anthropic

# Manuell kjøring
gh workflow run morgenrapport.yml
gh run watch
```

---

## Fysiologiske referanseverdier

Terskelpuls: ~166 bpm | FTP: 327W | VO2max: 56 | Vekt: 73 kg | HRV balansert: 70–98 ms

Pulssoner: S1 <139 / S2 139–148 / S3 149–158 / S4 159–169 / S5 >169 bpm
Wattsoner: S1 <196 / S2 196–245 / S3 246–294 / S4 295–344 / S5 345–392 / S6 >392 W

Rasekalender: Madrid HM 22.03.2026 (1:26:59, PR) | Hamburg Maraton 26.04.2026 (mål: sub 3:00)
Fase: Siste byggeblokk + taper. Metode: Norwegian Singles — 1 terskeløkt (14. april), resten maratonspesifikk volum.
CTL-mål inn mot Hamburg: 58–65 | TSB race-uka: +12 til +20

## Trenerprogram frem til Hamburg (oppdatert 30. mars 2026)

Nøkkelprioriteringer:
- Maratonspesifikk CTL via volum og maratontempodrag — ikke terskelvolum
- Én terskeløkt totalt (14. april)
- Stor nøkkeløkt: 28 km langtur 12. april (16 km i maratonfart)
- Påskeuka (1.–5. april): kun skigåing, ingen løping
- Taper starter 19. april

Dragtempo maratonfart: 4:16–4:12/km
Terskelfart: 4:02–3:58/km
Gel-strategi race-dag: hver 30–35 min

Fullt program ligger i ukeplan.json (31. mars – 26. april).

---

## Regler ved kodeendringer

1. Aldri hardkode credentials — bruk GitHub Secrets.
2. Ikke legg til retry-loops mot eksterne API-er.
3. Ikke endre feltnavn i garmin_data_DATO.json uten å oppdatere alle konsumenter
   (`claude_analyse.py` og `send_epost.py`).
4. Rapporten er plain text — ikke HTML, ikke vedlegg.
5. Test med `gh workflow run` før du regner endringen som ferdig.
