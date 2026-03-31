#!/usr/bin/env python3
"""
generer_dashboard.py
====================
Genererer docs/index.html fra dagens garmin_data JSON og ukeplan.json.
All helsedata krypteres med AES-256-GCM (PBKDF2-nøkkel fra passord).
Kildekoden i HTML-en inneholder ikke lesbar helsedata.
"""

import base64
import glob
import json
import math
import os
from datetime import date, datetime, timedelta, timezone


def finn_siste_json():
    filer = sorted(glob.glob("garmin_data_*.json"), reverse=True)
    return filer[0] if filer else None


def krypter_payload(data_json: str, passord: str) -> str:
    """Krypterer JSON-streng med AES-256-GCM + PBKDF2. Returnerer base64."""
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = os.urandom(16)
    iv   = os.urandom(12)
    kdf  = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100_000)
    key  = kdf.derive(passord.encode())
    ct   = AESGCM(key).encrypt(iv, data_json.encode(), None)
    return base64.b64encode(salt + iv + ct).decode()


def formater_analyse(analyse: str) -> str:
    if not analyse:
        return "<p style='color:#64748b'>Coaching-analyse ikke tilgjengelig. Bruk knappen øverst for å hente ferske data og generere ny analyse.</p>"
    lines = []
    for line in analyse.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(line.startswith(h) for h in
               ["HAMBURG-STATUS", "DAGSFORM", "BELASTNINGSVURDERING", "MØNSTER", "RÅDATA"]):
            lines.append(f'<p class="ah">{line}</p>')
        elif line.startswith("→"):
            lines.append(f'<p class="ar">{line}</p>')
        elif any(e in line for e in ["✅", "⚠️", "🔴"]):
            lines.append(f'<p class="as">{line}</p>')
        elif line.startswith("─"):
            lines.append('<hr class="adiv">')
        else:
            lines.append(f"<p>{line}</p>")
    return "\n".join(lines)


def status_fra_analyse(analyse: str):
    if not analyse:
        return "UKJENT", "#64748b", "?"
    if "✅" in analyse:
        return "I RUTE", "#22c55e", "✅"
    elif "⚠️" in analyse:
        return "DELVIS I RUTE", "#f59e0b", "⚠️"
    elif "🔴" in analyse:
        return "IKKE I RUTE", "#ef4444", "🔴"
    return "UKJENT", "#64748b", "?"


# TSS-estimat per økttype og varighet
TSS_SNITT = {
    "Rolig":            55,   # per time
    "Maratonspesifikk": 75,
    "Terskel":          90,
    "Intervall":        85,
    "Langtur":          65,
    "Ski+Løp":          70,   # kombinert dag
    "Ski":              50,
    "Styrke":           35,
    "Hvile":             0,
    "Rase":            110,
}

def beregn_projeksjon(ctl_start: float, atl_start: float, okter: list, fra_dato: date) -> list:
    """
    Simulerer CTL/ATL/TSB dag for dag frem til Hamburg (26. april)
    basert på planlagte økter i ukeplan.json.
    Returnerer liste med {dato, ctl, atl, tsb} fra i dag+1 til race day.
    """
    CTL_K = 1 - math.exp(-1 / 42)
    ATL_K = 1 - math.exp(-1 / 7)

    # Bygg oppslag dato → TSS fra ukeplan
    tss_plan = {}
    for o in okter:
        try:
            d = date.fromisoformat(o["dato"])
        except Exception:
            continue
        if d < fra_dato:
            continue
        varighet_t = (o.get("varighet_min") or 60) / 60
        tss_per_t  = TSS_SNITT.get(o.get("type", "Rolig"), 55)
        tss_plan[d] = round(varighet_t * tss_per_t)

    race_day = date(2026, 4, 26)
    ctl  = ctl_start
    atl  = atl_start
    resultat = []

    dag = fra_dato
    while dag <= race_day:
        # På løpsdagen viser vi formen FØR løpet (ikke inkluder løpets TSS)
        tss = 0 if dag == race_day else tss_plan.get(dag, 0)
        ctl = ctl + CTL_K * (tss - ctl)
        atl = atl + ATL_K * (tss - atl)
        tsb = ctl - atl
        resultat.append({
            "dato": (dag.strftime("%m-%d")),
            "ctl":  round(ctl, 1),
            "atl":  round(atl, 1),
            "tsb":  round(tsb, 1),
        })
        dag += timedelta(days=1)

    return resultat


