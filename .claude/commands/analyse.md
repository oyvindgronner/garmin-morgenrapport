Utfør full morgenanalyse for Øyvind. Gjør følgende steg i rekkefølge:

1. **Finn siste JSON**: Finn den nyeste `garmin_data_DATO.json`-filen i repoet (sorter på dato i filnavnet).

2. **Les dataene**: Les hele JSON-filen.

3. **Generer coaching-analyse**: Analyser dataene som en erfaren løpetrener med fokus på Hamburg Maraton 26. april 2026 (mål: sub 3:00). Inkluder:
   - Dagens form: HRV, søvn, Body Battery, hvilepuls — vurder treningsberedskap
   - Siste aktivitet(er): kvalitet, intensitet, utførelse vs. plan
   - CTL/ATL/TSB: treningsbelastning og recovery-status
   - Anbefaling for dagen: hva bør prioriteres i dag basert på data og ukeplan
   - Evt. avvik fra treningsplan og konsekvenser
   Bruk fysiologiske referanseverdier fra CLAUDE.md (terskelpuls ~166, FTP 327W, HRV-balanse 70–98 ms, etc.)

4. **Kjør generer_dashboard.py**: Kjør `python generer_dashboard.py` lokalt for å oppdatere `docs/index.html`.

5. **Commit og push**:
   ```
   git add docs/index.html
   git commit -m "Dashboard oppdatert DATO"
   git push
   ```
