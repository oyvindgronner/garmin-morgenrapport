import sys
import requests

TP_AUTH_COOKIE = sys.argv[1] if len(sys.argv) > 1 else input("Production_tpAuth: ").strip()
ATHLETE_ID = 4974341
ALT_ID = 1434794  # fra profilbilde-URL
BASE = "https://tpapi.trainingpeaks.com"

r = requests.get(f"{BASE}/users/v3/token",
    headers={"Cookie": f"Production_tpAuth={TP_AUTH_COOKIE}",
             "Accept": "application/json",
             "Origin": "https://app.trainingpeaks.com"}, timeout=15)
token = r.json()["token"]["access_token"]
print("Token OK")

h = {"Authorization": f"Bearer {token}", "Accept": "application/json",
     "Origin": "https://app.trainingpeaks.com"}
hc = {"Cookie": f"Production_tpAuth={TP_AUTH_COOKIE}",
      "Accept": "application/json", "Origin": "https://app.trainingpeaks.com"}

tests = [
    # Med ALT_ID 1434794
    (h,  f"{BASE}/workouts/v1/athletes/{ALT_ID}/workouts/2026-03-01/2026-03-13"),
    (hc, f"{BASE}/workouts/v1/athletes/{ALT_ID}/workouts/2026-03-01/2026-03-13"),
    (h,  f"{BASE}/workouts/v1/athletes/{ALT_ID}/calendar/2026-03-01/2026-03-13"),
    (hc, f"{BASE}/workouts/v1/athletes/{ALT_ID}/calendar/2026-03-01/2026-03-13"),
    (h,  f"{BASE}/baseactivity/v1/athletes/{ALT_ID}/workouts/2026-03-01/2026-03-13"),
    (hc, f"{BASE}/baseactivity/v1/athletes/{ALT_ID}/workouts/2026-03-01/2026-03-13"),
    (h,  f"{BASE}/fitness/v1/athletes/{ALT_ID}/fitnessdata?startDate=2026-01-01&endDate=2026-03-13"),
    (h,  f"{BASE}/fitness/v3/athletes/{ALT_ID}/fitnessdata?startDate=2026-01-01&endDate=2026-03-13"),
    (h,  f"{BASE}/metrics/v1/athletes/{ALT_ID}/metrics?startDate=2026-01-01&endDate=2026-03-13"),
    (hc, f"{BASE}/metrics/v1/athletes/{ALT_ID}/metrics?startDate=2026-01-01&endDate=2026-03-13"),
    (h,  f"{BASE}/fitness/v3/athletes/{ALT_ID}/load/2026-01-01/2026-03-13"),
    (hc, f"{BASE}/fitness/v3/athletes/{ALT_ID}/load/2026-01-01/2026-03-13"),
    # Uten athlete ID — generiske endepunkter
    (h,  f"{BASE}/workouts/v1/workouts/2026-03-01/2026-03-13"),
    (hc, f"{BASE}/workouts/v1/workouts/2026-03-01/2026-03-13"),
    (h,  f"{BASE}/fitness/v3/fitness?startDate=2026-01-01&endDate=2026-03-13"),
    (hc, f"{BASE}/fitness/v3/fitness?startDate=2026-01-01&endDate=2026-03-13"),
    # Med coach-ID
    (h,  f"{BASE}/workouts/v1/athletes/3026018/athletes/{ATHLETE_ID}/workouts/2026-03-01/2026-03-13"),
    (hc, f"{BASE}/workouts/v1/coaches/3026018/athletes/{ATHLETE_ID}/workouts/2026-03-01/2026-03-13"),
]

print(f"\n{'STATUS':<8} {'AUTH':<8} PATH")
print("-" * 80)
for headers, url in tests:
    try:
        r = requests.get(url, headers=headers, timeout=10)
        auth = "bearer" if "Authorization" in headers else "cookie"
        path = url.replace(BASE, "")
        mark = " ✓" if r.status_code == 200 else ""
        print(f"[{r.status_code}]    [{auth}]  {path}{mark}")
        if r.status_code == 200:
            print(f"         PREVIEW: {r.text[:200]}")
    except Exception as e:
        print(f"[ERR]             {url} — {e}")