def main():
    json_fil = finn_siste_json()
    if not json_fil:
        print("Ingen garmin_data JSON funnet")
        return

    with open(json_fil, encoding="utf-8") as f:
        data = json.load(f)

    if os.path.exists("ukeplan.json"):
        with open("ukeplan.json", encoding="utf-8") as f:
            ukeplan = json.load(f)
    else:
        ukeplan = data.get("ukeplan", {})

    # ── Utpakk data ─────────────────────────────────────────
    dato        = data.get("dato", date.today().isoformat())
    tp          = data.get("trainingpeaks", {})
    helse       = tp.get("helsedata", {})
    fitness_d   = tp.get("fitness", {}).get("dagens", {})
    trend_90d   = tp.get("fitness", {}).get("trend_90d", [])
    helse_90d   = tp.get("helsedata_90d", [])
    strava      = data.get("strava", {})
    aktiviteter = strava.get("aktiviteter", [])
    analyse     = data.get("claude_analyse", "")
    hentet      = strava.get("hentet", "")

    oppdatert = ""
    if hentet:
        try:
            dt        = datetime.fromisoformat(hentet.replace("Z", "+00:00"))
            oppdatert = dt.strftime("%d.%m.%Y kl. %H:%M UTC")
        except Exception:
            oppdatert = hentet[:16]

    today             = date.today()
    dager_til_hamburg = (date(2026, 4, 26) - today).days
    status_txt, status_farge, status_ikon = status_fra_analyse(analyse)

    # ── Payload som krypteres ────────────────────────────────
    # Alt av helsebiometri, aktivitetsdata og treningsanalyse
    ctl_na  = round(fitness_d.get("ctl") or 0, 1)
    tsb_na  = round(fitness_d.get("tsb") or 0, 1)
    hrv_na  = helse.get("hrv", None)

    hrv14   = [(d["dato"][5:], d.get("hrv"))  for d in helse_90d[-14:] if d.get("hrv")]
    bb7     = [(d["dato"][5:], d.get("bb_maks")) for d in helse_90d[-7:] if d.get("bb_maks")]
    sovn14  = [d for d in helse_90d[-14:] if d.get("sovn_min")]

    payload = {
        "dato":      dato,
        "oppdatert": oppdatert,
        "helse": {
            "hrv":           helse.get("hrv"),
            "hvilepuls":     helse.get("hvilepuls"),
            "bb_maks":       helse.get("bb_maks"),
            "sovn_min":      helse.get("sovn_min"),
            "dyp_sovn_min":  helse.get("dyp_sovn_min"),
            "rem_sovn_min":  helse.get("rem_sovn_min"),
            "stress_snitt":  helse.get("stress_snitt"),
            "sovn_score":    helse.get("sovn_score"),
        },
        "fitness": {
            "ctl": round(fitness_d.get("ctl") or 0, 1),
            "atl": round(fitness_d.get("atl") or 0, 1),
            "tsb": round(fitness_d.get("tsb") or 0, 1),
        },
        "trend90": [
            {"dato": d.get("dato","")[5:], "ctl": d.get("ctl"), "atl": d.get("atl"), "tsb": d.get("tsb")}
            for d in trend_90d
        ],
        "projeksjon": beregn_projeksjon(
            ctl_start = round(fitness_d.get("ctl") or 0, 1),
            atl_start = round(fitness_d.get("atl") or 0, 1),
            okter     = ukeplan.get("okter", []),
            fra_dato  = today,
        ),
        "hrv14": [{"dato": d[0], "hrv": d[1]} for d in hrv14],
        "bb7":   [{"dato": d[0], "bb":  d[1]} for d in bb7],
        "sovn14": [
            {
                "dato": d["dato"][5:],
                "dyp":  d.get("dyp_sovn_min") or 0,
                "rem":  d.get("rem_sovn_min") or 0,
                "lett": max(0, (d.get("sovn_min") or 0)
                              - (d.get("dyp_sovn_min") or 0)
                              - (d.get("rem_sovn_min") or 0)),
            }
            for d in sovn14
        ],
        "aktiviteter": [
            {
                "navn":             a.get("navn"),
                "dato":             a.get("dato"),
                "dist_km":          a.get("dist_km"),
                "snitt_tempo":      a.get("snitt_tempo"),
                "snitt_puls":       a.get("snitt_puls"),
                "normalisert_watt": a.get("normalisert_watt"),
                "suffer_score":     a.get("suffer_score"),
            }
            for a in aktiviteter[:3]
        ],
        "analyse":      analyse,
        "analyse_html": formater_analyse(analyse),
        "ukeplan":      ukeplan.get("okter", []),
    }

    # Les kommentarlogg for visning i dashboardet
    okt_logg = []
    if os.path.exists("okt_logg.json"):
        with open("okt_logg.json", encoding="utf-8") as f:
            okt_logg = json.load(f)

    payload["okt_logg"] = okt_logg[-10:]  # siste 10 kommentarer
    payload["github_token"] = os.environ.get("DASHBOARD_GITHUB_TOKEN", "")

    passord    = os.environ.get("DASHBOARD_PASSWORD") or "hamburg2026"
    kryptert   = krypter_payload(json.dumps(payload, ensure_ascii=False), passord)

    # ── Status-badge og dager (ikke-sensitiv, vises ikke i dashboardet) ──
    # Disse brukes IKKE i HTML-en — alt rendres av JS etter dekryptering.
    # Vi sender bare passord-hash for validering.
    import hashlib
    pw_hash = hashlib.sha256(passord.encode()).hexdigest()

    # ── Generer HTML ─────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Treningsdashboard — Hamburg 2026</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@300;400;600;700;800&display=swap">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{
  --blue:#0075be;
  --blue-dark:#005a94;
  --blue-light:#1a9de0;
  --gold:#c9a227;
  --gold-light:#e0b93a;
  --bg:#07141f;
  --bg2:#0c1e2e;
  --bg3:#112536;
  --border:#1a3348;
  --text:#e8f2fa;
  --muted:#7a9bb5;
  --dimmed:#3d5a72;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Open Sans',sans-serif;font-size:15px;line-height:1.5}}
a{{color:var(--blue-light)}}

/* ── Gate ── */
#gate{{display:flex;align-items:center;justify-content:center;min-height:100vh;
  background:var(--bg) url('https://haspa-marathon-hamburg.de/wp-content/uploads/2024/02/HMHH_Skyline_2024_MHV.jpg') center/cover no-repeat;}}
