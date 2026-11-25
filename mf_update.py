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
PLANS = ["Direct", "Regular"]       # both plans; choose between them in the dashboard
OPTIONS = ["Growth"]                # Growth only: IDCW NAVs drop on payouts, so NAV returns would be wrong
SCHEME_TYPES = ["Open Ended"]
EXCLUDE_ASSET_CLASSES = []          # e.g. ["Debt"] or ["Other"] (Other = index funds, ETFs, FoFs)
EXCLUDE_NAME_WORDS = ["segregated", "unclaimed"]

TRAILING_PERIODS = ["1W", "1M", "3M", "6M", "YTD", "1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "SI"]
DAYS_IN_YEAR = 365                  # CAGR = (NAV1/NAV0) ** (365 / days) - 1

# Benchmarks (NSE Total Return Indices, downloaded from niftyindices.com) - Equity categories only.
# Category names are as AMFI writes them (shown in the dashboard's Category list).
BENCHMARKS = {
    "Large Cap": "NIFTY 100",
    "Mid Cap": "NIFTY MIDCAP 150",
    "Small Cap": "NIFTY SMALLCAP 250",
}
EQUITY_DEFAULT_BENCHMARK = "NIFTY 500"   # every other Equity category (Flexi, Focused, Contra, Value, ELSS, ...)
BENCHMARK_HISTORY_FROM = "2005-04-01"    # index history is downloaded from this date (or the index's start, if later)
BENCHMARK_WORKERS = 2                    # indices downloaded in parallel

# All NSE equity Total Return Indices: (index name, name NSE's download service expects, group, index base date)
NSE_INDICES = [
    ("NIFTY 500", "NIFTY 500", "Broad market", "1995-01-01"),
    ("NIFTY 50", "NIFTY 50", "Broad market", "1995-11-03"),
    ("NIFTY NEXT 50", "NIFTY NEXT 50", "Broad market", "1996-11-04"),
    ("NIFTY 100", "NIFTY 100", "Broad market", "2003-01-01"),
    ("NIFTY MIDCAP 100", "NIFTY MIDCAP 100", "Broad market", "2003-01-01"),
    ("NIFTY 200", "NIFTY 200", "Broad market", "2004-01-01"),
    ("NIFTY MIDCAP 50", "NIFTY MIDCAP 50", "Broad market", "2004-01-01"),
    ("NIFTY SMALLCAP 100", "NIFTY SMLCAP 100", "Broad market", "2004-01-01"),
    ("NIFTY LARGEMIDCAP 250", "NIFTY LARGEMID250", "Broad market", "2005-04-01"),
    ("NIFTY MICROCAP 250", "NIFTY MICROCAP250", "Broad market", "2005-04-01"),
    ("NIFTY MIDCAP 150", "NIFTY MIDCAP 150", "Broad market", "2005-04-01"),
    ("NIFTY MIDSMALLCAP 400", "NIFTY MIDSMALLCAP 400", "Broad market", "2005-04-01"),
    ("NIFTY MIDSMALLCAP400 50:50", "NIFTY MIDSMALLCAP400 50:50", "Broad market", "2005-04-01"),
    ("NIFTY SMALLCAP 250", "NIFTY SMALLCAP 250", "Broad market", "2005-04-01"),
    ("NIFTY SMALLCAP 50", "NIFTY SMALLCAP 50", "Broad market", "2005-04-01"),
    ("NIFTY SMALLCAP 500", "NIFTY SMALLCAP 500", "Broad market", "2005-04-01"),
    ("NIFTY TOTAL MARKET", "NIFTY TOTAL MKT", "Broad market", "2005-04-01"),
    ("NIFTY500 LARGEMIDSMALL EQUAL-CAP WEIGHTED", "NIFTY500 LARGEMIDSMALL EQUAL-CAP WEIGHTED", "Broad market", "2005-04-01"),
    ("NIFTY500 MULTICAP 50:25:25", "NIFTY500 MULTICAP", "Broad market", "2005-04-01"),
    ("NIFTY MIDCAP SELECT", "NIFTY MID SELECT", "Broad market", "2005-10-03"),
    ("NIFTY NEXT 100", "NIFTY NEXT 100", "Broad market", "2010-10-01"),
    ("NIFTY INDIA FPI 150", "NIFTY INDIA FPI 150", "Broad market", "2022-10-03"),
    ("NIFTY FMCG", "NIFTY FMCG", "Sector", "1996-01-01"),
    ("NIFTY IT", "NIFTY IT", "Sector", "1996-01-01"),
    ("NIFTY BANK", "NIFTY BANK", "Sector", "2000-01-01"),
    ("NIFTY PHARMA", "NIFTY PHARMA", "Sector", "2001-01-01"),
    ("NIFTY AUTO", "NIFTY AUTO", "Sector", "2004-01-01"),
    ("NIFTY FINANCIAL SERVICES", "NIFTY FIN SERVICE", "Sector", "2004-01-01"),
    ("NIFTY FINANCIAL SERVICES 25/50", "NIFTY FINSRV25 50", "Sector", "2004-01-01"),
    ("NIFTY METAL", "NIFTY METAL", "Sector", "2004-01-01"),
    ("NIFTY PSU BANK", "NIFTY PSU BANK", "Sector", "2004-01-01"),
    ("NIFTY HEALTHCARE", "NIFTY HEALTHCARE", "Sector", "2004-04-01"),
    ("NIFTY PRIVATE BANK", "NIFTY PVT BANK", "Sector", "2004-05-01"),
    ("NIFTY CAPITAL GOODS", "NIFTY CAPITAL GOODS", "Sector", "2005-04-01"),
    ("NIFTY CEMENT", "NIFTY CEMENT", "Sector", "2005-04-01"),
    ("NIFTY CHEMICALS", "NIFTY CHEMICALS", "Sector", "2005-04-01"),
    ("NIFTY COMMERCIAL & TRANSPORT SERVICES", "NIFTY COMMERCIAL & TRANSPORT SERVICES", "Sector", "2005-04-01"),
    ("NIFTY CONSTRUCTION", "NIFTY CONSTRUCTION", "Sector", "2005-04-01"),
    ("NIFTY CONSUMER DURABLES", "NIFTY CONSR DURBL", "Sector", "2005-04-01"),
    ("NIFTY FINANCIAL SERVICES EX-BANK", "NIFTY FINANCIAL SERVICES EX-BANK", "Sector", "2005-04-01"),
    ("NIFTY MIDSMALL FINANCIAL SERVICES", "NIFTY MIDSMALL FINANCIAL SERVICES", "Sector", "2005-04-01"),
    ("NIFTY MIDSMALL HEALTHCARE", "NIFTY MIDSML HLTH", "Sector", "2005-04-01"),
    ("NIFTY MIDSMALL IT & TELECOM", "NIFTY MIDSMALL IT & TELECOM", "Sector", "2005-04-01"),
    ("NIFTY NBFC", "NIFTY NBFC", "Sector", "2005-04-01"),
    ("NIFTY OIL & GAS", "NIFTY OIL AND GAS", "Sector", "2005-04-01"),
    ("NIFTY POWER", "NIFTY POWER", "Sector", "2005-04-01"),
    ("NIFTY TELECOMMUNICATIONS", "NIFTY TELECOMMUNICATIONS", "Sector", "2005-04-01"),
    ("NIFTY500 HEALTHCARE", "NIFTY500 HEALTHCARE", "Sector", "2005-04-01"),
    ("NIFTY MEDIA", "NIFTY MEDIA", "Sector", "2005-12-30"),
    ("NIFTY REALTY", "NIFTY REALTY", "Sector", "2006-12-29"),
    ("NIFTY HOUSING FINANCE", "NIFTY HOUSING FINANCE", "Sector", "2018-04-02"),
    ("NIFTY RETAIL", "NIFTY RETAIL", "Sector", "2018-04-02"),
    ("NIFTY INSURANCE", "NIFTY INSURANCE", "Sector", "2019-09-27"),
    ("NIFTY CONSUMER SERVICES", "NIFTY CONSUMER SERVICES", "Sector", "2020-07-01"),
    ("NIFTY HOSPITALS", "NIFTY HOSPITALS", "Sector", "2021-03-31"),
    ("NIFTY REITS & REALTY", "NIFTY REITS & REALTY", "Sector", "2021-07-01"),
    ("NIFTY MNC", "NIFTY MNC", "Thematic", "1994-12-31"),
    ("NIFTY PSE", "NIFTY PSE", "Thematic", "1995-01-01"),
    ("NIFTY SERVICES SECTOR", "NIFTY SERV SECTOR", "Thematic", "1999-06-01"),
    ("NIFTY ENERGY", "NIFTY ENERGY", "Thematic", "2001-01-01"),
    ("NIFTY COMMODITIES", "NIFTY COMMODITIES", "Thematic", "2004-01-01"),
    ("NIFTY INFRASTRUCTURE", "NIFTY INFRA", "Thematic", "2004-01-01"),
    ("NIFTY CONGLOMERATE 50", "NIFTY CONGLOMERATE 50", "Thematic", "2005-04-01"),
    ("NIFTY CORE HOUSING", "NIFTY CORE HOUSING", "Thematic", "2005-04-01"),
    ("NIFTY HOUSING", "NIFTY HOUSING", "Thematic", "2005-04-01"),
    ("NIFTY INDIA CORPORATE GROUP INDEX - ADITYA BIRLA GROUP", "NIFTY INDIA CORPORATE GROUP INDEX - ADITYA BIRLA GROUP", "Thematic", "2005-04-01"),
    ("NIFTY INDIA CORPORATE GROUP INDEX - MAHINDRA GROUP", "NIFTY INDIA CORPORATE GROUP INDEX - MAHINDRA GROUP", "Thematic", "2005-04-01"),
    ("NIFTY INDIA CORPORATE GROUP INDEX - TATA GROUP", "NIFTY INDIA CORPORATE GROUP INDEX - TATA GROUP", "Thematic", "2005-04-01"),
    ("NIFTY INDIA CORPORATE GROUP INDEX - TATA GROUP 25% CAP", "NIFTY TATA 25 CAP", "Thematic", "2005-04-01"),
    ("NIFTY INDIA DIGITAL", "NIFTY IND DIGITAL", "Thematic", "2005-04-01"),
    ("NIFTY INDIA INFRASTRUCTURE & LOGISTICS", "NIFTY INDIA INFRASTRUCTURE & LOGISTICS", "Thematic", "2005-04-01"),
    ("NIFTY INDIA MANUFACTURING", "NIFTY INDIA MFG", "Thematic", "2005-04-01"),
    ("NIFTY INDIA NEW AGE CONSUMPTION", "NIFTY INDIA NEW AGE CONSUMPTION", "Thematic", "2005-04-01"),
    ("NIFTY INDIA SELECT 5 CORPORATE GROUPS (MAATR)", "NIFTY INDIA SELECT 5 CORPORATE GROUPS (MAATR)", "Thematic", "2005-04-01"),
    ("NIFTY INDIA TOURISM", "NIFTY INDIA TOURISM", "Thematic", "2005-04-01"),
    ("NIFTY MIDSMALL INDIA CONSUMPTION", "NIFTY MIDSMALL INDIA CONSUMPTION", "Thematic", "2005-04-01"),
    ("NIFTY MOBILITY", "NIFTY MOBILITY", "Thematic", "2005-04-01"),
    ("NIFTY NON-CYCLICAL CONSUMER", "NIFTY NON-CYCLICAL CONSUMER", "Thematic", "2005-04-01"),
    ("NIFTY RURAL", "NIFTY RURAL", "Thematic", "2005-04-01"),
    ("NIFTY TRANSPORTATION & LOGISTICS", "NIFTY TRANSPORTATION & LOGISTICS", "Thematic", "2005-04-01"),
    ("NIFTY WAVES", "NIFTY WAVES", "Thematic", "2005-04-01"),
    ("NIFTY500 MULTICAP INDIA MANUFACTURING 50:30:20", "NIFTY MULTI MFG", "Thematic", "2005-04-01"),
    ("NIFTY500 MULTICAP INFRASTRUCTURE 50:30:20", "NIFTY MULTI INFRA", "Thematic", "2005-04-01"),
    ("NIFTY INDIA CONSUMPTION", "NIFTY CONSUMPTION", "Thematic", "2006-01-02"),
    ("NIFTY50 SHARIAH", "NIFTY50 SHARIAH", "Thematic", "2006-12-29"),
    ("NIFTY500 SHARIAH", "NIFTY500 SHARIAH", "Thematic", "2006-12-29"),
    ("NIFTY CPSE", "NIFTY CPSE", "Thematic", "2009-01-01"),
    ("NIFTY MIDCAP LIQUID 15", "NIFTY MID LIQ 15", "Thematic", "2009-01-01"),
    ("NIFTY SHARIAH 25", "NIFTY SHARIAH 25", "Thematic", "2009-01-01"),
    ("NIFTY100 LIQUID 15", "NIFTY100 LIQ 15", "Thematic", "2009-01-01"),
    ("NIFTY100 ENHANCED ESG", "NIFTY100 ENHANCED ESG", "Thematic", "2011-04-01"),
    ("NIFTY100 ESG", "NIFTY100 ESG", "Thematic", "2011-04-01"),
    ("NIFTY100 ESG SECTOR LEADERS", "NIFTY100ESGSECLDR", "Thematic", "2014-01-01"),
    ("NIFTY500 AHIMSA", "NIFTY500 AHIMSA", "Thematic", "2016-04-01"),
    ("NIFTY SME EMERGE", "NIFTY SME EMERGE", "Thematic", "2016-12-01"),
    ("NIFTY IPO", "NIFTY IPO", "Thematic", "2017-01-02"),
    ("NIFTY EV & NEW AGE AUTOMOTIVE", "NIFTY EV & NEW AGE AUTOMOTIVE", "Thematic", "2018-04-02"),
    ("NIFTY INDIA DEFENCE", "NIFTY INDIA DEFENCE", "Thematic", "2018-04-02"),
    ("NIFTY INDIA DEFENCE EQUAL WEIGHT", "NIFTY INDIA DEFENCE EQUAL WEIGHT", "Thematic", "2018-04-02"),
    ("NIFTY CAPITAL MARKETS", "NIFTY CAPITAL MARKETS", "Thematic", "2019-04-01"),
    ("NIFTY REITS & INVITS", "NIFTY REITS & INVITS", "Thematic", "2019-07-01"),
    ("NIFTY SMALL FINANCE BANKS & MICROFINANCE INSTITUTIONS", "NIFTY SMALL FINANCE BANKS & MICROFINANCE INSTITUTIONS", "Thematic", "2021-03-31"),
    ("NIFTY SUGAR & ETHANOL", "NIFTY SUGAR & ETHANOL", "Thematic", "2021-03-31"),
    ("NIFTY INDIA RAILWAYS PSU", "NIFTY INDIA RAILWAYS PSU", "Thematic", "2021-04-01"),
    ("NIFTY REITS & INVITS 90:10", "NIFTY REITS & INVITS 90:10", "Thematic", "2021-04-01"),
    ("NIFTY INDIA INTERNET", "NIFTY INDIA INTERNET", "Thematic", "2021-10-01"),
    ("NIFTY AI CATALYSTS", "NIFTY AI CATALYSTS", "Thematic", "2024-06-28"),
    ("NIFTY50 EQUAL WEIGHT", "NIFTY50 EQL WGT", "Strategy", "1995-11-03"),
    ("NIFTY50 USD", "NON OPEN SOURCE", "Strategy", "1995-11-03"),
    ("NIFTY100 EQUAL WEIGHT", "NIFTY100 EQL WGT", "Strategy", "2003-01-01"),
    ("NIFTY ALPHA 50", "NIFTY ALPHA 50", "Strategy", "2003-12-31"),
    ("NIFTY HIGH BETA 50", "NIFTY HIGH BETA 50", "Strategy", "2003-12-31"),
    ("NIFTY LOW VOLATILITY 50", "NIFTY LOW VOLATILITY 50", "Strategy", "2003-12-31"),
    ("NIFTY 50 FUTURES PR", "NON OPEN SOURCE", "Strategy", "2005-04-01"),
    ("NIFTY 50 FUTURES TR", "NIFTY 50 FUTURES TR INDEX", "Strategy", "2005-04-01"),
    ("NIFTY ALPHA LOW-VOLATILITY 30", "NIFTY ALPHALOWVOL", "Strategy", "2005-04-01"),
    ("NIFTY ALPHA QUALITY LOW-VOLATILITY 30", "NIFTY ALPHA QUALITY LOW-VOLATILITY 30", "Strategy", "2005-04-01"),
    ("NIFTY ALPHA QUALITY VALUE LOW-VOLATILITY 30", "NIFTY ALPHA QUALITY VALUE LOW-VOLATILITY 30", "Strategy", "2005-04-01"),
    ("NIFTY HIGH DIVIDEND YIELD 15", "NIFTY HIGH DIVIDEND YIELD 15", "Strategy", "2005-04-01"),
    ("NIFTY MIDCAP150 MOMENTUM 50", "NIFTY MIDCAP150 MOMENTUM 50", "Strategy", "2005-04-01"),
    ("NIFTY MIDCAP150 QUALITY 50", "NIFTY M150 QLTY50", "Strategy", "2005-04-01"),
    ("NIFTY MIDSMALLCAP400 MOMENTUM QUALITY 100", "NIFTY MIDSMALLCAP400 MOMENTUM QUALITY 100", "Strategy", "2005-04-01"),
    ("NIFTY QUALITY LOW-VOLATILITY 30", "NIFTY QUALITY LOW-VOLATILITY 30", "Strategy", "2005-04-01"),
    ("NIFTY SMALLCAP250 MOMENTUM QUALITY 100", "NIFTY SMALLCAP250 MOMENTUM QUALITY 100", "Strategy", "2005-04-01"),
    ("NIFTY SMALLCAP250 QUALITY 50", "NIFTY SML250 Q50", "Strategy", "2005-04-01"),
    ("NIFTY TOTAL MARKET MOMENTUM QUALITY 50", "NIFTY TOTAL MARKET MOMENTUM QUALITY 50", "Strategy", "2005-04-01"),
    ("NIFTY100 ALPHA 30", "NIFTY100 ALPHA 30", "Strategy", "2005-04-01"),
    ("NIFTY100 LOW VOLATILITY 30", "NIFTY100 LOWVOL30", "Strategy", "2005-04-01"),
    ("NIFTY200 ALPHA 30", "NIFTY200 ALPHA 30", "Strategy", "2005-04-01"),
    ("NIFTY200 MOMENTUM 30", "NIFTY200MOMENTM30", "Strategy", "2005-04-01"),
    ("NIFTY200 QUALITY 30", "NIFTY200 QUALITY 30", "Strategy", "2005-04-01"),
    ("NIFTY200 VALUE 30", "NIFTY200 VALUE 30", "Strategy", "2005-04-01"),
    ("NIFTY500 EQUAL WEIGHT", "NIFTY500 EQUAL WEIGHT", "Strategy", "2005-04-01"),
    ("NIFTY500 GROWTH 50", "NIFTY500 GROWTH 50", "Strategy", "2005-04-01"),
    ("NIFTY500 LOW VOLATILITY 50", "NIFTY500 LOWVOL50", "Strategy", "2005-04-01"),
    ("NIFTY500 MOMENTUM 50", "NIFTY500 MOMENTUM 50", "Strategy", "2005-04-01"),
    ("NIFTY500 MULTICAP MOMENTUM QUALITY 50", "NIFTY500 MULTICAP MOMENTUM QUALITY 50", "Strategy", "2005-04-01"),
    ("NIFTY500 MULTIFACTOR MQVLV 50", "NIFTY500 MQVLV50", "Strategy", "2005-04-01"),
    ("NIFTY500 QUALITY 50", "NIFTY500 QLTY50", "Strategy", "2005-04-01"),
    ("NIFTY500 VALUE 50", "NIFTY500 VALUE 50", "Strategy", "2005-04-01"),
    ("NIFTY TOP 10 EQUAL WEIGHT", "NIFTY TOP 10 EQUAL WEIGHT", "Strategy", "2006-03-02"),
    ("NIFTY TOP 15 EQUAL WEIGHT", "NIFTY TOP 15 EQUAL WEIGHT", "Strategy", "2006-03-02"),
    ("NIFTY TOP 20 EQUAL WEIGHT", "NIFTY TOP 20 EQUAL WEIGHT", "Strategy", "2006-03-02"),
    ("NIFTY DIVIDEND OPPORTUNITIES 50", "NIFTY DIV OPPS 50", "Strategy", "2007-10-01"),
    ("NIFTY GROWTH SECTORS 15", "NIFTY GROWSECT 15", "Strategy", "2009-01-01"),
    ("NIFTY50 VALUE 20", "NIFTY50 VALUE 20", "Strategy", "2009-01-01"),
    ("NIFTY50 PR 1X INVERSE", "NON OPEN SOURCE", "Strategy", "2009-04-02"),
    ("NIFTY50 PR 2X LEVERAGE", "NON OPEN SOURCE", "Strategy", "2009-04-02"),
    ("NIFTY50 TR 1X INVERSE", "NON OPEN SOURCE", "Strategy", "2009-04-02"),
    ("NIFTY50 TR 2X LEVERAGE", "NON OPEN SOURCE", "Strategy", "2009-04-02"),
    ("NIFTY100 QUALITY 30", "NIFTY100 QUALTY30", "Strategy", "2009-10-01"),
    ("NIFTY500 FLEXICAP QUALITY 30", "NIFTY500 FLEXICAP QUALITY 30", "Strategy", "2009-10-01"),
    ("NIFTY 50 ARBITRAGE", "NON OPEN SOURCE", "Strategy", "2010-04-01"),
]
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
CREATE TABLE IF NOT EXISTS bench_history (index_name TEXT NOT NULL, bdate TEXT NOT NULL, value REAL NOT NULL,
  PRIMARY KEY (index_name, bdate)) WITHOUT ROWID;
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
    """Reads both AMFI layouts:
       new (2026): code;isin;isin;Scheme Name;Plan;Option;NAV;Date
       old:        code;isin;isin;Scheme Name;NAV;Date
    Data rows sit under section-header lines (type + category) and AMC-name lines."""
    lines = text.replace("\r", "").split("\n")
    first = next((l for l in lines if l.strip()), "")
    header = [h.strip().lower() for h in first.split(";")]
    if "scheme code" not in first.lower() or "net asset value" not in first.lower():
        raise ValueError("NAVAll.txt format not recognised (AMFI may have changed it). "
                         f"First line: {first[:100]!r}")
    has_plan_cols = "plan" in header and "option" in header
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
            if has_plan_cols and len(p) >= 8:
                name, plan, option = ";".join(p[3:-4]).strip(), p[-4].strip(), p[-3].strip()
                full = " - ".join(x for x in (name, plan, option) if x)
            else:
                full = ";".join(p[3:-2]).strip()
            out.append(dict(scheme_code=int(p[0]), scheme_name=full,
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


_PLANOPT = re.compile(r"\b(direct|dir|regular|reg|plan|growth|option|opt|gr|g|cumulative|cum|retail|institutional)\b", re.I)


def _only_planopt(text):
    return not re.sub(r"[\s\-–()/.,]", "", _PLANOPT.sub("", text))


def clean_name(name):
    """'HDFC Flexi Cap Fund - Growth Option - Direct Plan' -> 'HDFC Flexi Cap Fund'"""
    s = re.sub(r"\s*\(existing number of segregated portfolios?[^)]*\)", "", name or "", flags=re.I)
    s = re.sub(r"\(([^)]*)\)", lambda m: "" if _only_planopt(m.group(1)) else m.group(0), s)
    keep = [p for p in (x.strip() for x in re.split(r"\s*[-–]\s*", s)) if p and not _only_planopt(p)]
    if not keep:
        return (name or "").strip()
    out = " - ".join(keep)
    out = re.sub(r"(\s+(direct|regular)(\s+plan)?(\s+growth(\s+(plan|option))?)?)+\s*$", "", out, flags=re.I)
    out = re.sub(r"\s+(growth(\s+(plan|option))?)\s*$", "", out, flags=re.I)
    return re.sub(r"\s{2,}", " ", out).strip(" -")


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
    lname = re.sub(r"\(existing number of segregated portfolios?[^)]*\)", "", name.lower())
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




# ======================= 3b. BENCHMARK INDICES (NSE TRI) =======================
NIFTY_TRI_URLS = ["https://www.niftyindices.com/Backpage/getTotalReturnIndexString",
                  "https://www.niftyindices.com/Backpage.aspx/getTotalReturnIndexString"]
NIFTY_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36",
    "Referer": "https://www.niftyindices.com/reports/historical-data",
    "Origin": "https://www.niftyindices.com",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=UTF-8",
}


def benchmark_for(asset_class, category):
    """Index name for a category, or None (benchmarks are mapped for Equity only)."""
    if (asset_class or "").lower() != "equity":
        return None
    for k, v in BENCHMARKS.items():
        if k.lower() == (category or "").strip().lower():
            return v
    return EQUITY_DEFAULT_BENCHMARK


_IDX = {n: (api, grp, base) for n, api, grp, base in NSE_INDICES}


def all_benchmarks():
    return list(_IDX) + sorted((set(BENCHMARKS.values()) | {EQUITY_DEFAULT_BENCHMARK}) - set(_IDX))


def api_name(index):
    return _IDX.get(index, (index,))[0]


_KEEP_UPPER = {"IT", "PSE", "PSU", "MNC", "FMCG", "CPSE", "ESG", "USD", "EV", "REITS", "INVITS", "SME", "BHARAT", "IPO", "AAA", "AA", "PR", "TR", "MAATR", "BFSI"}


def bench_label(index_name):
    words = [w if (w in _KEEP_UPPER or any(ch.isdigit() for ch in w) and not w.startswith("NIFTY")) else w.capitalize()
             for w in index_name.split()]
    return " ".join(words).replace("Nifty50", "Nifty50").replace("Nifty100", "Nifty100").replace("Nifty200", "Nifty200").replace("Nifty500", "Nifty500") + " TRI"


def _nifty_session():
    try:                                   # cloudscraper copes with Cloudflare checks if it is installed
        import cloudscraper
        s = cloudscraper.create_scraper()
    except Exception:
        s = requests.Session()
    s.headers.update(NIFTY_HEADERS)
    try:
        s.get("https://www.niftyindices.com/reports/historical-data", timeout=30)   # picks up cookies
    except Exception:
        pass
    return s


def _parse_tri(rows):
    out = []
    for r in rows:
        keys = {k.lower().replace(" ", "").replace("_", ""): k for k in r}
        dk = keys.get("date") or keys.get("historicaldate")
        vk = next((keys[k] for k in keys if "totalreturn" in k and "net" not in k), None)
        if not dk or not vk:
            continue
        d = None
        for fmt in ("%d %b %Y", "%d-%b-%Y", "%d %B %Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                d = datetime.strptime(str(r[dk]).strip(), fmt).date()
                break
            except ValueError:
                continue
        try:
            v = float(str(r[vk]).replace(",", ""))
        except ValueError:
            continue
        if d and v > 0:
            out.append((d.isoformat(), v))
    return out


def fetch_tri(sess, index, start, end):
    """Daily TRI values for one index between two dates (inclusive)."""
    api = api_name(index)
    payload = json.dumps({"cinfo": json.dumps({"name": api, "startDate": start.strftime("%d-%b-%Y"),
                                               "endDate": end.strftime("%d-%b-%Y"), "indexName": api})})
    last = None
    for url in NIFTY_TRI_URLS:
        try:
            r = sess.post(url, data=payload, timeout=60)
            if r.status_code != 200:
                last = f"HTTP {r.status_code} from {url}"
                continue
            j = r.json()
            if isinstance(j, dict) and "d" in j:
                j = json.loads(j["d"]) if isinstance(j["d"], str) else j["d"]
            if isinstance(j, list):
                return _parse_tri(j)
            last = f"unexpected response from {url}: {str(j)[:120]}"
        except ValueError:
            last = f"{url} did not return data (probably a 'checking your browser' page - site is blocking automated access)"
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:150]}"
    raise RuntimeError(last)


def _download_index(index, last):
    """Runs in a worker thread: fetch one index from its last stored date (or the start) up to today."""
    sess, today = _nifty_session(), date.today()
    base = pd.Timestamp(_IDX.get(index, (None, None, BENCHMARK_HISTORY_FROM))[2])
    first = max(base, pd.Timestamp(BENCHMARK_HISTORY_FROM)).date()
    cur = (pd.Timestamp(last) - pd.Timedelta(days=10)).date() if last else first
    rows, err = [], None
    while cur <= today:                                      # one year per request
        chunk_end = min((pd.Timestamp(cur) + pd.Timedelta(days=364)).date(), today)
        try:
            rows += fetch_tri(sess, index, cur, chunk_end)
        except Exception as e:
            err = str(e)
            break
        cur = (pd.Timestamp(chunk_end) + pd.Timedelta(days=1)).date()
        time.sleep(0.4)
    return index, rows, err


def step_benchmarks(con):
    """Keep bench_history up to date for all NSE equity TRIs. Never stops the run: on failure old data is kept,
    and an interrupted first download continues from where it stopped next time."""
    names = all_benchmarks()
    last = dict(con.execute("SELECT index_name, MAX(bdate) FROM bench_history GROUP BY index_name").fetchall())
    todo = len([n for n in names if n not in last])
    log.info("Updating %d NSE indices%s ...", len(names),
             f" (first download of {todo} indices takes a while; it resumes if interrupted)" if todo > 20 else "")
    ok, failed = [], []
    with ThreadPoolExecutor(max_workers=BENCHMARK_WORKERS) as ex:
        futs = [ex.submit(_download_index, n, last.get(n)) for n in names]
        for i, fut in enumerate(as_completed(futs), 1):
            index, rows, err = fut.result()
            if rows:
                con.executemany("INSERT INTO bench_history VALUES (?,?,?) ON CONFLICT(index_name, bdate) DO UPDATE SET value=excluded.value",
                                [(index, d, v) for d, v in rows])
                con.commit()
            (failed if err else ok).append(index)
            if err and len(failed) <= 3:
                log.warning("  index %s: download problem (%s)", index, err)
            if i % 25 == 0 or i == len(names):
                log.info("  indices: %d / %d done (%d with problems)", i, len(names), len(failed))
    for index in sorted(set(BENCHMARKS.values()) | {EQUITY_DEFAULT_BENCHMARK}):
        lt = con.execute("SELECT MAX(bdate), COUNT(*) FROM bench_history WHERE index_name=?", (index,)).fetchone()
        log.info("Benchmark %s TRI: %d values, latest %s", index, lt[1], lt[0])
    if failed:
        log.warning("%d indices could not be updated this time (stored data kept; retried next run).", len(failed))
    log_run(con, "benchmarks", "ok" if not failed else "partial", None, f"ok={len(ok)} failed={len(failed)}")


def bench_test():
    """python mf_update.py --bench-test : quick check that niftyindices.com answers from this computer."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sess = _nifty_session()
    end = date.today()
    for index in sorted(set(BENCHMARKS.values()) | {EQUITY_DEFAULT_BENCHMARK}) + ["NIFTY BANK", "NIFTY IT", "NIFTY SMALLCAP 100"]:
        try:
            rows = sorted(fetch_tri(sess, index, end - pd.Timedelta(days=30), end))
            print(f"OK    {index:20s} {len(rows)} values, newest {rows[-1] if rows else '-'}")
        except Exception as e:
            print(f"FAIL  {index:20s} {e}")


# ======================= 4. RETURN CALCULATIONS =======================
# The dashboard recalculates everything in the browser for any as-on date; these Python
# versions produce Fund_Returns.csv and are the reference the browser maths is tested against.
# Rules: holiday -> last NAV on or before the date
#        1W..1Y and YTD: absolute | longer periods: CAGR = (NAV1/NAV0) ** (365/days) - 1
#        fund younger than the period -> blank
PERIOD_OFFSETS = {"1W": dict(weeks=1), "1M": dict(months=1), "3M": dict(months=3), "6M": dict(months=6),
                  "1Y": dict(years=1), "2Y": dict(years=2), "3Y": dict(years=3), "5Y": dict(years=5),
                  "7Y": dict(years=7), "10Y": dict(years=10)}
ABSOLUTE_PERIODS = {"1W", "1M", "3M", "6M", "YTD", "1Y"}


def nav_on_or_before(s, d):
    i = s.index.searchsorted(pd.Timestamp(d), side="right") - 1
    return (s.index[i], float(s.iloc[i])) if i >= 0 else (None, None)


def cagr(r, days):
    return (1 + r) ** (DAYS_IN_YEAR / days) - 1


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
    if days <= 0:
        return None
    r = n1 / n0 - 1
    return r if (period in ABSOLUTE_PERIODS or days <= DAYS_IN_YEAR) else cagr(r, days)


def calendar_returns(s, as_of):
    """Full calendar years {year: r}: last NAV of year / last NAV of previous year - 1."""
    full, prev = {}, None
    for d, v in s.resample("YE").last().dropna().items():
        if d.year >= pd.Timestamp(as_of).year:
            break
        if prev is None:
            if (d - s.index[0]).days >= 7 and s.index[0] <= pd.Timestamp(d.year - 1, 12, 31) + pd.Timedelta(days=7):
                full[d.year] = v / float(s.iloc[0]) - 1
        else:
            full[d.year] = v / prev - 1
        prev = v
    return full


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
PLAN_CODE = {"Direct": "D", "Regular": "R"}


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
    funds, cats, csv, inactive = [], {}, [], set()

    for (cat_id, plan), g in schemes.groupby(["category_id", "plan"]):
        pc = PLAN_CODE.get(plan)
        if pc is None:
            continue
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

        for c in active:
            s = panel[c].dropna()
            m = meta.loc[c]
            name = clean_name(m["scheme_name"])
            funds.append({"c": int(c), "n": name, "fn": m["scheme_name"], "amc": m["amc"], "cat": cat_id, "pl": pc,
                          "inc": s.index[0].date().isoformat(), "last": s.index[-1].date().isoformat(),
                          "nav": _n(s.iloc[-1], 4)})
            tr = {p: trailing_return(s, as_of, p) for p in TRAILING_PERIODS}
            cy = calendar_returns(s, as_of)
            csv.append({"Scheme Code": int(c), "Fund": name, "Plan": plan, "AMC": m["amc"], "Asset Class": ac,
                        "Category": cat_name, "Inception": s.index[0].date(), "NAV Date": s.index[-1].date(),
                        "NAV": round(s.iloc[-1], 4),
                        **{f"{p} %": (None if v is None else round(v * 100, 2)) for p, v in tr.items()},
                        **{f"CY{y} %": round(v * 100, 2) for y, v in sorted(cy.items(), reverse=True)[:10]}})

        fname = f"{cat_id}__{pc.lower()}.json"
        _write_json(nav_dir / fname, {
            "id": cat_id, "plan": pc, "name": cat_name, "ac": ac, "as_of": as_of_s,
            "dates": [d.date().isoformat() for d in panel.index],
            "series": {str(int(c)): [_n(v, 4) for v in panel[c].to_numpy()] for c in active},
            "cat_avg": [_n(v, 4) for v in category_average(panel)]})
        cat = cats.setdefault(cat_id, {"id": cat_id, "name": cat_name, "ac": ac, "n": {}, "files": {}, "bench": benchmark_for(ac, cat_name)})
        cat["n"][pc] = len(active)
        cat["files"][pc] = f"nav/{fname}"

    con.execute("UPDATE schemes SET status='active' WHERE in_universe=1")
    con.executemany("UPDATE schemes SET status='inactive' WHERE scheme_code=?", [(c,) for c in inactive])
    con.commit()
    cat_list = sorted(cats.values(), key=lambda c: (c["ac"], c["name"]))
    # benchmark series files
    bdir = DATA / "bench"
    bdir.mkdir(exist_ok=True)
    benches, idx_csv = [], []
    for index in all_benchmarks():
        b = pd.read_sql_query("SELECT bdate, value FROM bench_history WHERE index_name=? AND bdate<=? ORDER BY bdate",
                              con, params=(index, as_of_s))
        if b.empty:
            continue
        bid = re.sub(r"[^a-z0-9]+", "_", index.lower()).strip("_")
        _write_json(bdir / f"{bid}.json", {"id": index, "label": bench_label(index), "dates": b["bdate"].tolist(),
                                            "values": [round(float(v), 4) for v in b["value"]]})
        benches.append({"id": index, "label": bench_label(index), "file": f"bench/{bid}.json",
                        "group": _IDX.get(index, (None, "Broad market"))[1],
                        "first": b["bdate"].iloc[0], "last": b["bdate"].iloc[-1]})
        s = pd.Series(b["value"].to_numpy(), index=pd.to_datetime(b["bdate"]))
        tr = {p: trailing_return(s, as_of, p) for p in TRAILING_PERIODS}
        idx_csv.append({"Index": bench_label(index), "Group": _IDX.get(index, (None, "Broad market"))[1],
                    "First value": s.index[0].date(), "Value date": s.index[-1].date(), "Value": round(s.iloc[-1], 2), **{f"{p} %": (None if v is None else round(v * 100, 2)) for p, v in tr.items()},
                    **{f"CY{y} %": round(v * 100, 2) for y, v in sorted(calendar_returns(s, as_of).items(), reverse=True)[:10]}})
    have = {b["id"] for b in benches}
    for c in cat_list:
        if c.get("bench") not in have:
            c["bench"] = None
    if not benches:
        log.warning("No benchmark data available yet - the dashboard will compare with category averages only.")
    _write_json(DATA / "summary.json", {
        "version": 2, "as_of": as_of_s, "generated_at": datetime.now().isoformat(timespec="seconds"),
        "periods": TRAILING_PERIODS, "days_in_year": DAYS_IN_YEAR,
        "asset_classes": sorted({c["ac"] for c in cat_list}),
        "categories": cat_list, "funds": funds, "inactive_count": len(inactive), "benchmarks": benches})
    try:
        pd.DataFrame(csv).to_csv(DATA / "Fund_Returns.csv", index=False)
        if idx_csv:
            pd.DataFrame(idx_csv).to_csv(DATA / "Index_Returns.csv", index=False)
    except PermissionError:
        log.warning("Fund_Returns.csv / Index_Returns.csv is open in Excel - close it to let it update next time.")
    msg = f"{len(funds)} funds in {len(cat_list)} categories ({len(inactive)} closed/merged skipped)"
    log_run(con, "build", "ok", as_of_s, msg)
    log.info("Returns ready: %s in %.0fs", msg, time.time() - t0)


# ======================= DEMO (works offline) =======================
def make_demo_navall(seed=7):
    """Synthetic AMFI-format file + history (Direct and Regular plans) to try everything offline."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2012-01-02", pd.Timestamp(date.today()) - pd.offsets.BDay(1))
    mkt = rng.normal(0.13 / 252, 0.17 / np.sqrt(252), len(days))
    cats = [("Equity Scheme - Large Cap Fund", 10, 0.12, 0.16, 0.95), ("Equity Scheme - Mid Cap Fund", 10, 0.16, 0.21, 1.15),
            ("Equity Scheme - Small Cap Fund", 8, 0.18, 0.25, 1.25), ("Equity Scheme - Flexi Cap Fund", 10, 0.14, 0.18, 1.0),
            ("Hybrid Scheme - Aggressive Hybrid Fund", 6, 0.11, 0.12, 0.7), ("Debt Scheme - Liquid Fund", 6, 0.065, 0.004, 0)]
    amcs = ["Alpha", "Bharat", "Coastal", "Deccan", "Everest", "Ganga", "Himalaya", "Indus", "Jaipur", "Kaveri"]
    styles = ["{n} - Direct Plan - Growth", "{n} - Growth Option - Direct Plan", "{n}-Direct Plan-Growth", "{n} Direct Growth"]
    lines = ["Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date", ""]
    hist, code = [], 900001
    for sec, k, mu, vol, beta in cats:
        lines += [f"Open Ended Schemes({sec})", ""]
        for i in range(k):
            st = 0 if i < k - 3 else int(rng.integers(len(days) // 3, len(days) - 300))
            if beta:
                r = beta * mkt + rng.normal((mu - beta * 0.13) / 252, vol * 0.5 / np.sqrt(252), len(days))
            else:
                r = rng.normal(mu / 252, vol / np.sqrt(252), len(days))
            nav_d = 10 * np.cumprod(1 + r[st:])
            nav_r = 10 * np.cumprod(1 + r[st:] - 0.009 / 252)          # regular plan: ~0.9% higher expense
            base = f"{amcs[i]} {sec.split(' - ')[1]}"
            lines.append(f"{amcs[i]} Mutual Fund")
            for nav, cd, plan in ((nav_d, code, "Direct"), (nav_r, code + 50000, "Regular")):
                opt = ["Growth", "Growth Option", "GROWTH", "Direct Growth"][i % 4].replace("Direct", plan)
                lines.append(f"{cd};INFDEMO{cd};-;{base};{plan} Plan;{opt};{nav[-1]:.4f};{days[-1]:%d-%b-%Y}")
                hist += [(cd, d.date().isoformat(), float(v)) for d, v in zip(days[st:], nav)]
            lines.append("")
            code += 1
    bench = {}
    for name, beta, alpha in (("NIFTY 100", 0.95, -0.005), ("NIFTY MIDCAP 150", 1.15, 0.02), ("NIFTY SMALLCAP 250", 1.25, 0.01), ("NIFTY 500", 1.0, 0.0),
                              ("NIFTY 50", 0.93, -0.01), ("NIFTY BANK", 1.1, 0.0), ("NIFTY IT", 0.8, 0.02), ("NIFTY PHARMA", 0.6, 0.01),
                              ("NIFTY FMCG", 0.5, 0.0), ("NIFTY INDIA CONSUMPTION", 0.8, 0.01), ("NIFTY PSE", 1.2, 0.0),
                              ("NIFTY ALPHA 50", 1.2, 0.04), ("NIFTY LOW VOLATILITY 50", 0.7, 0.01)):
        br = beta * mkt + alpha / 252 + rng.normal(0, 0.002, len(days))
        bench[name] = [(d.date().isoformat(), float(v)) for d, v in zip(days, 10000 * np.cumprod(1 + br))]
    return "\n".join(lines), hist, bench


# ======================= RUN =======================
def main():
    if "--bench-test" in sys.argv:
        bench_test()
        return
    DATA.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%H:%M:%S",
                        handlers=[logging.StreamHandler(sys.stdout),
                                  logging.FileHandler(DATA / "update_log.txt", encoding="utf-8")])
    demo = "--demo" in sys.argv
    con = db_connect(DATA / "demo.db" if demo else DB_PATH)
    try:
        if demo:
            log.info("DEMO MODE: synthetic funds, no internet needed")
            text, hist, bench = make_demo_navall()
            step_daily(con, text)
            save_navs(con, hist)
            for name, rows in bench.items():
                con.executemany("INSERT OR REPLACE INTO bench_history VALUES (?,?,?)", [(name, d, v) for d, v in rows])
            con.executemany("INSERT OR REPLACE INTO history_done VALUES (?, 'done', 0, '')",
                            [(c,) for c in {h[0] for h in hist}])
            con.commit()
        else:
            gapped = step_daily(con, get_navall_text())
            step_history(con, gapped)
            step_benchmarks(con)
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
