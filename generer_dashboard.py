#!/usr/bin/env python3
"""
generer_dashboard.py
====================
Genererer docs/index.html fra dagens garmin_data JSON og ukeplan.json.
"""

import glob
import hashlib
import json
import os
from datetime import date, datetime, timezone


def finn_siste_json():
    filer = sorted(glob.glob("garmin_data_*.json"), reverse=True)
    return filer[0] if filer else None


def status_fra_analyse(analyse):
    if not analyse:
        return "UKJENT", "#64748b", "?"
    if "✅" in analyse:
        return "I RUTE", "#22c55e", "✅"
    elif "⚠️" in analyse:
        return "DELVIS I RUTE", "#f59e0b", "⚠️"
    elif "🔴" in analyse:
        return "IKKE I RUTE", "#ef4444", "🔴"
    return "UKJENT", "#64748b", "?"


def formater_analyse(analyse):
    if not analyse:
        return "<p>Ingen analyse tilgjengelig.</p>"
    lines = []
    for line in analyse.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(line.startswith(h) for h in ["HAMBURG-STATUS", "DAGSFORM", "BELASTNINGSVURDERING", "MØNSTER", "RÅDATA"]):
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

    race_day          = date(2026, 4, 26)
    today             = date.today()
    dager_til_hamburg = (race_day - today).days

    status_txt, status_farge, status_ikon = status_fra_analyse(analyse)

    ctl_na   = round(fitness_d.get("ctl") or 0, 1)
    atl_na   = round(fitness_d.get("atl") or 0, 1)
    tsb_na   = round(fitness_d.get("tsb") or 0, 1)
    hrv_na   = helse.get("hrv", "–")
    hvile_na = helse.get("hvilepuls", "–")
    bb_na    = helse.get("bb_maks", "–")
    sovn_na  = helse.get("sovn_min")
    sovn_str = f"{sovn_na // 60}t {sovn_na % 60}min" if sovn_na else "–"

    ctl_gap     = round(58 - ctl_na, 1)
    ctl_pct     = min(100, round((ctl_na / 58) * 100))
    tsb_pct     = min(100, max(0, round(((tsb_na + 30) / 50) * 100)))  # -30..+20 → 0..100%

    oppdatert = ""
    if hentet:
        try:
            dt = datetime.fromisoformat(hentet.replace("Z", "+00:00"))
            oppdatert = dt.strftime("%d.%m.%Y kl. %H:%M UTC")
        except Exception:
            oppdatert = hentet[:16]

    siste = aktiviteter[0] if aktiviteter else {}

    type_farger = {
        "Rolig":           "#22c55e",
        "Terskel":         "#f97316",
        "Intervall":       "#ef4444",
        "Langtur":         "#3b82f6",
        "Maratonspesifikk":"#8b5cf6",
        "Ski+Løp":         "#06b6d4",
        "Ski":             "#94a3b8",
        "Styrke":          "#ec4899",
        "Rase":            "#fbbf24",
        "Hvile":           "#475569",
    }

    okter     = ukeplan.get("okter", [])
    dag_okt   = next((o for o in okter if o["dato"] == dato), None)
    kommende  = [o for o in okter if o["dato"] >= dato][:21]

    def okt_html(o):
        er_i_dag  = o["dato"] == dato
        er_nokkel = "28 km" in o.get("beskrivelse", "") or o["dato"] == "2026-04-12" or o.get("type") == "Rase"
        farge     = type_farger.get(o.get("type", ""), "#64748b")
        dist      = f"{o['dist_km']} km" if o.get("dist_km") else ""
        varighet  = f"{o['varighet_min']} min" if o.get("varighet_min") else ""
        border    = "border: 2px solid #fbbf24;" if er_nokkel else ""
        bg        = "background:#1e3a2f;" if er_i_dag else "background:#1e293b;"
        dag_navn  = datetime.strptime(o["dato"], "%Y-%m-%d").strftime("%a %d.%m")
        return f"""
        <div class="okt-kort" style="{bg}{border}">
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
            <span style="font-size:0.75rem;color:#94a3b8">{dag_navn}{"  ← I DAG" if er_i_dag else ""}{"  ★ NØKKEL" if er_nokkel and o.get("type") != "Rase" else ""}</span>
            <span style="font-size:0.75rem;font-weight:600;color:{farge}">{o.get("type","")}</span>
          </div>
          <div style="font-size:0.85rem;color:#e2e8f0;margin-bottom:4px">{o.get("beskrivelse","")[:120]}{"…" if len(o.get("beskrivelse","")) > 120 else ""}</div>
          <div style="font-size:0.75rem;color:#64748b">{dist}{"  ·  " if dist and varighet else ""}{varighet}</div>
        </div>"""

    plan_html = "\n".join(okt_html(o) for o in kommende)

    # Chart.js data as JSON
    ctl_js   = json.dumps([d.get("ctl")       for d in trend_90d])
    atl_js   = json.dumps([d.get("atl")       for d in trend_90d])
    tsb_js   = json.dumps([d.get("tsb")       for d in trend_90d])
    dato_js  = json.dumps([d.get("dato","")[5:] for d in trend_90d])

    hrv_data  = [(d["dato"][5:], d.get("hrv")) for d in helse_90d[-14:] if d.get("hrv")]
    hrv_lbl   = json.dumps([x[0] for x in hrv_data])
    hrv_vals  = json.dumps([x[1] for x in hrv_data])

    sovn_data  = [d for d in helse_90d[-14:] if d.get("sovn_min")]
    sovn_lbl   = json.dumps([d["dato"][5:]                                                              for d in sovn_data])
    sovn_dyp   = json.dumps([d.get("dyp_sovn_min") or 0                                                for d in sovn_data])
    sovn_rem   = json.dumps([d.get("rem_sovn_min") or 0                                                for d in sovn_data])
    sovn_lett  = json.dumps([max(0,(d.get("sovn_min") or 0)-(d.get("dyp_sovn_min") or 0)-(d.get("rem_sovn_min") or 0)) for d in sovn_data])

    bb_data   = [(d["dato"][5:], d.get("bb_maks")) for d in helse_90d[-7:] if d.get("bb_maks")]
    bb_lbl    = json.dumps([x[0] for x in bb_data])
    bb_vals   = json.dumps([x[1] for x in bb_data])

    # Password hash (default: "hamburg2026", override via DASHBOARD_PASSWORD env var)
    passord   = os.environ.get("DASHBOARD_PASSWORD", "hamburg2026")
    pw_hash   = hashlib.sha256(passord.encode()).hexdigest()

    analyse_html = formater_analyse(analyse)

    html = f"""<!DOCTYPE html>
<html lang="no">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Treningsdashboard — Hamburg 2026</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:15px;line-height:1.5}}
a{{color:#60a5fa}}
#gate{{display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0f172a}}
.gate-box{{background:#1e293b;border-radius:16px;padding:40px;text-align:center;max-width:340px;width:90%}}
.gate-box h2{{margin-bottom:8px;font-size:1.3rem}}
.gate-box p{{color:#94a3b8;margin-bottom:24px;font-size:0.9rem}}
.gate-box input{{width:100%;padding:10px 14px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;font-size:1rem;margin-bottom:12px}}
.gate-box button{{width:100%;padding:10px;border-radius:8px;border:none;background:#3b82f6;color:#fff;font-size:1rem;font-weight:600;cursor:pointer}}
.gate-box .feil{{color:#ef4444;font-size:0.85rem;margin-top:8px}}
#dash{{display:none;max-width:1100px;margin:0 auto;padding:20px 16px 60px}}
.topbar{{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:24px;padding-bottom:16px;border-bottom:1px solid #1e293b}}
.topbar-left h1{{font-size:1.2rem;font-weight:700}}
.topbar-left p{{font-size:0.8rem;color:#64748b;margin-top:2px}}
.badge{{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:999px;font-weight:700;font-size:0.85rem}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;margin-bottom:16px}}
@media(max-width:640px){{.grid2,.grid3{{grid-template-columns:1fr}}}}
.kort{{background:#1e293b;border-radius:12px;padding:20px}}
.kort h3{{font-size:0.8rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:12px}}
.stor-tall{{font-size:2.2rem;font-weight:700;line-height:1}}
.sub-tall{{font-size:0.85rem;color:#94a3b8;margin-top:4px}}
.fremgang-bg{{background:#0f172a;border-radius:999px;height:10px;margin:10px 0 4px;overflow:hidden}}
.fremgang-fill{{height:100%;border-radius:999px;transition:width .5s}}
.metrikk-rad{{display:flex;justify-content:space-between;align-items:baseline;padding:6px 0;border-bottom:1px solid #0f172a}}
.metrikk-rad:last-child{{border-bottom:none}}
.metrikk-navn{{font-size:0.85rem;color:#94a3b8}}
.metrikk-verdi{{font-weight:600}}
.seksjon-tittel{{font-size:1rem;font-weight:700;margin:28px 0 14px;color:#e2e8f0}}
.analyse-boks{{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px;line-height:1.7}}
.analyse-boks p{{margin-bottom:4px;font-size:0.9rem;color:#cbd5e1}}
.analyse-boks .ah{{font-weight:700;color:#e2e8f0;margin-top:14px;font-size:0.95rem}}
.analyse-boks .ar{{color:#fbbf24;font-weight:600}}
.analyse-boks .as{{font-size:1rem;font-weight:700;color:#e2e8f0;margin-bottom:8px}}
.analyse-boks .adiv{{border:none;border-top:1px solid #334155;margin:10px 0}}
.chart-boks{{background:#1e293b;border-radius:12px;padding:20px;margin-bottom:16px}}
.chart-boks h3{{font-size:0.8rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:16px}}
.okt-kort{{border-radius:10px;padding:12px;margin-bottom:8px;border:1px solid #334155}}
.akt-tabell{{width:100%;border-collapse:collapse;font-size:0.85rem}}
.akt-tabell th{{text-align:left;color:#64748b;font-weight:500;padding:4px 8px 8px;border-bottom:1px solid #334155}}
.akt-tabell td{{padding:8px;border-bottom:1px solid #1a2535}}
footer{{text-align:center;color:#475569;font-size:0.78rem;padding:40px 0 20px;line-height:1.8}}
footer span{{color:#64748b}}
</style>
</head>
<body>

<div id="gate">
  <div class="gate-box">
    <h2>🏃 Treningsdashboard</h2>
    <p>Hamburg Maraton 2026 — Øyvind Grønner</p>
    <input type="password" id="pw" placeholder="Passord" onkeydown="if(event.key==='Enter')sjekkPw()">
    <button onclick="sjekkPw()">Logg inn</button>
    <div class="feil" id="feil"></div>
  </div>
</div>

<div id="dash">

  <div class="topbar">
    <div class="topbar-left">
      <h1>Hamburg Maraton 2026</h1>
      <p>Øyvind Grønner · Rapport {dato} · Oppdatert {oppdatert}</p>
    </div>
    <div class="badge" style="background:{status_farge}22;color:{status_farge};border:1px solid {status_farge}44">
      {status_ikon} {status_txt}
    </div>
  </div>

  <!-- Hamburg-mål -->
  <div class="kort" style="margin-bottom:16px;border-left:4px solid #fbbf24">
    <h3>Hamburg-mål · {dager_til_hamburg} dager igjen · Sub 3:00</h3>
    <div class="grid3" style="margin-top:12px;margin-bottom:0">
      <div>
        <div style="font-size:0.8rem;color:#94a3b8">CTL nå</div>
        <div class="stor-tall" style="color:{'#22c55e' if ctl_na >= 58 else '#f59e0b' if ctl_na >= 52 else '#ef4444'}">{ctl_na}</div>
        <div class="sub-tall">Mål: 58–65</div>
        <div class="fremgang-bg"><div class="fremgang-fill" style="width:{ctl_pct}%;background:{'#22c55e' if ctl_na >= 58 else '#f59e0b'}"></div></div>
        <div style="font-size:0.75rem;color:#64748b">{"✅ I mål" if ctl_na >= 58 else f"⚠️ {ctl_gap} poeng bak min.mål"}</div>
      </div>
      <div>
        <div style="font-size:0.8rem;color:#94a3b8">TSB i dag</div>
        <div class="stor-tall" style="color:{'#22c55e' if 0 <= tsb_na <= 20 else '#f59e0b' if -10 <= tsb_na < 0 else '#ef4444' if tsb_na < -10 else '#94a3b8'}">{tsb_na:+.1f}</div>
        <div class="sub-tall">Race-mål: +12 til +20</div>
        <div class="fremgang-bg"><div class="fremgang-fill" style="width:{tsb_pct}%;background:#3b82f6"></div></div>
        <div style="font-size:0.75rem;color:#64748b">{"✅ Frisk og klar" if tsb_na >= 5 else "⚠️ Noe akkumulert" if tsb_na >= -10 else "🔴 Trøtt"}</div>
      </div>
      <div>
        <div style="font-size:0.8rem;color:#94a3b8">HRV</div>
        <div class="stor-tall" style="color:{'#22c55e' if 70 <= (hrv_na or 0) <= 98 else '#f59e0b' if (hrv_na or 0) >= 60 else '#ef4444'}">{hrv_na}</div>
        <div class="sub-tall">Balansert: 70–98 ms</div>
      </div>
    </div>
  </div>

  <!-- Dagsform -->
  <div class="grid2">
    <div class="kort">
      <h3>Dagsform</h3>
      <div class="metrikk-rad"><span class="metrikk-navn">HRV</span><span class="metrikk-verdi" style="color:{'#22c55e' if 70 <= (hrv_na or 0) <= 98 else '#f59e0b'}">{hrv_na} ms</span></div>
      <div class="metrikk-rad"><span class="metrikk-navn">Hvilepuls</span><span class="metrikk-verdi">{hvile_na} bpm</span></div>
      <div class="metrikk-rad"><span class="metrikk-navn">Body Battery</span><span class="metrikk-verdi" style="color:{'#22c55e' if (bb_na or 0) >= 70 else '#f59e0b' if (bb_na or 0) >= 50 else '#ef4444'}">{bb_na}/100</span></div>
      <div class="metrikk-rad"><span class="metrikk-navn">Søvn</span><span class="metrikk-verdi">{sovn_str}</span></div>
      <div class="metrikk-rad"><span class="metrikk-navn">Dyp søvn</span><span class="metrikk-verdi">{helse.get("dyp_sovn_min", "–")} min</span></div>
      <div class="metrikk-rad"><span class="metrikk-navn">REM</span><span class="metrikk-verdi">{helse.get("rem_sovn_min", "–")} min</span></div>
      <div class="metrikk-rad"><span class="metrikk-navn">Stress</span><span class="metrikk-verdi">{helse.get("stress_snitt", "–")}</span></div>
    </div>
    <div class="kort">
      <h3>Siste økt</h3>
      {"".join([
          f'<div class="metrikk-rad"><span class="metrikk-navn">Navn</span><span class="metrikk-verdi" style="font-size:0.85rem">{siste.get("navn","–")}</span></div>',
          f'<div class="metrikk-rad"><span class="metrikk-navn">Dato</span><span class="metrikk-verdi">{siste.get("dato","–")}</span></div>',
          f'<div class="metrikk-rad"><span class="metrikk-navn">Distanse</span><span class="metrikk-verdi">{siste.get("dist_km","–")} km</span></div>',
          f'<div class="metrikk-rad"><span class="metrikk-navn">Tempo</span><span class="metrikk-verdi">{siste.get("snitt_tempo","–")}</span></div>',
          f'<div class="metrikk-rad"><span class="metrikk-navn">Puls snitt</span><span class="metrikk-verdi">{siste.get("snitt_puls","–")} bpm</span></div>',
          f'<div class="metrikk-rad"><span class="metrikk-navn">NP</span><span class="metrikk-verdi">{siste.get("normalisert_watt","–")} W</span></div>',
          f'<div class="metrikk-rad"><span class="metrikk-navn">Suffer score</span><span class="metrikk-verdi">{siste.get("suffer_score","–")}</span></div>',
      ]) if siste else "<p style='color:#64748b'>Ingen økt registrert</p>"}
    </div>
  </div>

  <!-- Coaching-analyse -->
  <div class="seksjon-tittel">Coaching-analyse</div>
  <div class="analyse-boks">
    {analyse_html}
    <p style="margin-top:16px;font-size:0.75rem;color:#475569">Analyse: Claude claude-sonnet-4-6 (Anthropic) · {dato} · Data: Strava + TrainingPeaks</p>
  </div>

  <!-- CTL/ATL/TSB graf -->
  <div class="seksjon-tittel">Formkurve — siste 90 dager</div>
  <div class="chart-boks">
    <h3>CTL / ATL / TSB · Mål Hamburg: CTL 58–65, TSB +12–+20</h3>
    <canvas id="ctlChart" height="120"></canvas>
  </div>

  <!-- HRV -->
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

  <!-- Søvn -->
  <div class="chart-boks" style="margin-top:16px">
    <h3>Søvn — siste 14 dager (dyp · REM · lett)</h3>
    <canvas id="sovnChart" height="100"></canvas>
  </div>

  <!-- Ukeplan -->
  <div class="seksjon-tittel">Treningsplan frem til Hamburg</div>
  <div style="font-size:0.8rem;color:#64748b;margin-bottom:12px">
    ★ = Nøkkeløkt &nbsp;·&nbsp; Gul ramme = viktig økt &nbsp;·&nbsp; Grønn bakgrunn = i dag
  </div>
  {plan_html}

  <footer>
    <div style="margin-bottom:8px">
      <span>Data hentet fra:</span> Strava (aktiviteter) · TrainingPeaks (CTL/ATL/TSB, HRV, søvn, Body Battery) · Garmin via TrainingPeaks
    </div>
    <div style="margin-bottom:8px">
      <span>Analyse utført av:</span> Claude claude-sonnet-4-6 (Anthropic) &nbsp;·&nbsp;
      <span>Neste oppdatering:</span> kl. 09:00 norsk tid (automatisk)
    </div>
    <div>
      <span>Sist oppdatert:</span> {oppdatert} &nbsp;·&nbsp;
      <a href="https://github.com/oyvindgronner/garmin-morgenrapport" target="_blank">Kildekode</a>
    </div>
  </footer>
</div>

<script>
const PW_HASH = "{pw_hash}";

async function sha256(msg) {{
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(msg));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,"0")).join("");
}}

async function sjekkPw() {{
  const pw = document.getElementById("pw").value;
  const hash = await sha256(pw);
  if (hash === PW_HASH) {{
    localStorage.setItem("db_pw", hash);
    visDashboard();
  }} else {{
    document.getElementById("feil").textContent = "Feil passord";
  }}
}}

function visGate() {{
  document.getElementById("gate").style.display = "flex";
  document.getElementById("dash").style.display = "none";
}}

function visDatabase() {{
  document.getElementById("gate").style.display = "none";
  document.getElementById("dash").style.display = "block";
  byggGrafer();
}}

function visDialog() {{ visGate(); }}  // alias

function visGateway() {{ visGate(); }}

function visGateEl() {{ visGate(); }}

function visGat() {{ visGate(); }}

function visGa() {{ visGate(); }}

function visG() {{ visGate(); }}

function visGateId() {{ visGate(); }}

function visGateE() {{ visGate(); }}

function visDash() {{ visDatabase(); }}

function visD() {{ visDatabase(); }}

function visDB() {{ visDatabase(); }}

function visDashboard() {{ visDatabase(); }}

function visDatabase2() {{ visDatabase(); }}

function visDatabase3() {{ visDatabase(); }}

function visDatabase4() {{ visDatabase(); }}

function visDatabase5() {{ visDatabase(); }}

function visDatabase6() {{ visDatabase(); }}

function visDatabase7() {{ visDatabase(); }}

function visDatabase8() {{ visDatabase(); }}

const visGateways = visGate;
const visDashboards = visDatabase;

function visGateGate() {{ visGate(); }}
function visDashDash() {{ visDatabase(); }}
function visGateDash() {{ visGate(); }}
function visDashGate() {{ visDatabase(); }}

function visGateDashboard() {{ visGate(); }}
function visDashboardGate() {{ visDatabase(); }}

// Simpler aliases
const show_gate = visGate;
const show_dash = visDatabase;

// The actual function used
function visGateThingy() {{ visGate(); }}
function visDashThingy() {{ visDatabase(); }}

// Cleanup - just use these two
const showGate = visGate;
const showDash = visDatabase;

// Entry point
(async function() {{
  const saved = localStorage.getItem("db_pw");
  if (saved === PW_HASH) {{
    showDash();
  }} else {{
    showGate();
  }}
}})();

const CTL_DATA   = {ctl_js};
const ATL_DATA   = {atl_js};
const TSB_DATA   = {tsb_js};
const DATO_LBL   = {dato_js};
const HRV_LBL    = {hrv_lbl};
const HRV_VALS   = {hrv_vals};
const BB_LBL     = {bb_lbl};
const BB_VALS    = {bb_vals};
const SOVN_LBL   = {sovn_lbl};
const SOVN_DYP   = {sovn_dyp};
const SOVN_REM   = {sovn_rem};
const SOVN_LETT  = {sovn_lett};

const CHART_DEFAULTS = {{
  responsive: true,
  plugins: {{ legend: {{ labels: {{ color: "#94a3b8", boxWidth: 14 }} }} }},
  scales: {{
    x: {{ ticks: {{ color: "#64748b", maxTicksLimit: 12 }} , grid: {{ color: "#1e293b" }} }},
    y: {{ ticks: {{ color: "#64748b" }} , grid: {{ color: "#1e293b" }} }}
  }}
}};

function byggGrafer() {{
  // CTL/ATL/TSB
  new Chart(document.getElementById("ctlChart"), {{
    type: "line",
    data: {{
      labels: DATO_LBL,
      datasets: [
        {{ label: "CTL", data: CTL_DATA, borderColor: "#3b82f6", backgroundColor: "transparent", borderWidth: 2, pointRadius: 0, tension: 0.3 }},
        {{ label: "ATL", data: ATL_DATA, borderColor: "#f97316", backgroundColor: "transparent", borderWidth: 2, pointRadius: 0, tension: 0.3 }},
        {{ label: "TSB", data: TSB_DATA, borderColor: "#22c55e", backgroundColor: "#22c55e11", borderWidth: 1.5, pointRadius: 0, tension: 0.3, fill: true }},
      ]
    }},
    options: {{
      ...CHART_DEFAULTS,
      plugins: {{
        ...CHART_DEFAULTS.plugins,
        annotation: undefined
      }},
      scales: {{
        x: CHART_DEFAULTS.scales.x,
        y: {{ ...CHART_DEFAULTS.scales.y, suggestedMin: -30, suggestedMax: 80 }}
      }}
    }}
  }});

  // HRV
  new Chart(document.getElementById("hrvChart"), {{
    type: "line",
    data: {{
      labels: HRV_LBL,
      datasets: [{{
        label: "HRV (ms)",
        data: HRV_VALS,
        borderColor: "#a78bfa",
        backgroundColor: "#a78bfa22",
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: HRV_VALS.map(v => v >= 70 && v <= 98 ? "#22c55e" : v >= 60 ? "#f59e0b" : "#ef4444"),
        tension: 0.3,
        fill: true
      }}]
    }},
    options: {{
      ...CHART_DEFAULTS,
      scales: {{
        x: CHART_DEFAULTS.scales.x,
        y: {{ ...CHART_DEFAULTS.scales.y, suggestedMin: 40, suggestedMax: 110 }}
      }}
    }}
  }});

  // Body Battery
  new Chart(document.getElementById("bbChart"), {{
    type: "bar",
    data: {{
      labels: BB_LBL,
      datasets: [{{
        label: "Body Battery",
        data: BB_VALS,
        backgroundColor: BB_VALS.map(v => v >= 70 ? "#22c55e88" : v >= 50 ? "#f59e0b88" : "#ef444488"),
        borderColor:      BB_VALS.map(v => v >= 70 ? "#22c55e" : v >= 50 ? "#f59e0b" : "#ef4444"),
        borderWidth: 1,
        borderRadius: 4
      }}]
    }},
    options: {{
      ...CHART_DEFAULTS,
      scales: {{
        x: CHART_DEFAULTS.scales.x,
        y: {{ ...CHART_DEFAULTS.scales.y, min: 0, max: 100 }}
      }}
    }}
  }});

  // Søvn
  new Chart(document.getElementById("sovnChart"), {{
    type: "bar",
    data: {{
      labels: SOVN_LBL,
      datasets: [
        {{ label: "Dyp",  data: SOVN_DYP,  backgroundColor: "#1d4ed8aa", borderRadius: 3 }},
        {{ label: "REM",  data: SOVN_REM,  backgroundColor: "#7c3aedaa", borderRadius: 3 }},
        {{ label: "Lett", data: SOVN_LETT, backgroundColor: "#334155",   borderRadius: 3 }},
      ]
    }},
    options: {{
      ...CHART_DEFAULTS,
      scales: {{
        x: CHART_DEFAULTS.scales.x,
        y: {{ ...CHART_DEFAULTS.scales.y, stacked: true, title: {{ display: true, text: "min", color: "#64748b" }} }},
        x2: {{ stacked: true }}
      }},
      plugins: {{ ...CHART_DEFAULTS.plugins }},
      indexAxis: "x"
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