#gate::before{{content:'';position:fixed;inset:0;background:rgba(7,20,31,0.82)}}
.gate-box{{position:relative;background:rgba(12,30,46,0.97);border:1px solid var(--border);border-top:3px solid var(--gold);border-radius:4px;padding:44px 40px;text-align:center;max-width:360px;width:90%;box-shadow:0 24px 60px rgba(0,0,0,.6)}}
.gate-logo{{width:220px;margin:0 auto 28px;display:block}}
.gate-box p{{color:var(--muted);margin-bottom:28px;font-size:0.88rem;font-weight:300;letter-spacing:.03em}}
.gate-box input{{width:100%;padding:11px 14px;border-radius:3px;border:1px solid var(--border);background:var(--bg);color:var(--text);font-size:1rem;font-family:inherit;margin-bottom:12px}}
.gate-box input:focus{{outline:none;border-color:var(--blue)}}
.gate-box button{{width:100%;padding:11px;border-radius:3px;border:none;background:var(--blue);color:#fff;font-size:0.95rem;font-weight:700;cursor:pointer;letter-spacing:.04em;text-transform:uppercase;transition:background .2s}}
.gate-box button:hover{{background:var(--blue-light)}}
.gate-box .feil{{color:#ef4444;font-size:0.83rem;margin-top:10px;min-height:1.2em}}

/* ── Header ── */
#dash{{display:none;max-width:1140px;margin:0 auto;padding:0 16px 60px}}
.site-header{{background:var(--blue);padding:10px 20px;display:flex;align-items:center;justify-content:space-between;margin:0 -16px 0;position:sticky;top:0;z-index:100;box-shadow:0 2px 12px rgba(0,0,0,.4)}}
.site-header img{{height:36px}}
.site-header-right{{font-size:0.75rem;color:rgba(255,255,255,.7);text-align:right}}
.topbar{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin:20px 0 20px;padding-bottom:16px;border-bottom:1px solid var(--border)}}
.topbar-left h1{{font-size:1.25rem;font-weight:800;letter-spacing:-.01em}}
.topbar-left p{{font-size:0.78rem;color:var(--muted);margin-top:3px}}
.badge{{display:inline-flex;align-items:center;gap:6px;padding:7px 16px;border-radius:3px;font-weight:700;font-size:0.82rem;letter-spacing:.04em;text-transform:uppercase}}

/* ── Layout ── */
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px}}
@media(max-width:640px){{.grid2,.grid3{{grid-template-columns:1fr}}}}
.kort{{background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:20px}}
.kort h3{{font-size:0.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:12px;font-weight:600}}
.stor-tall{{font-size:2.4rem;font-weight:800;line-height:1}}
.sub-tall{{font-size:0.83rem;color:var(--muted);margin-top:5px}}
.fremgang-bg{{background:var(--bg);border-radius:2px;height:8px;margin:10px 0 4px;overflow:hidden}}
.fremgang-fill{{height:100%;border-radius:2px;transition:width .6s}}
.metrikk-rad{{display:flex;justify-content:space-between;align-items:baseline;padding:7px 0;border-bottom:1px solid var(--bg)}}
.metrikk-rad:last-child{{border-bottom:none}}
.metrikk-navn{{font-size:0.83rem;color:var(--muted)}}
.metrikk-verdi{{font-weight:600;font-size:0.92rem}}
.seksjon-tittel{{font-size:0.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--blue-light);margin:28px 0 12px;padding-left:10px;border-left:3px solid var(--blue)}}

