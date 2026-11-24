"""
MF Dashboard - updater (one file does everything)
=================================================
Double-click Run_Update.bat  (or run:  python mf_update.py)

Each run automatically:
  1. downloads today's NAVs from AMFI (NAVAll.txt)
  2. downloads full NAV history for any fund that doesn't have it yet
     (first run: all funds, ~20-40 min; later runs: only new funds / gaps)
  3. cleans bad data, calculates returns, and writes the files the dashboard reads

Everything it creates goes into the  data  folder next to this file.
Settings you may want to change are right below.
"""

# ============================ SETTINGS ============================
PLANS = ["Direct"]                  # add "Regular" to include regular plans
OPTIONS = ["Growth"]                # Growth only: IDCW NAVs drop on payouts
SCHEME_TYPES = ["Open Ended"]
EXCLUDE_ASSET_CLASSES = []          # e.g. ["Debt"] or ["Other"] (Other = index funds, ETFs, FoFs)
EXCLUDE_NAME_WORDS = ["segregated", "unclaimed"]

TRAILING_PERIODS = ["1W", "1M", "3M", "6M", "YTD", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "SI"]
# ==================================================================

# Advanced settings (normally leave as is)
NAVALL_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
HISTORY_URL = "https://api.mfapi.in/mf/{code}"     # same source mftool uses for history
DOWNLOAD_WORKERS = 2           # parallel history downloads (keep low to avoid being blocked)
REQUEST_PAUSE = 0.5            # seconds between requests per worker
SPIKE_LIMIT = {"Equity": 0.15, "Hybrid": 0.10, "Debt": 0.05}   # daily move that triggers a check
SPIKE_DEFAULT = 0.15
REVERSAL_TOLERANCE = 0.03     # big move that comes back within 3% next day = bad print, removed
STALE_DAYS = 7                # no NAV for 7 days -> fund treated as closed/merged
GAP_BUSINESS_DAYS = 3         # fund missing more than 3 business days -> history refetched
CATEGORY_AVG_MIN_FUNDS = 3

import json
import logging
import math
import os
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
DB_PATH = DATA / "mf.db"
log = logging.getLogger("mf")


# ======================= 1. DATABASE =======================
SCHEMA = """
CREATE TABLE IF NOT EXISTS schemes (
  scheme_code INTEGER PRIMARY KEY, scheme_name TEXT, amc TEXT, scheme_type TEXT,
  asset_class TEXT, category TEXT, category_id TEXT, plan TEXT, option TEXT,
  first_seen TEXT, last_seen TEXT, in_universe INTEGER DEFAULT 0, status TEXT DEFAULT 'active');
CREATE TABLE IF NOT EXISTS nav_history (
  scheme_code INTEGER NOT NULL, nav_date TEXT NOT NULL, nav REAL NOT NULL,
  PRIMARY KEY (scheme_code, nav_date)) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS history_done (scheme_code INTEGER PRIMARY KEY, status TEXT, rows INTEGER, at TEXT);
CREATE TABLE IF NOT EXISTS nav_flags (scheme_code INTEGER, nav_date TEXT, flag TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS run_log (at TEXT, step TEXT, status TEXT, nav_date TEXT, message TEXT);
"""


