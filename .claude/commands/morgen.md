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

Analyser dataene som en erfaren løpetrener med fokus på Hamburg Maraton 26. april 2026 (mål: sub 3:00). Følg **nøyaktig** dette outputformatet (brukes av dashboardet):

```
✅/⚠️/🔴 [STATUS] — [Én setning begrunnelse, maks 20 ord]

SISTE ØKT:
[Vurder siste økt: NP, IF, TSS, EF, puls. Maks 3 setninger med konkrete tall.]

BELASTNINGSBILDE:
[CTL-utvikling, ATL, TSB-trend, nødvendig daglig TSS. Maks 4 setninger.]

HAMBURG-STATUS:
[CTL nå vs mål 58–65, TSB race-dag. Maks 3 setninger.]

DAGSFORM:
[Kun det verdt å nevne: HRV, søvn, Body Battery. Ikke kommenter normalverdier med mer enn ett ord.]

BELASTNINGSVURDERING I DAG:
→ GJENNOMFØR SOM PLANLAGT / LEGG PÅ: [justering] / REDUSER: [justering]
[Én setning begrunnelse basert på HRV, TSB og CTL-gap.]
```

Regler:
- Maks 320 ord totalt
- Norsk språk
- Kvantifiser alltid: bpm, watt, km, TSS, IF
- Beregn IF = NP/327, TSS = (varighet_sek × NP × IF) / (327 × 3600) × 100, EF = NP/snitt_puls
- Bruk fysiologiske referanseverdier fra CLAUDE.md

## Steg 3b – Lagre analysen til JSON

Etter at analysen er generert, **lagre den til JSON-filen** slik at dashboardet kan vise den:

```python
import json

analyse_tekst = """[SETT INN ANALYSEN HER]"""

with open('garmin_data_DATO.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
data['claude_analyse'] = analyse_tekst
with open('garmin_data_DATO.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
```

Kjør dette som et python3-skript med riktig filnavn og den faktiske analyseteksten.

## Steg 4 – Generer og push dashboard

```
python3 generer_dashboard.py
git add docs/index.html garmin_data_DATO.json
git commit -m "Dashboard oppdatert DATO"
git push
```

Bekreft til slutt at alt gikk bra og vis en kort oppsummering av analysen.