/* ── Analyse ── */
.analyse-boks{{background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:22px;margin-bottom:16px;line-height:1.75}}
.analyse-boks p{{margin-bottom:4px;font-size:0.9rem;color:#c5d8e8}}
.analyse-boks .ah{{font-weight:700;color:var(--text);margin-top:16px;font-size:0.95rem;text-transform:uppercase;letter-spacing:.04em;color:var(--blue-light)}}
.analyse-boks .ar{{color:var(--gold-light);font-weight:600}}
.analyse-boks .as{{font-size:1rem;font-weight:700;color:var(--text);margin-bottom:10px}}
.analyse-boks .adiv{{border:none;border-top:1px solid var(--border);margin:12px 0}}

/* ── Grafer ── */
.chart-boks{{background:var(--bg2);border:1px solid var(--border);border-radius:4px;padding:20px;margin-bottom:16px}}
.chart-boks h3{{font-size:0.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:16px;font-weight:600}}

/* ── Treningsplan ── */
.okt-kort{{border-radius:3px;padding:13px;margin-bottom:8px;border:1px solid var(--border);background:var(--bg2)}}

/* ── Trigger ── */
.trigger-panel{{background:var(--bg2);border:1px solid var(--border);border-top:2px solid var(--blue);border-radius:4px;padding:20px;margin-bottom:16px}}
.trigger-panel h3{{font-size:0.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px;font-weight:600}}
.trigger-panel textarea{{width:100%;background:var(--bg);border:1px solid var(--border);border-radius:3px;color:var(--text);padding:10px 12px;font-size:0.9rem;font-family:inherit;resize:vertical;min-height:72px;margin-bottom:12px}}
.trigger-panel textarea:focus{{outline:none;border-color:var(--blue)}}
.trigger-btn{{padding:10px 28px;border-radius:3px;border:none;background:var(--blue);color:#fff;font-size:0.88rem;font-weight:700;cursor:pointer;letter-spacing:.05em;text-transform:uppercase;transition:background .2s}}
.trigger-btn:hover{{background:var(--blue-light)}}
.trigger-btn:disabled{{opacity:.5;cursor:not-allowed}}
.trigger-status{{font-size:0.82rem;margin-top:10px;min-height:1.2em}}
.progress-wrap{{margin-top:14px;display:none}}
.progress-bar-bg{{background:var(--border);border-radius:4px;height:10px;overflow:hidden;margin-bottom:6px}}
.progress-bar-fill{{height:100%;background:var(--blue);border-radius:4px;width:0%;transition:width .5s ease}}
.progress-pct{{font-size:0.82rem;color:var(--muted);font-weight:600}}

/* ── Logg ── */
.logg-rad{{display:flex;gap:10px;padding:7px 0;border-bottom:1px solid var(--bg);font-size:0.82rem}}
.logg-rad:last-child{{border-bottom:none}}
.logg-dato{{color:var(--muted);white-space:nowrap;min-width:60px}}
.logg-okt{{color:var(--muted);white-space:nowrap;max-width:140px;overflow:hidden;text-overflow:ellipsis}}
.logg-txt{{color:var(--text);flex:1}}

/* ── Footer ── */
footer{{text-align:center;color:var(--dimmed);font-size:0.76rem;padding:40px 0 20px;line-height:1.9;border-top:1px solid var(--border);margin-top:20px}}
footer span{{color:var(--muted)}}
.footer-logo{{opacity:.25;height:28px;margin-bottom:16px}}
</style>
</head>
<body>

<!-- Passord-gate -->
<div id="gate">
  <div class="gate-box">
    <img class="gate-logo"
         src="https://haspa-marathon-hamburg.de/wp-content/uploads/2025/04/HMH26_Logo40years_langGold.png"
         alt="Haspa Marathon Hamburg 2026">
    <p>Øyvind Grønner · Personlig treningsdashboard</p>
    <input type="password" id="pw" placeholder="Passord"
           onkeydown="if(event.key==='Enter')loggInn()">
    <button onclick="loggInn()" id="logg-inn-knapp">Logg inn</button>
    <div class="feil" id="feil"></div>
  </div>
</div>

<!-- Dashboard — fylles av JS etter dekryptering -->
<div id="dash">
  <div class="site-header">
    <img src="https://haspa-marathon-hamburg.de/wp-content/uploads/2025/04/HMH26_Logo40years_langGold.png"
         alt="Haspa Marathon Hamburg 2026">
    <div class="site-header-right">
      Øyvind Grønner &nbsp;·&nbsp; Sub 3:00
    </div>
  </div>
  <div class="topbar">
    <div class="topbar-left">
      <h1>Hamburg Maraton 2026</h1>
      <p id="meta">Laster…</p>
    </div>
    <div class="badge" id="badge"></div>
  </div>

  <!-- Hent ferske data -->
  <div class="trigger-panel" id="trigger-panel">
    <h3>Hent ferske data og generer ny analyse</h3>
    <textarea id="okt-kommentar" placeholder="Kommentar til siste økt — f.eks. 'Følte meg tung, beina tunge etter gårsdagens terskel' (valgfritt)"></textarea>
    <div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap">
      <button class="trigger-btn" id="trigger-btn" onclick="triggerRapport()">Hent ferske data</button>
      <div class="trigger-status" id="trigger-status"></div>
    </div>
    <div class="progress-wrap" id="progress-wrap">
      <div class="progress-bar-bg"><div class="progress-bar-fill" id="progress-fill"></div></div>
      <div class="progress-pct" id="progress-pct"></div>
    </div>
  </div>

  <!-- Kommentarlogg -->
  <div id="logg-seksjon" style="display:none;margin-bottom:16px">
    <div class="seksjon-tittel" style="margin-top:0">Øktkommentarer</div>
    <div class="kort" id="logg-innhold"></div>
  </div>

  <!-- Hamburg-mål -->
  <div class="kort" id="maal-kort" style="margin-bottom:16px;border-left:4px solid var(--gold);background:linear-gradient(135deg,#0c1e2e 0%,#071420 100%)">
    <h3 id="maal-tittel">Hamburg-mål · Sub 3:00</h3>
    <div class="grid3" style="margin-top:12px;margin-bottom:0" id="maal-grid"></div>
    <div style="margin-top:12px;font-size:0.75rem;color:#475569">
      Kondisjon = treningsbase bygd opp over 42 dager &nbsp;·&nbsp;
      Tretthet = belastning siste 7 dager &nbsp;·&nbsp;
      Dagsform = kondisjon minus tretthet
    </div>
  </div>

  <!-- Dagsform + siste økt -->
  <div class="grid2">
    <div class="kort"><h3>Dagsform</h3><div id="dagsform-innhold"></div></div>
    <div class="kort"><h3>Siste økt</h3><div id="siste-okt-innhold"></div></div>
  </div>

  <!-- Coaching-analyse -->
  <div class="seksjon-tittel">Coaching-analyse</div>
  <div class="analyse-boks" id="analyse-boks"></div>

  <!-- Formkurve -->
  <div class="seksjon-tittel">Formkurve — siste 90 dager + plan frem til Hamburg</div>
  <div class="chart-boks">
    <h3>Kondisjon / Tretthet / Dagsform &nbsp;·&nbsp; Stiplet = planlagt &nbsp;·&nbsp; Mål: Kondisjon 58–65, Dagsform +12–+20 på løpsdagen</h3>
    <canvas id="ctlChart" height="130"></canvas>
  </div>

  <div class="grid2">
    <div class="chart-boks" style="margin-bottom:0">
      <h3>HRV — siste 14 dager (balansert: 70–98 ms)</h3>
      <canvas id="hrvChart" height="140"></canvas>
    </div>
    <div class="chart-boks" style="margin-bottom:0">
      <h3>Body Battery — siste 7 dager</h3>
      <canvas id="bbChart" height="140"></canvas>
    </div>
  </div>

  <div class="chart-boks" style="margin-top:16px">
    <h3>Søvn — siste 14 dager (dyp · REM · lett)</h3>
    <canvas id="sovnChart" height="100"></canvas>
  </div>

  <!-- Treningsplan -->
  <div class="seksjon-tittel">Treningsplan frem til Hamburg</div>
  <div style="font-size:0.8rem;color:#64748b;margin-bottom:12px">
    ★ = Nøkkeløkt &nbsp;·&nbsp; Gul ramme = viktig økt &nbsp;·&nbsp; Grønn bakgrunn = i dag
  </div>
  <div id="plan-innhold"></div>

  <footer>
    <img class="footer-logo"
         src="https://haspa-marathon-hamburg.de/wp-content/uploads/2025/04/HMH26_Logo40years_langGold.png"
         alt="Haspa Marathon Hamburg 2026"><br>
    <div style="margin-bottom:4px">
      <span>Data:</span> Strava · TrainingPeaks · Garmin via TrainingPeaks
    </div>
    <div style="margin-bottom:4px">
      <span>Analyse:</span> Claude claude-sonnet-4-6 (Anthropic) &nbsp;·&nbsp;
      <span>Oppdatering:</span> manuelt fra dashboardet
    </div>
    <div>
      <span>Sist oppdatert:</span> <span id="footer-dato">–</span> &nbsp;·&nbsp;
      <a href="https://github.com/oyvindgronner/garmin-morgenrapport" target="_blank">Kildekode</a>
    </div>
  </footer>
</div>

<script>
// ── Kryptert helsedata ────────────────────────────────────────────────────────
// Kryptert med AES-256-GCM, nøkkel utledet fra passord via PBKDF2 (100 000 runder).
// Lesbar i kilden uten passord: ingenting.
const ENCRYPTED = "{kryptert}";
const PW_HASH   = "{pw_hash}";  // SHA-256 for rask feilmelding

// ── Krypto-hjelp ─────────────────────────────────────────────────────────────
async function sha256hex(msg) {{
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(msg));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,"0")).join("");
}}

async function deriverNøkkel(passord, salt) {{
  const mat = await crypto.subtle.importKey(
    "raw", new TextEncoder().encode(passord), "PBKDF2", false, ["deriveKey"]
  );
  return crypto.subtle.deriveKey(
    {{name:"PBKDF2", salt, iterations:100_000, hash:"SHA-256"}},
    mat,
    {{name:"AES-GCM", length:256}},
    false, ["decrypt"]
  );
}}

async function dekrypter(b64, passord) {{
  const raw  = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
  const salt = raw.slice(0, 16);
  const iv   = raw.slice(16, 28);
  const ct   = raw.slice(28);
  const key  = await deriverNøkkel(passord, salt);
  const dec  = await crypto.subtle.decrypt({{name:"AES-GCM", iv}}, key, ct);
  return JSON.parse(new TextDecoder().decode(dec));
}}

// ── Innlogging ────────────────────────────────────────────────────────────────
async function loggInn() {{
  const pw   = document.getElementById("pw").value;
  const knapp = document.getElementById("logg-inn-knapp");
  if (!pw) return;

  // Rask feilmelding via SHA-256 (unngår å vente på PBKDF2 ved feil passord)
  const hash = await sha256hex(pw);
  if (hash !== PW_HASH) {{
    document.getElementById("feil").textContent = "Feil passord";
    return;
  }}

  knapp.textContent = "Dekrypterer…";
  knapp.disabled = true;
  document.getElementById("feil").textContent = "";
  try {{
    const data = await dekrypter(ENCRYPTED, pw);
    localStorage.setItem("db_pw", pw);
    visDashboard(data);
  }} catch(e) {{
    document.getElementById("feil").textContent = "Dekryptering feilet";
    knapp.textContent = "Logg inn";
    knapp.disabled = false;
  }}
}}

// ── Automatisk innlogging fra localStorage ────────────────────────────────────
(async function() {{
  const lagret = localStorage.getItem("db_pw");
  if (!lagret) return;
  try {{
    const data = await dekrypter(ENCRYPTED, lagret);
    visDashboard(data);
  }} catch(e) {{
    localStorage.removeItem("db_pw");
  }}
}})();

// ── Lagret dekryptert data (for trigger-funksjon) ────────────────────────────
let _dekryptertData = null;

// ── Trigger workflow ──────────────────────────────────────────────────────────
const REPO = "oyvindgronner/garmin-morgenrapport";
const WORKFLOW = "morgenrapport.yml";

function ghFetch(token, path) {{
  return fetch(`https://api.github.com/repos/${{REPO}}/${{path}}`, {{
    headers: {{ "Authorization": `token ${{token}}`, "Accept": "application/vnd.github.v3+json" }}
  }}).then(r => r.json());
}}

async function triggerRapport() {{
  const token     = _dekryptertData?.github_token;
  const kommentar = document.getElementById("okt-kommentar")?.value?.trim() || "";
  const btn       = document.getElementById("trigger-btn");
  const statusEl  = document.getElementById("trigger-status");
  const wrapEl    = document.getElementById("progress-wrap");
  const fillEl    = document.getElementById("progress-fill");
  const pctEl     = document.getElementById("progress-pct");

  if (!token) {{
    statusEl.textContent = "Ingen GitHub-token konfigurert (DASHBOARD_GITHUB_TOKEN mangler).";
    statusEl.style.color = "#ef4444";
    return;
  }}

  btn.disabled = true;
  statusEl.style.color = "#94a3b8";
  statusEl.textContent = "Sender forespørsel…";

  // 1. Dispatch
  const dispResp = await fetch(
    `https://api.github.com/repos/${{REPO}}/actions/workflows/${{WORKFLOW}}/dispatches`,
    {{
      method: "POST",
      headers: {{
        "Authorization": `token ${{token}}`,
        "Accept": "application/vnd.github.v3+json",
        "Content-Type": "application/json",
      }},
      body: JSON.stringify({{ ref: "main", inputs: {{ okt_kommentar: kommentar }} }})
    }}
  );

  if (dispResp.status !== 204) {{
    const txt = await dispResp.text();
    statusEl.textContent = `Feil ${{dispResp.status}}: ${{txt}}`;
    statusEl.style.color = "#ef4444";
    btn.disabled = false;
    return;
  }}

  statusEl.textContent = "Workflow startet…";
  wrapEl.style.display = "block";
  setProgress(fillEl, pctEl, 0, "#0075be");

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // 2. Finn run-ID (venter til den dukker opp, maks 30s)
  await sleep(4000);
  let runId = null;
  const dispatchedAt = Date.now();
  while (!runId) {{
    if (Date.now() - dispatchedAt > 30000) {{
      statusEl.textContent = "Fant ikke kjøring — last inn siden manuelt om noen minutter.";
      return;
    }}
    const data = await ghFetch(token, `actions/workflows/${{WORKFLOW}}/runs?per_page=5`);
    const run = data.workflow_runs?.find(r => r.status === "in_progress" || r.status === "queued");
    if (run) runId = run.id;
    else await sleep(3000);
  }}

  // 3. Poll steg-fremdrift
  while (true) {{
    const data = await ghFetch(token, `actions/runs/${{runId}}/jobs`);
    const job  = data.jobs?.[0];
    if (!job) {{ await sleep(4000); continue; }}

    const steps = job.steps || [];
    const total = steps.length;
    const done  = steps.filter(s => s.status === "completed").length;
    const pct   = total > 0 ? Math.round(done / total * 100) : 0;
    setProgress(fillEl, pctEl, pct, "#0075be");

    if (job.status === "completed") {{
      if (job.conclusion === "success") {{
        setProgress(fillEl, pctEl, 100, "#22c55e");
        pctEl.textContent = "Ferdig — laster inn nytt dashboard…";
        statusEl.textContent = "";
        await sleep(2000);
        window.location.reload();
      }} else {{
        setProgress(fillEl, pctEl, pct, "#ef4444");
        statusEl.textContent = `Workflow feilet (${{job.conclusion}}).`;
        statusEl.style.color = "#ef4444";
        btn.disabled = false;
      }}
      return;
    }}

    await sleep(4000);
  }}
}}

function setProgress(fillEl, pctEl, pct, color) {{
  fillEl.style.width   = pct + "%";
  fillEl.style.background = color;
  pctEl.textContent    = pct + "%";
}}

// ── Dashboard-rendering ───────────────────────────────────────────────────────
const TYPE_FARGER = {{
  "Rolig":"#22c55e","Terskel":"#f97316","Intervall":"#ef4444",
  "Langtur":"#3b82f6","Maratonspesifikk":"#8b5cf6","Ski+Løp":"#06b6d4",
  "Ski":"#94a3b8","Styrke":"#ec4899","Rase":"#fbbf24","Hvile":"#475569"
}};

function metrikk(navn, verdi, farge) {{
  const fargestyle = farge ? `color:${{farge}}` : "";
  return `<div class="metrikk-rad">
    <span class="metrikk-navn">${{navn}}</span>
    <span class="metrikk-verdi" style="${{fargestyle}}">${{verdi ?? "–"}}</span>
  </div>`;
}}

function fargeCTL(v)  {{ return v >= 58 ? "#22c55e" : v >= 52 ? "#f59e0b" : "#ef4444"; }}
function fargeTSB(v)  {{ return v >= 5 && v <= 25 ? "#22c55e" : v >= -10 ? "#f59e0b" : "#ef4444"; }}
function fargeHRV(v)  {{ return v >= 70 && v <= 98 ? "#22c55e" : v >= 60 ? "#f59e0b" : "#ef4444"; }}
function fargeBB(v)   {{ return v >= 70 ? "#22c55e" : v >= 50 ? "#f59e0b" : "#ef4444"; }}

function statusFraAnalyse(a) {{
  if (!a) return ["UKJENT","#64748b","?"];
  if (a.includes("✅")) return ["I RUTE","#22c55e","✅"];
  if (a.includes("⚠️")) return ["DELVIS I RUTE","#f59e0b","⚠️"];
  if (a.includes("🔴")) return ["IKKE I RUTE","#ef4444","🔴"];
  return ["UKJENT","#64748b","?"];
}}

function visDashboard(d) {{
  _dekryptertData = d;
  document.getElementById("gate").style.display = "none";
  document.getElementById("dash").style.display = "block";

  const today   = new Date().toISOString().slice(0,10);
  const helse   = d.helse || {{}};
  const fitness = d.fitness || {{}};
  const ctl = fitness.ctl || 0;
  const atl = fitness.atl || 0;
  const tsb = fitness.tsb || 0;
  const hrv = helse.hrv;

  // Topbar
  document.getElementById("meta").textContent =
    `Øyvind Grønner · Rapport ${{d.dato}} · Oppdatert ${{d.oppdatert || "–"}}`;
  document.getElementById("footer-dato").textContent = d.oppdatert || "–";

  const [stxt, sfarge, sikon] = statusFraAnalyse(d.analyse);
  const badge = document.getElementById("badge");
  badge.textContent = `${{sikon}} ${{stxt}}`;
  badge.style.cssText = `background:${{sfarge}}22;color:${{sfarge}};border:1px solid ${{sfarge}}44`;

  // Hamburg-mål
  const raceDay = new Date("2026-04-26");
  const dager   = Math.round((raceDay - new Date()) / 86400000);
  document.getElementById("maal-tittel").textContent =
    `Hamburg-mål · ${{dager}} dager igjen · Sub 3:00`;

  const ctlPct = Math.min(100, Math.round((ctl / 58) * 100));
  const tsbPct = Math.min(100, Math.max(0, Math.round(((tsb + 30) / 50) * 100)));
  document.getElementById("maal-grid").innerHTML = `
    <div>
      <div style="font-size:.8rem;color:#94a3b8">Kondisjon (CTL)</div>
      <div class="stor-tall" style="color:${{fargeCTL(ctl)}}">${{ctl}}</div>
      <div class="sub-tall">Mål: 58–65</div>
      <div class="fremgang-bg"><div class="fremgang-fill" style="width:${{ctlPct}}%;background:${{fargeCTL(ctl)}}"></div></div>
      <div style="font-size:.75rem;color:#64748b">${{ctl >= 58 ? "✅ I mål" : `⚠️ ${{(58-ctl).toFixed(1)}} bak min.mål`}}</div>
    </div>
    <div>
      <div style="font-size:.8rem;color:#94a3b8">Dagsform (TSB)</div>
      <div class="stor-tall" style="color:${{fargeTSB(tsb)}}">${{tsb >= 0 ? "+" : ""}}${{tsb.toFixed(1)}}</div>
      <div class="sub-tall">Race-mål: +12 til +20</div>
      <div class="fremgang-bg"><div class="fremgang-fill" style="width:${{tsbPct}}%;background:#3b82f6"></div></div>
      <div style="font-size:.75rem;color:#64748b">${{tsb >= 5 ? "✅ Frisk og klar" : tsb >= -10 ? "⚠️ Noe akkumulert" : "🔴 Trøtt"}}</div>
    </div>
    <div>
      <div style="font-size:.8rem;color:#94a3b8">HRV</div>
      <div class="stor-tall" style="color:${{fargeHRV(hrv || 0)}}">${{hrv ?? "–"}}</div>
      <div class="sub-tall">Balansert: 70–98 ms</div>
    </div>`;

  // Dagsform
  const sovnMin = helse.sovn_min;
  const sovnStr = sovnMin ? `${{Math.floor(sovnMin/60)}}t ${{sovnMin%60}}min` : "–";

  // Garmin søvnscore (hentes direkte fra API — Garmin sin egen algoritme)
  // Fallback: beregn fra varighet + dyp + REM hvis scoren mangler
  let sovnscore = helse.sovn_score ?? null;
  if (sovnscore === null && sovnMin) {{
    const v = Math.min(40, Math.max(0, (sovnMin - 300) / 180 * 40));
    const dp = helse.dyp_sovn_min ? Math.min(30, (helse.dyp_sovn_min / sovnMin * 100) / 20 * 30) : 0;
    const rm = helse.rem_sovn_min ? Math.min(30, (helse.rem_sovn_min / sovnMin * 100) / 25 * 30) : 0;
    sovnscore = Math.min(100, Math.round(v + dp + rm + 10));
  }}
  const sovnscoreFarge = sovnscore >= 75 ? "#22c55e" : sovnscore >= 55 ? "#f59e0b" : "#ef4444";
  const sovnscoreLabel = sovnscore >= 80 ? "Utmerket" : sovnscore >= 65 ? "God" : sovnscore >= 50 ? "Ok" : "Dårlig";
  const sovnscoreKilde = helse.sovn_score != null ? "" : " (beregnet)";

  // HRV-status fra Garmin (BALANCED / UNBALANCED / LOW osv.)
  const hrvStatusMap = {{
    "BALANCED":   ["Balansert", "#22c55e"],
    "UNBALANCED": ["Ubalansert", "#f59e0b"],
    "LOW":        ["Lav", "#ef4444"],
    "POOR":       ["Svak", "#ef4444"],
  }};
  const [hrvStatusTxt, hrvStatusFarge] = hrvStatusMap[helse.hrv_status] || [null, null];
  const hrvStr = hrv
    ? `${{hrv}} ms${{hrvStatusTxt ? ` — ${{hrvStatusTxt}}` : ""}}`
    : "–";

  document.getElementById("dagsform-innhold").innerHTML =
    metrikk("HRV",          hrvStr, hrvStatusFarge || fargeHRV(hrv||0))
  + (helse.hrv_baseline
      ? metrikk("HRV baseline", helse.hrv_baseline)
      : "")
  + metrikk("Hvilepuls",    helse.hvilepuls ? `${{helse.hvilepuls}} bpm` : "–")
  + metrikk("Body Battery", helse.bb_maks ? `${{helse.bb_maks}}/100` : "–",  fargeBB(helse.bb_maks||0))
  + metrikk("Søvnscore",    sovnscore !== null ? `${{sovnscore}}/100 — ${{sovnscoreLabel}}${{sovnscoreKilde}}` : "–", sovnscoreFarge)
  + metrikk("Søvn totalt",  sovnStr)
  + metrikk("Dyp søvn",     helse.dyp_sovn_min ? `${{helse.dyp_sovn_min}} min` : "–")
  + metrikk("REM",          helse.rem_sovn_min ? `${{helse.rem_sovn_min}} min` : "–")
  + (helse.respirasjonsfrekvens
      ? metrikk("Respirasjonsfrekvens", `${{helse.respirasjonsfrekvens}} ånd/min`)
      : "")
  + metrikk("Stress",       helse.stress_snitt ?? "–");

  // Siste økt
  const siste = (d.aktiviteter || [])[0] || {{}};
  document.getElementById("siste-okt-innhold").innerHTML = siste.navn
    ? metrikk("Navn",    `<span style="font-size:.85rem">${{siste.navn}}</span>`)
    + metrikk("Dato",    siste.dato)
    + metrikk("Distanse",siste.dist_km ? `${{siste.dist_km}} km` : "–")
    + metrikk("Tempo",   siste.snitt_tempo)
    + metrikk("Puls",    siste.snitt_puls ? `${{siste.snitt_puls}} bpm` : "–")
    + metrikk("NP",      siste.normalisert_watt ? `${{siste.normalisert_watt}} W` : "–")
    + metrikk("Suffer",  siste.suffer_score ?? "–")
    : "<p style='color:#64748b'>Ingen økt registrert</p>";

  // Analyse
  document.getElementById("analyse-boks").innerHTML =
    (d.analyse_html || "<p>Ingen analyse tilgjengelig.</p>")
    + `<p style="margin-top:16px;font-size:.75rem;color:#475569">Analyse: Claude claude-sonnet-4-6 (Anthropic) · ${{d.dato}} · Data: Strava + TrainingPeaks</p>`;

  // Treningsplan
  const okter   = d.ukeplan || [];
  const kommende = okter.filter(o => o.dato >= today).slice(0, 21);
  document.getElementById("plan-innhold").innerHTML = kommende.map(o => {{
    const erIDag  = o.dato === today;
    const erNokkel = o.dato === "2026-04-12" || o.type === "Rase"
                     || (o.beskrivelse || "").includes("28 km");
    const farge   = TYPE_FARGER[o.type] || "#64748b";
    const bg      = erIDag ? "background:#1e3a2f;" : "background:#1e293b;";
    const border  = erNokkel ? "border:2px solid #fbbf24;" : "border:1px solid #334155;";
    const dagNavn = new Date(o.dato + "T12:00:00")
                    .toLocaleDateString("no-NO", {{weekday:"short",day:"2-digit",month:"2-digit"}});
    const info    = [o.dist_km ? `${{o.dist_km}} km` : null, o.varighet_min ? `${{o.varighet_min}} min` : null]
                    .filter(Boolean).join("  ·  ");
    const notat   = (o.beskrivelse || "").length > 120
                    ? o.beskrivelse.slice(0, 120) + "…" : o.beskrivelse;
    return `<div class="okt-kort" style="${{bg}}${{border}}">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px">
        <span style="font-size:.75rem;color:#94a3b8">${{dagNavn}}${{erIDag ? "  ← I DAG" : ""}}${{erNokkel && o.type !== "Rase" ? "  ★ NØKKEL" : ""}}</span>
        <span style="font-size:.75rem;font-weight:600;color:${{farge}}">${{o.type || ""}}</span>
      </div>
      <div style="font-size:.85rem;color:#e2e8f0;margin-bottom:4px">${{notat}}</div>
      <div style="font-size:.75rem;color:#64748b">${{info}}</div>
    </div>`;
  }}).join("");

  // ── Grafer ────────────────────────────────────────────────
  const DEFAULTS = {{
    responsive: true,
    plugins: {{ legend: {{ labels: {{ color:"#7a9bb5", boxWidth:14, font:{{family:"Open Sans"}} }} }} }},
    scales: {{
      x: {{ ticks:{{ color:"#3d5a72", maxTicksLimit:12 }}, grid:{{ color:"#0c1e2e" }} }},
      y: {{ ticks:{{ color:"#3d5a72" }},                   grid:{{ color:"#0c1e2e" }} }}
    }}
  }};

  // Kondisjon/Tretthet/Dagsform (CTL/ATL/TSB) + prosjeksjon
  {{
    // Historikk-labels + prosjeksjon-labels i én felles akse
    const histLbl = d.trend90.map(x => x.dato);
    const projLbl = (d.projeksjon || []).map(x => x.dato);

    // Null-padding: historikk-serier er tomme der prosjeksjonen starter, og omvendt
    const histLen = histLbl.length;
    const projLen = projLbl.length;
    const allLbl  = [...histLbl, ...projLbl];

    const pad = (arr, before, after) =>
      [...Array(before).fill(null), ...arr, ...Array(after).fill(null)];

    const histCTL = d.trend90.map(x => x.ctl);
    const histATL = d.trend90.map(x => x.atl);
    const histTSB = d.trend90.map(x => x.tsb);
    const projCTL = (d.projeksjon || []).map(x => x.ctl);
    const projATL = (d.projeksjon || []).map(x => x.atl);
    const projTSB = (d.projeksjon || []).map(x => x.tsb);

    // Siste historikk-punkt kobles til første proj-punkt (ingen gap i linjen)
    const bridge = 1;

    new Chart(document.getElementById("ctlChart"), {{
      type: "line",
      data: {{
        labels: allLbl,
        datasets: [
          // ── Historikk (heltrukket) ──
          {{
            label: "Kondisjon",
            data: [...histCTL, projCTL[0] ?? null, ...Array(projLen - bridge).fill(null)],
            borderColor: "#0075be", backgroundColor: "transparent",
            borderWidth: 2.5, pointRadius: 0, tension: 0.3
          }},
          {{
            label: "Tretthet",
            data: [...histATL, projATL[0] ?? null, ...Array(projLen - bridge).fill(null)],
            borderColor: "#c9a227", backgroundColor: "transparent",
            borderWidth: 2.5, pointRadius: 0, tension: 0.3
          }},
          {{
            label: "Dagsform",
            data: [...histTSB, projTSB[0] ?? null, ...Array(projLen - bridge).fill(null)],
            borderColor: "#22c55e", backgroundColor: "#22c55e0d",
            borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: true
          }},
          // ── Prosjeksjon (stiplet) ──
          {{
            label: "Kondisjon (plan)",
            data: [...Array(histLen).fill(null), ...projCTL],
            borderColor: "#0075be", backgroundColor: "transparent",
            borderWidth: 2, borderDash: [6, 4], pointRadius: 0, tension: 0.3
          }},
          {{
            label: "Tretthet (plan)",
            data: [...Array(histLen).fill(null), ...projATL],
            borderColor: "#c9a227", backgroundColor: "transparent",
            borderWidth: 2, borderDash: [6, 4], pointRadius: 0, tension: 0.3
          }},
          {{
            label: "Dagsform (plan)",
            data: [...Array(histLen).fill(null), ...projTSB],
            borderColor: "#22c55e", backgroundColor: "transparent",
            borderWidth: 1.5, borderDash: [6, 4], pointRadius: 0, tension: 0.3
          }},
        ]
      }},
      options: {{
        ...DEFAULTS,
        plugins: {{
          ...DEFAULTS.plugins,
          legend: {{
            labels: {{
              color: "#94a3b8", boxWidth: 14,
              // Vis bare de 3 historikk-seriene i legenden
              filter: item => !item.text.includes("(plan)")
            }}
          }},
          tooltip: {{
            callbacks: {{
              title: ctx => ctx[0].label,
              label: ctx => `${{ctx.dataset.label}}: ${{ctx.parsed.y?.toFixed(1) ?? "–"}}`
            }}
          }}
        }},
        scales: {{
          x: {{ ...DEFAULTS.scales.x, ticks: {{ color: "#64748b", maxTicksLimit: 14 }} }},
          y: {{ ...DEFAULTS.scales.y, suggestedMin: -30, suggestedMax: 80 }}
        }}
      }}
    }});
  }}

  // HRV
  const hrvVals = d.hrv14.map(x => x.hrv);
  new Chart(document.getElementById("hrvChart"), {{
    type: "line",
    data: {{
      labels: d.hrv14.map(x => x.dato),
      datasets: [{{
        label: "HRV (ms)", data: hrvVals,
        borderColor:"#a78bfa", backgroundColor:"#a78bfa22",
        borderWidth:2, tension:0.3, fill:true,
        pointRadius:4,
        pointBackgroundColor: hrvVals.map(v => v>=70&&v<=98?"#22c55e":v>=60?"#f59e0b":"#ef4444")
      }}]
    }},
    options: {{...DEFAULTS, scales:{{x:DEFAULTS.scales.x, y:{{...DEFAULTS.scales.y, suggestedMin:40, suggestedMax:110}}}}}}
  }});

  // Body Battery
  const bbVals = d.bb7.map(x => x.bb);
  new Chart(document.getElementById("bbChart"), {{
    type: "bar",
    data: {{
      labels: d.bb7.map(x => x.dato),
      datasets: [{{
        label:"Body Battery", data:bbVals, borderRadius:4,
        backgroundColor: bbVals.map(v => v>=70?"#22c55e88":v>=50?"#f59e0b88":"#ef444488"),
        borderColor:      bbVals.map(v => v>=70?"#22c55e":v>=50?"#f59e0b":"#ef4444"),
        borderWidth:1
      }}]
    }},
    options: {{...DEFAULTS, scales:{{x:DEFAULTS.scales.x, y:{{...DEFAULTS.scales.y, min:0, max:100}}}}}}
  }});

  // Kommentarlogg
  const logg = d.okt_logg || [];
  if (logg.length > 0) {{
    document.getElementById("logg-seksjon").style.display = "block";
    document.getElementById("logg-innhold").innerHTML = [...logg].reverse().map(p => `
      <div class="logg-rad">
        <span class="logg-dato">${{p.dato ? p.dato.slice(5) : "–"}}</span>
        <span class="logg-okt">${{p.okt_navn || ""}}</span>
        <span class="logg-txt">${{p.kommentar}}</span>
      </div>`).join("");
  }}

  // Trigger-panel: skjul hvis ingen token
  if (!d.github_token) {{
    document.getElementById("trigger-panel").innerHTML =
      `<p style="font-size:.85rem;color:#64748b">Oppdatering trigges via GitHub Actions workflow_dispatch (DASHBOARD_GITHUB_TOKEN ikke konfigurert).</p>`;
  }}

  // Søvn
  new Chart(document.getElementById("sovnChart"), {{
    type: "bar",
    data: {{
      labels: d.sovn14.map(x => x.dato),
      datasets: [
        {{label:"Dyp",  data:d.sovn14.map(x=>x.dyp),  backgroundColor:"#1d4ed8aa", borderRadius:3}},
        {{label:"REM",  data:d.sovn14.map(x=>x.rem),  backgroundColor:"#7c3aedaa", borderRadius:3}},
        {{label:"Lett", data:d.sovn14.map(x=>x.lett), backgroundColor:"#334155",   borderRadius:3}},
      ]
    }},
    options: {{
      ...DEFAULTS,
      scales: {{
        x: DEFAULTS.scales.x,
        y: {{...DEFAULTS.scales.y, stacked:true, title:{{display:true, text:"min", color:"#64748b"}}}},
      }},
      plugins: DEFAULTS.plugins
    }}
  }});
}}
</script>
</body>
</html>"""

    os.makedirs("docs", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Dashboard generert: docs/index.html ({len(html)//1024} KB)")


if __name__ == "__main__":
    main()
