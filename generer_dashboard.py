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
import os
from datetime import date, datetime, timezone


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
        return "<p>Ingen analyse tilgjengelig.</p>"
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

    passord    = os.environ.get("DASHBOARD_PASSWORD", "hamburg2026")
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
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f172a;color:#e2e8f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:15px;line-height:1.5}}
a{{color:#60a5fa}}
#gate{{display:flex;align-items:center;justify-content:center;min-height:100vh}}
.gate-box{{background:#1e293b;border-radius:16px;padding:40px;text-align:center;max-width:340px;width:90%}}
.gate-box h2{{margin-bottom:8px;font-size:1.3rem}}
.gate-box p{{color:#94a3b8;margin-bottom:24px;font-size:0.9rem}}
.gate-box input{{width:100%;padding:10px 14px;border-radius:8px;border:1px solid #334155;background:#0f172a;color:#e2e8f0;font-size:1rem;margin-bottom:12px}}
.gate-box button{{width:100%;padding:10px;border-radius:8px;border:none;background:#3b82f6;color:#fff;font-size:1rem;font-weight:600;cursor:pointer}}
.gate-box .feil{{color:#ef4444;font-size:0.85rem;margin-top:8px;min-height:1.2em}}
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
footer{{text-align:center;color:#475569;font-size:0.78rem;padding:40px 0 20px;line-height:1.8}}
footer span{{color:#64748b}}
</style>
</head>
<body>

<!-- Passord-gate -->
<div id="gate">
  <div class="gate-box">
    <h2>🏃 Treningsdashboard</h2>
    <p>Hamburg Maraton 2026 — Øyvind Grønner</p>
    <input type="password" id="pw" placeholder="Passord"
           onkeydown="if(event.key==='Enter')loggInn()">
    <button onclick="loggInn()" id="logg-inn-knapp">Logg inn</button>
    <div class="feil" id="feil"></div>
  </div>
</div>

<!-- Dashboard — fylles av JS etter dekryptering -->
<div id="dash">
  <div class="topbar">
    <div class="topbar-left">
      <h1>Hamburg Maraton 2026</h1>
      <p id="meta">Laster…</p>
    </div>
    <div class="badge" id="badge"></div>
  </div>

  <!-- Hamburg-mål -->
  <div class="kort" id="maal-kort" style="margin-bottom:16px;border-left:4px solid #fbbf24">
    <h3 id="maal-tittel">Hamburg-mål · Sub 3:00</h3>
    <div class="grid3" style="margin-top:12px;margin-bottom:0" id="maal-grid"></div>
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
  <div class="seksjon-tittel">Formkurve — siste 90 dager</div>
  <div class="chart-boks">
    <h3>CTL / ATL / TSB · Mål Hamburg: CTL 58–65, TSB +12–+20</h3>
    <canvas id="ctlChart" height="120"></canvas>
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
    <div style="margin-bottom:8px">
      <span>Data hentet fra:</span> Strava (aktiviteter) · TrainingPeaks (CTL/ATL/TSB, HRV, søvn, Body Battery) · Garmin via TrainingPeaks
    </div>
    <div style="margin-bottom:8px">
      <span>Analyse utført av:</span> Claude claude-sonnet-4-6 (Anthropic) &nbsp;·&nbsp;
      <span>Neste oppdatering:</span> kl. 09:00 norsk tid (automatisk)
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
      <div style="font-size:.8rem;color:#94a3b8">CTL nå</div>
      <div class="stor-tall" style="color:${{fargeCTL(ctl)}}">${{ctl}}</div>
      <div class="sub-tall">Mål: 58–65</div>
      <div class="fremgang-bg"><div class="fremgang-fill" style="width:${{ctlPct}}%;background:${{fargeCTL(ctl)}}"></div></div>
      <div style="font-size:.75rem;color:#64748b">${{ctl >= 58 ? "✅ I mål" : `⚠️ ${{(58-ctl).toFixed(1)}} bak min.mål`}}</div>
    </div>
    <div>
      <div style="font-size:.8rem;color:#94a3b8">TSB i dag</div>
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
  document.getElementById("dagsform-innhold").innerHTML =
    metrikk("HRV",       hrv ? `${{hrv}} ms` : "–",      fargeHRV(hrv||0))
  + metrikk("Hvilepuls", helse.hvilepuls ? `${{helse.hvilepuls}} bpm` : "–")
  + metrikk("Body Battery", helse.bb_maks ? `${{helse.bb_maks}}/100` : "–", fargeBB(helse.bb_maks||0))
  + metrikk("Søvn",        sovnStr)
  + metrikk("Dyp søvn",    helse.dyp_sovn_min ? `${{helse.dyp_sovn_min}} min` : "–")
  + metrikk("REM",         helse.rem_sovn_min ? `${{helse.rem_sovn_min}} min` : "–")
  + metrikk("Stress",      helse.stress_snitt ?? "–");

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
    plugins: {{ legend: {{ labels: {{ color:"#94a3b8", boxWidth:14 }} }} }},
    scales: {{
      x: {{ ticks:{{ color:"#64748b", maxTicksLimit:12 }}, grid:{{ color:"#1e293b" }} }},
      y: {{ ticks:{{ color:"#64748b" }},                   grid:{{ color:"#1e293b" }} }}
    }}
  }};

  // CTL/ATL/TSB
  new Chart(document.getElementById("ctlChart"), {{
    type: "line",
    data: {{
      labels: d.trend90.map(x => x.dato),
      datasets: [
        {{label:"CTL", data:d.trend90.map(x=>x.ctl), borderColor:"#3b82f6", backgroundColor:"transparent", borderWidth:2, pointRadius:0, tension:0.3}},
        {{label:"ATL", data:d.trend90.map(x=>x.atl), borderColor:"#f97316", backgroundColor:"transparent", borderWidth:2, pointRadius:0, tension:0.3}},
        {{label:"TSB", data:d.trend90.map(x=>x.tsb), borderColor:"#22c55e", backgroundColor:"#22c55e11", borderWidth:1.5, pointRadius:0, tension:0.3, fill:true}},
      ]
    }},
    options: {{...DEFAULTS, scales:{{x:DEFAULTS.scales.x, y:{{...DEFAULTS.scales.y, suggestedMin:-30, suggestedMax:80}}}}}}
  }});

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