def db_connect(path=DB_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL")
    con.executescript(SCHEMA)
    return con


def save_navs(con, rows):
    con.executemany(
        "INSERT INTO nav_history VALUES (?,?,?) ON CONFLICT(scheme_code, nav_date) DO UPDATE SET nav=excluded.nav",
        rows)
    con.commit()


def log_run(con, step, status, nav_date=None, message=""):
    con.execute("INSERT INTO run_log VALUES (?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), step, status, nav_date, message))
    con.commit()


# ======================= 2. READ AMFI NAVAll.txt =======================
SECTION_RE = re.compile(r"^(.*?)\s*Schemes?\s*\((.*)\)\s*$", re.IGNORECASE)


def parse_navall(text):
    """Rows look like  code;isin;isin;name;nav;date  under section + AMC header lines."""
    lines = text.replace("\r", "").split("\n")
    first = next((l for l in lines if l.strip()), "")
    if "scheme code" not in first.lower() or "net asset value" not in first.lower():
        raise ValueError("NAVAll.txt format not recognised (AMFI may have changed it). "
                         f"First line: {first[:100]!r}")
    out, stype, section, amc = [], None, None, None
    for raw in lines[1:]:
        line = raw.strip()
        if not line:
            continue
        p = line.split(";")
        if len(p) >= 6 and p[0].strip().isdigit():
            try:
                nav = float(p[-2].replace(",", ""))
                d = datetime.strptime(p[-1].strip(), "%d-%b-%Y").date()
            except ValueError:
                continue                       # 'N.A.' NAVs etc.
            if nav <= 0:
                continue
            out.append(dict(scheme_code=int(p[0]), scheme_name=";".join(p[3:-2]).strip(),
                            nav=nav, nav_date=d, scheme_type=stype, section=section, amc=amc))
        elif ";" in line:
            continue
        else:
            m = SECTION_RE.match(line)
            if m:
                stype, section, amc = m.group(1).strip().title(), m.group(2).strip(), None
            else:
                amc = line
    if not out:
        raise ValueError("NAVAll.txt has no scheme rows.")
    return out


IDCW_RE = re.compile(r"\bidcw\b|income distribution|\bdividend\b(?!\s+yield)|\bpayout\b|\breinvest", re.I)


def classify(rec):
    name = rec["scheme_name"]
    rec["plan"] = "Direct" if re.search(r"\bdirect\b|\bdir\b", name, re.I) else "Regular"
    if IDCW_RE.search(name):
        rec["option"] = "IDCW"
    elif re.search(r"\bbonus\b", name, re.I):
        rec["option"] = "Bonus"
    elif re.search(r"\bgrowth\b|\bcumulative\b", name, re.I):
        rec["option"] = "Growth"
    else:
        rec["option"] = "Other"
    sec = rec["section"] or "Unclassified"
    ac, cat = sec.split(" - ", 1) if " - " in sec else (sec, sec)
    rec["asset_class"] = re.sub(r"\s+Schemes?$", "", ac.strip(), flags=re.I)
    rec["category"] = re.sub(r"\s+Fund$", "", cat.strip(), flags=re.I)
    rec["category_id"] = re.sub(r"[^a-z0-9]+", "_", f"{rec['asset_class']}_{rec['category']}".lower()).strip("_")
    lname = name.lower()
    rec["in_universe"] = int(rec["scheme_type"] in SCHEME_TYPES and rec["plan"] in PLANS
                             and rec["option"] in OPTIONS and rec["asset_class"] not in EXCLUDE_ASSET_CLASSES
                             and not any(w in lname for w in EXCLUDE_NAME_WORDS))
    return rec


def save_schemes(con, recs):
    rows = [(r["scheme_code"], r["scheme_name"], r["amc"], r["scheme_type"], r["asset_class"], r["category"],
             r["category_id"], r["plan"], r["option"], r["nav_date"].isoformat(), r["nav_date"].isoformat(),
             r["in_universe"]) for r in recs]
    con.executemany("""INSERT INTO schemes (scheme_code, scheme_name, amc, scheme_type, asset_class, category,
                         category_id, plan, option, first_seen, last_seen, in_universe)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(scheme_code) DO UPDATE SET scheme_name=excluded.scheme_name, amc=excluded.amc,
                         scheme_type=excluded.scheme_type, asset_class=excluded.asset_class,
                         category=excluded.category, category_id=excluded.category_id, plan=excluded.plan,
                         option=excluded.option, last_seen=MAX(last_seen, excluded.last_seen),
                         in_universe=excluded.in_universe""", rows)
    con.commit()


def get_navall_text():
    """Download NAVAll.txt; if that fails, use a NAVAll.txt you saved into this folder."""
    for attempt in range(1, 4):
        try:
            r = requests.get(NAVALL_URL, timeout=60, headers={"User-Agent": "Mozilla/5.0 (personal MF dashboard)"})
            r.raise_for_status()
            return r.text
        except Exception as e:
            log.warning("AMFI download attempt %d failed: %s", attempt, e)
            time.sleep(5 * attempt)
    manual = HERE / "NAVAll.txt"
    if manual.exists():
        log.info("Using the NAVAll.txt saved in the folder instead.")
        return manual.read_text(encoding="utf-8", errors="replace")
    raise RuntimeError("Could not download NAVAll.txt. Open " + NAVALL_URL +
                       " in your browser, save it as NAVAll.txt in this folder, and run again.")


def step_daily(con, text):
    recs = [classify(r) for r in parse_navall(text)]
    nav_date = max(r["nav_date"] for r in recs)
    (DATA / "NAVAll_latest.txt").write_text(text, encoding="utf-8")
    prev_last = dict(con.execute("SELECT scheme_code, MAX(nav_date) FROM nav_history GROUP BY scheme_code"))
    save_schemes(con, recs)
    uni = [r for r in recs if r["in_universe"]]
    save_navs(con, [(r["scheme_code"], r["nav_date"].isoformat(), r["nav"]) for r in uni])
    gapped = [r["scheme_code"] for r in uni if r["scheme_code"] in prev_last
              and np.busday_count(prev_last[r["scheme_code"]], nav_date.isoformat()) > GAP_BUSINESS_DAYS]
    log.info("Today's NAVs: %s | %d funds in your universe (of %d schemes in the file)",
             nav_date, len(uni), len(recs))
    log_run(con, "daily", "ok", nav_date.isoformat(), f"{len(uni)} funds")
    return gapped


# ======================= 3. NAV HISTORY =======================
import threading
from collections import Counter
_local = threading.local()
_pause_until = [0.0]          # shared: when the server says "too many requests", all workers wait


def _session():
    if not hasattr(_local, "s"):
        _local.s = requests.Session()
        _local.s.headers["User-Agent"] = "Mozilla/5.0 (personal MF dashboard)"
    return _local.s


def fetch_history(code, attempts=5):
    """Full NAV history for one scheme. Retries with increasing waits; obeys rate limits."""
    last = None
    for i in range(attempts):
        wait = _pause_until[0] - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            r = _session().get(HISTORY_URL.format(code=code), timeout=60)
            if r.status_code == 429 or r.status_code >= 500:
                delay = float(r.headers.get("Retry-After") or 0) or [5, 15, 30, 60, 90][i]
                _pause_until[0] = max(_pause_until[0], time.time() + delay)
                last = f"HTTP {r.status_code} (server busy / too many requests)"
                continue
            if r.status_code >= 400:
                raise LookupError(f"HTTP {r.status_code} - scheme not available on {HISTORY_URL.split('/mf')[0]}")
            data = r.json().get("data") or []
            rows = []
            for item in data:
                try:
                    v = float(item["nav"])
                    if v > 0:
                        rows.append((code, datetime.strptime(item["date"], "%d-%m-%Y").date().isoformat(), v))
                except (KeyError, ValueError, TypeError):
                    continue
            time.sleep(REQUEST_PAUSE)
            return rows
        except LookupError:
            raise
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:150]}"
            time.sleep([2, 5, 10, 20, 30][i])
    raise RuntimeError(last)


