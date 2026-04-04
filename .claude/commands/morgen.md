Kjør hele morgenrutinen i ett: hent data, analyser og oppdater dashboardet.

Gjør følgende steg i rekkefølge — stopp og si ifra hvis noe feiler:

## Steg 1 – Trigger GitHub Actions workflow

Kjør:
```
gh workflow run morgenrapport.yml --repo oyvindgronner/garmin-morgenrapport
```

Vent 5 sekunder, hent så workflow run-ID:
```
gh run list --repo oyvindgronner/garmin-morgenrapport --limit 1 --json databaseId,status,conclusion
```

Poll hvert 15. sekund med samme kommando inntil `status` er `completed`. Vis gjerne en kort statusmelding for hvert poll («⏳ Venter på GitHub Actions… (Xs)»). Maks ventetid: 5 minutter. Hvis `conclusion` ikke er `success` når ferdig — stopp og vis feilmeldingen.

## Steg 2 – Hent ny JSON lokalt

```
git pull
```

Finn den nyeste `garmin_data_DATO.json`-filen i repoet (sorter på dato i filnavnet) og les hele innholdet.

## Steg 3 – Generer coaching-analyse

Analyser dataene som en erfaren løpetrener med fokus på Hamburg Maraton 26. april 2026 (mål: sub 3:00). Inkluder:
- Dagens form: HRV, søvn, Body Battery, hvilepuls — vurder treningsberedskap
- Siste aktivitet(er): kvalitet, intensitet, utførelse vs. plan
- CTL/ATL/TSB: treningsbelastning og recovery-status
- Anbefaling for dagen: hva bør gjøres i dag basert på data og ukeplan
- Evt. avvik fra treningsplan og konsekvenser

Bruk fysiologiske referanseverdier fra CLAUDE.md (terskelpuls ~166 bpm, FTP 327W, HRV-balanse 70–98 ms, maratonfart 4:16–4:12/km, etc.)

## Steg 4 – Generer og push dashboard

```
python generer_dashboard.py
git add docs/index.html
git commit -m "Dashboard oppdatert DATO"
git push
```

Bekreft til slutt at alt gikk bra og vis en kort oppsummering av analysen.
