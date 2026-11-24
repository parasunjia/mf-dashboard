# Mutual Fund Performance Dashboard

Self-updating dashboard of Indian mutual fund returns (Direct plan, Growth option).

* **Data:** daily NAVs from AMFI (NAVAll.txt); NAV history from api.mfapi.in (the source mftool uses)
* **Updates:** automatically every weekday night via GitHub Actions (`.github/workflows/update.yml`)
* **Views:** category rankings with quartiles · compare up to 8 funds over any period · fund details with monthly heatmap and rolling returns

## Files
| File | What it does |
|---|---|
| `mf_update.py` | Downloads NAVs, cleans the data, calculates returns, writes the files the page reads |
| `index.html` | The dashboard (runs in the browser) |
| `.github/workflows/update.yml` | Runs `mf_update.py` every night and publishes the result |
| `requirements.txt` | Python libraries needed |

## Return conventions
Up to 1 year: absolute. Above 1 year: CAGR, (NAV₁/NAV₀)^(365.25/days) − 1. Holidays use the previous NAV.
Funds younger than a period show "–". Category average = equal-weighted index of current funds.

*Past performance is not a guide to future returns. Not investment advice.*