def step_history(con, extra_codes=()):
    todo = [c for (c,) in con.execute(
        """SELECT s.scheme_code FROM schemes s LEFT JOIN history_done h USING (scheme_code)
           WHERE s.in_universe=1 AND (h.status IS NULL OR h.status='failed')""")]
    todo = sorted(set(todo) | set(extra_codes))
    if not todo:
        return
    if len(todo) > 100:
        log.info("Downloading NAV history for %d funds. First time takes 20-40 minutes. "
                 "If it stops, just run again - it continues where it left off.", len(todo))
    else:
        log.info("Downloading NAV history for %d new/gapped funds...", len(todo))
    ok = bad = 0
    reasons = Counter()
    with ThreadPoolExecutor(max_workers=DOWNLOAD_WORKERS) as ex:
        futs = {ex.submit(fetch_history, c): c for c in todo}
        for i, f in enumerate(as_completed(futs), 1):
            c, now = futs[f], datetime.now().isoformat(timespec="seconds")
            try:
                rows = f.result()
                save_navs(con, rows)
                con.execute("INSERT OR REPLACE INTO history_done VALUES (?,?,?,?)",
                            (c, "done" if rows else "empty", len(rows), now))
                ok += 1
            except Exception as e:
                con.execute("INSERT OR REPLACE INTO history_done VALUES (?,?,?,?)", (c, "failed", 0, now))
                bad += 1
                reasons[str(e)[:80]] += 1
                if bad <= 3:
                    log.warning("  history failed for scheme %s: %s", c, e)
            con.commit()
            if i % 50 == 0 or i == len(todo):
                log.info("  history: %d / %d done (%d failed)", i, len(todo), bad)
    log_run(con, "history", "ok" if not bad else "partial", None, f"ok={ok} failed={bad}")
    if bad:
        log.warning("%d funds failed to download - run again to retry them. Reasons:", bad)
        for why, n in reasons.most_common(3):
            log.warning("   %5d x  %s", n, why)


