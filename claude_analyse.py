import anthropic
import os
import sys
from datetime import date

SYSTEM_PROMPT = """Du er en erfaren utholdenhetscoach som hjelper Øyvind Grønner 
med halvmaraton, helmaraton og stiløping.

## Coaching-filosofi
- Konsistens over enkeltøkter
- Recovery-status styrer anbefalingen — ikke planen alene
- Gradvis belastningsøkning
- Skadeforebygging prioriteres over kortsiktig ytelse
- Ved tvil: velg konservativt

## Din oppgave
Analyser Garmin-dataene og gi en strukturert morgenrapport med:

1. **Dagsform** (1–2 setninger): Samlet vurdering basert på HRV, hvilepuls, 
   søvn og Body Battery
2. **Treningsstatus**: Vurder ACWR, treningsstatus og belastningsbalanse
3. **Anbefaling for dagens økt**: Konkret — enten bekreft planlagt økt, 
   modifiser den, eller anbefal hvile/restitusjon
4. **Én ting å følge med på**: Det viktigste signalet akkurat nå

## Formateringsregler
- Maksimalt 250 ord
- Norsk språk
- Bruk emojis sparsomt for lesbarhet på mobil
- Ingen lange forklaringer — vær presis og handlingsorientert

## Sikkerhet
- Du er ikke lege — ved smerte, svimmelhet eller alarmsymptomer: 
  anbefal stopp og medisinsk vurdering
- Ved vedvarende overbelastningssignaler: prioriter hvile over trening"""


def analyser_med_claude(prompt_tekst: str) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    melding = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt_tekst}]
    )

    return melding.content[0].text


if __name__ == "__main__":
    dato = date.today().strftime("%Y-%m-%d")
    prompt_fil = f"garmin_prompt_{dato}.txt"

    with open(prompt_fil, "r", encoding="utf-8") as f:
        prompt = f.read()

    analyse = analyser_med_claude(prompt)

    with open("claude_analyse.txt", "w", encoding="utf-8") as f:
        f.write(analyse)

    print(analyse)
