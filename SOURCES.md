# Data sources

## Department of Census and Statistics, Sri Lanka

**Weekly Retail Prices for Selected Consumer Items - Colombo District**

Official index: https://www.statistics.gov.lk/InflationAndPrices/StaticalInformation/RetailPrices

Downloaded on 23 November 2026, Asia/Colombo. This is the primary dataset used by the application.

The full development workspace retains 325 original PDF reports under `data/raw/dcs/`. The compact source archive excludes these original PDFs; use `scripts/download_dcs.py` to restore them if re-extracting prices. Training and inference can run offline from the included processed CSV. Each file's URL, download status and SHA-256 checksum are in `manifest.json`. The captured index page is `index.html`. Of 418 distinct archive links checked, 93 did not return a usable PDF during download. This is an availability observation, not proof that DCS never published those reports.

Example source reports:

- First available in this snapshot: https://www.statistics.gov.lk/Resource/en/InflationAndPrices/retail/DCSB-WRP-2019-12-W4.pdf
- Pre-holdout report: https://www.statistics.gov.lk/Resource/en/InflationAndPrices/retail/DCSB-WRP-2025-12-W4.pdf
- Latest downloaded report: https://www.statistics.gov.lk/Resource/en/InflationAndPrices/retail/DCSB-WRP-2026-11-W1.pdf

## Extraction

`scripts/prepare_dcs.py` reads the **current-week average price** column by its position inside the table's average-price block. It does not infer the current price by counting tokens, which could shift when an earlier-year value is missing. The earlier-year average, previous-week comparison column, percent changes and min/max ranges are not used as current targets.

The processed file `data/processed/dcs_weekly_prices.csv` contains 6,495 positive price observations for 20 food series. Each row retains the original report filename, page and URL. Units are LKR/kg. Report-period labels come from each source filename, and extraction retains one price per food and reporting period. `extraction_summary.json` records row counts and parsing failures.

Food definitions remain source-specific. For example, red rice is DCS's “Raw Red - (Average)”, lentils are “Mysore Dhall - (Average)”, and tomatoes are “Tomatoe - No 1.” Local and imported potatoes are distinct series; imported big onions are not mixed with red onions. The dataset covers Colombo district market averages, not separate observations for every market or an official population-weighted national index.

DCS labels four reporting periods per month. The program uses a 48-slot annual index. Dates displayed internally as 1/8/15/22 encode these labels only; they are not claimed to be exact collection dates. Missing reports and missing prices stay missing. Any training example without the required past features is excluded.

Extracted coverage: December 2019 W4 to November 2026 W1. Complete training targets: February 2020 W4 to December 2025 W4, 5,031 rows. Held-out 2026 targets: January W1 to November W1, 820 rows.

Original publications are credited to the Department of Census and Statistics. No CC BY-IGO license is claimed for these DCS reports. Their public availability is not treated as evidence of a specific redistribution license; retain DCS attribution and consult the publisher's terms before wider republication. The repository snapshot is for this educational project.

This is a retrospective downloaded snapshot. Historical publication vintages and collection microdata are not available here. Source revisions, changing market coverage and extraction errors remain possible. Future model outputs are estimates, not DCS statistics.

## Technical references

- Scikit-learn, ensemble methods: https://scikit-learn.org/stable/modules/ensemble.html
- XGBoost Python API: https://xgboost.readthedocs.io/en/stable/python/python_api.html
- FastAPI: https://fastapi.tiangolo.com/
- React: https://react.dev/
- Recharts: https://recharts.github.io/

The notebook and `AI_USAGE.md` acknowledge the assistance used to implement the project.