# ======================= 4. RETURN CALCULATIONS =======================
# Rules: holiday -> last NAV on or before the date | <=1 year absolute, >1 year CAGR (365.25-day years)
#        fund younger than the period -> blank | fund TWRR = chain-linked NAV returns = NAV1/NAV0 - 1
PERIOD_OFFSETS = {"1W": dict(weeks=1), "1M": dict(months=1), "3M": dict(months=3), "6M": dict(months=6),
                  "1Y": dict(years=1), "2Y": dict(years=2), "3Y": dict(years=3), "5Y": dict(years=5),
                  "7Y": dict(years=7), "10Y": dict(years=10)}


def nav_on_or_before(s, d):
    i = s.index.searchsorted(pd.Timestamp(d), side="right") - 1
    return (s.index[i], float(s.iloc[i])) if i >= 0 else (None, None)


def annualise(r, days):
    return (1 + r) ** (365.25 / days) - 1 if days > 366 else r


def twrr(sub_period_returns):
    return float(np.prod([1 + r for r in sub_period_returns]) - 1)


def trailing_return(s, as_of, period):
    as_of = pd.Timestamp(as_of)
    if s.empty:
        return None
    if period == "SI":
        start, n0 = s.index[0], float(s.iloc[0])
    else:
        start = pd.Timestamp(as_of.year - 1, 12, 31) if period == "YTD" else as_of - pd.DateOffset(**PERIOD_OFFSETS[period])
        if s.index[0] > start:
            return None
        _, n0 = nav_on_or_before(s, start)
    _, n1 = nav_on_or_before(s, as_of)
    days = (as_of - start).days
    return annualise(n1 / n0 - 1, days) if days > 0 else None


def calendar_returns(s, as_of):
    """Full calendar years {year: r} and the launch year {year: r} (partial)."""
    full, partial, prev = {}, {}, None
    for d, v in s.resample("YE").last().dropna().items():
        if d.year >= pd.Timestamp(as_of).year:
            break
        if prev is None:
            if (d - s.index[0]).days >= 7:
                r = v / float(s.iloc[0]) - 1
                if s.index[0] <= pd.Timestamp(d.year - 1, 12, 31) + pd.Timedelta(days=7):
                    full[d.year] = r
                else:
                    partial[d.year] = r
        else:
            full[d.year] = v / prev - 1
        prev = v
    return full, partial


def monthly_returns(s):
    me = s.resample("ME").last()
    r = (me / me.shift(1) - 1).iloc[1:]
    r.index = r.index.strftime("%Y-%m")
    return r


def category_average(panel):
    """Equal-weighted index (base 100) of the daily returns of the category's funds."""
    ff = panel.ffill(limit=5)
    rets = ff / ff.shift(1) - 1
    ok = (rets.notna().sum(axis=1) >= CATEGORY_AVG_MIN_FUNDS).to_numpy()
    out = np.full(len(panel), np.nan)
    if ok.any():
        pos = int(np.argmax(ok))
        g = (1 + rets.mean(axis=1).where(ok, 0.0)).to_numpy()
        out[max(pos - 1, 0)] = 100.0
        out[pos:] = 100.0 * np.cumprod(g[pos:])
    return out


def ranks(values):
    s = pd.Series({k: v for k, v in values.items() if v is not None}, dtype=float)
    if s.empty:
        return {}
    rk, n = s.rank(ascending=False, method="min"), len(s)
    return {k: [int(r), n, min(4, max(1, math.ceil(r / n * 4)))] for k, r in rk.items()}


def clean_panel(panel, asset_class):
    """Remove one-day bad prints; flag other big moves."""
    flags, out = [], panel.copy()
    for c in panel.columns:
        s = panel[c].dropna()
        if len(s) < 3:
            continue
        thr = SPIKE_LIMIT.get(asset_class, SPIKE_DEFAULT)
        r = s / s.shift(1) - 1
        bad = (r.abs() > thr) & ((s.shift(-1) / s.shift(1) - 1).abs() <= REVERSAL_TOLERANCE) & (r * r.shift(-1) < 0)
        for d in s.index[bad]:
            flags.append((int(c), d.date().isoformat(), "removed", f"{r[d]:+.1%} move reversed next day"))
        out.loc[s.index[bad], c] = np.nan
        s2 = s[~bad]
        r2 = s2 / s2.shift(1) - 1
        for d in s2.index[r2.abs() > thr]:
            flags.append((int(c), d.date().isoformat(), "big_move_kept", f"{r2[d]:+.1%}"))
    return out, flags


# ======================= 5. BUILD DASHBOARD FILES =======================
def _n(x, nd):
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(float(x), nd)


def _write_json(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(tmp, path)


def step_build(con):
    t0 = time.time()
    nav_dir = DATA / "nav"
    nav_dir.mkdir(parents=True, exist_ok=True)
    schemes = pd.read_sql_query("SELECT * FROM schemes WHERE in_universe=1", con)
    as_of_s = con.execute("""SELECT MAX(nav_date) FROM nav_history JOIN schemes USING (scheme_code)
                             WHERE in_universe=1""").fetchone()[0]
    if schemes.empty or not as_of_s:
        raise RuntimeError("No fund data yet.")
    as_of = pd.Timestamp(as_of_s)
    log.info("Calculating returns as of %s ...", as_of_s)
    con.execute("DELETE FROM nav_flags")
    funds, cats, cat_stats, csv, inactive = [], [], {}, [], set()

    for cat_id, g in schemes.groupby("category_id"):
        codes = g["scheme_code"].tolist()
        df = pd.read_sql_query(f"SELECT * FROM nav_history WHERE scheme_code IN ({','.join('?' * len(codes))})",
                               con, params=codes)
        if df.empty:
            continue
        df["nav_date"] = pd.to_datetime(df["nav_date"])
        panel = df.pivot(index="nav_date", columns="scheme_code", values="nav").sort_index()
        ac, cat_name = g["asset_class"].iloc[0], g["category"].iloc[0]
        panel, flags = clean_panel(panel, ac)
        con.executemany("INSERT INTO nav_flags VALUES (?,?,?,?)", flags)

        last = panel.apply(lambda c: c.last_valid_index())
        stale = {int(c) for c, d in last.items() if d is None or pd.isna(d) or d < as_of - pd.Timedelta(days=STALE_DAYS)}
        inactive |= stale
        active = [c for c in panel.columns if int(c) not in stale]
        if not active:
            continue
        panel = panel[active].dropna(how="all")
        meta = g.set_index("scheme_code")

        res, by_period, monthly = {}, {p: {} for p in TRAILING_PERIODS}, {}
        for c in active:
            s = panel[c].dropna()
            tr = {p: trailing_return(s, as_of, p) for p in TRAILING_PERIODS}
            for p, v in tr.items():
                by_period[p][c] = v
            res[c] = (s, tr, *calendar_returns(s, as_of))
            monthly[c] = monthly_returns(s)
        rk = {p: ranks(by_period[p]) for p in TRAILING_PERIODS}

        stats = {}
        for p in TRAILING_PERIODS:
            a = np.array([v for v in by_period[p].values() if v is not None])
            if len(a):
                stats[p] = {"avg": _n(a.mean() * 100, 2), "med": _n(np.median(a) * 100, 2),
                            "max": _n(a.max() * 100, 2), "min": _n(a.min() * 100, 2), "n": len(a)}
        cat_stats[cat_id] = stats

        for c in active:
            s, tr, cy, cyp = res[c]
            m = meta.loc[c]
            funds.append({"c": int(c), "n": m["scheme_name"], "amc": m["amc"], "cat": cat_id,
                          "inc": s.index[0].date().isoformat(), "last": s.index[-1].date().isoformat(),
                          "nav": _n(s.iloc[-1], 4),
                          "tr": {p: None if v is None else _n(v * 100, 2) for p, v in tr.items()},
                          "cy": {str(y): _n(v * 100, 2) for y, v in cy.items()},
                          "cyp": {str(y): _n(v * 100, 2) for y, v in cyp.items()},
                          "rk": {p: rk[p][c] for p in TRAILING_PERIODS if c in rk[p]}})
            csv.append({"Scheme Code": int(c), "Scheme Name": m["scheme_name"], "AMC": m["amc"],
                        "Asset Class": ac, "Category": cat_name, "Inception": s.index[0].date(),
                        "NAV Date": s.index[-1].date(), "NAV": round(s.iloc[-1], 4),
                        **{f"{p} %": (None if v is None else round(v * 100, 2)) for p, v in tr.items()}})

        months = sorted({k for ser in monthly.values() for k in ser.index})
        _write_json(nav_dir / f"{cat_id}.json", {
            "id": cat_id, "name": cat_name, "ac": ac, "as_of": as_of_s,
            "dates": [d.date().isoformat() for d in panel.index],
            "series": {str(int(c)): [_n(v, 4) for v in panel[c].to_numpy()] for c in active},
            "cat_avg": [_n(v, 4) for v in category_average(panel)],
            "months": months,
            "monthly": {str(int(c)): [_n(monthly[c].get(mo, np.nan) * 100, 2) for mo in months] for c in active}})
        cats.append({"id": cat_id, "name": cat_name, "ac": ac, "n": len(active), "file": f"nav/{cat_id}.json"})

    con.execute("UPDATE schemes SET status='active' WHERE in_universe=1")
    con.executemany("UPDATE schemes SET status='inactive' WHERE scheme_code=?", [(c,) for c in inactive])
    con.commit()
    _write_json(DATA / "summary.json", {
        "as_of": as_of_s, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "periods": TRAILING_PERIODS, "categories": sorted(cats, key=lambda c: (c["ac"], c["name"])),
        "cat_stats": cat_stats, "funds": funds, "inactive_count": len(inactive)})
    try:
        pd.DataFrame(csv).to_csv(DATA / "Fund_Returns.csv", index=False)
    except PermissionError:
        log.warning("Fund_Returns.csv is open in Excel - close it to let it update next time.")
    msg = f"{len(funds)} funds in {len(cats)} categories ({len(inactive)} closed/merged skipped)"
    log_run(con, "build", "ok", as_of_s, msg)
    log.info("Returns ready: %s in %.0fs", msg, time.time() - t0)


# ======================= DEMO (works offline) =======================
def make_demo_navall(seed=7):
    """Synthetic AMFI-format file + history so you can try everything without internet."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2012-01-02", pd.Timestamp(date.today()) - pd.offsets.BDay(1))
    mkt = rng.normal(0.13 / 252, 0.17 / np.sqrt(252), len(days))
    cats = [("Equity Scheme - Large Cap Fund", 10, 0.12, 0.16, 0.95), ("Equity Scheme - Mid Cap Fund", 10, 0.16, 0.21, 1.15),
            ("Equity Scheme - Small Cap Fund", 8, 0.18, 0.25, 1.25), ("Equity Scheme - Flexi Cap Fund", 10, 0.14, 0.18, 1.0),
            ("Hybrid Scheme - Aggressive Hybrid Fund", 6, 0.11, 0.12, 0.7), ("Debt Scheme - Liquid Fund", 6, 0.065, 0.004, 0)]
    amcs = ["Alpha", "Bharat", "Coastal", "Deccan", "Everest", "Ganga", "Himalaya", "Indus", "Jaipur", "Kaveri"]
    lines = ["Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Net Asset Value;Date", ""]
    hist, code = [], 900001
    for sec, k, mu, vol, beta in cats:
        lines += [f"Open Ended Schemes({sec})", ""]
        for i in range(k):
            st = 0 if i < k - 3 else int(rng.integers(len(days) // 3, len(days) - 300))
            if beta:
                r = beta * mkt + rng.normal((mu - beta * 0.13) / 252, vol * 0.5 / np.sqrt(252), len(days))
            else:
                r = rng.normal(mu / 252, vol / np.sqrt(252), len(days))
            nav = 10 * np.cumprod(1 + r[st:])
            name = f"{amcs[i]} {sec.split(' - ')[1]} - Direct Plan - Growth"
            lines += [f"{amcs[i]} Mutual Fund", f"{code};INFDEMO{code};-;{name};{nav[-1]:.4f};{days[-1]:%d-%b-%Y}", ""]
            hist += [(code, d.date().isoformat(), float(v)) for d, v in zip(days[st:], nav)]
            code += 1
    return "\n".join(lines), hist


# ======================= RUN =======================
def main():
    DATA.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(DATA / "update_log.txt", encoding="utf-8")])
    demo = "--demo" in sys.argv
    con = db_connect(DATA / "demo.db" if demo else DB_PATH)
    try:
        if demo:
            log.info("DEMO MODE: synthetic funds, no internet needed")
            text, hist = make_demo_navall()
            step_daily(con, text)
            save_navs(con, hist)
            con.executemany("INSERT OR REPLACE INTO history_done VALUES (?, 'done', 0, '')",
                            [(c,) for c in {h[0] for h in hist}])
            con.commit()
        else:
            gapped = step_daily(con, get_navall_text())
            step_history(con, gapped)
            missing = con.execute("""SELECT COUNT(*) FROM schemes s JOIN history_done h USING (scheme_code)
                                     WHERE s.in_universe=1 AND h.status='failed'""").fetchone()[0]
            if missing:
                log.warning("NOTE: %d funds still have no history, so their returns will be blank. "
                            "Run Run_Update.bat again to retry them.", missing)
        step_build(con)
        log.info("All done. Data is in: %s", DATA)
    except Exception as e:
        log.error("STOPPED: %s", e)
        log_run(con, "run", "failed", None, str(e)[:300])
        log.info("Your previous dashboard data is unchanged. Details are in data/update_log.txt")
        sys.exit(1)
    finally:
        con.close()


if __name__ == "__main__":
    main()
