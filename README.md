# Food Lens

**Essential Food Price Movement Prediction**  
Machine Learning and Pattern Recognition  
**Nivethan R. | 224138H**

A React and FastAPI dashboard comparing bagging, boosting and stacking on Sri Lankan food-price movements.

## Run locally

Use Python 3.12 and Node.js 22.12 or newer.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci --prefix frontend
./scripts/start.sh
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**. If dependencies are already installed, run only the last command. Stop both services with Control-C.

On macOS, XGBoost may need `brew install libomp` if it reports a missing OpenMP library. On Windows, use `.venv\Scripts\python` instead of `.venv/bin/python` and run the two services in separate terminals:

```bash
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm run dev --prefix frontend -- --port 5173 --strictPort
```

The saved models and processed dataset are included. An initial run does not require downloading data or training again. Vite proxies `/api` to FastAPI; a frontend build alone does not provide the backend.

## Dataset and evaluation

Source: **Department of Census and Statistics (DCS), Sri Lanka**, weekly retail-price reports for main markets in Colombo district. See [SOURCES.md](SOURCES.md).

- 6,495 reported prices across 20 food series, in LKR/kg.
- Source coverage: December 2019 W4 to November 2026 W1, from 325 reports.
- Training: 5,031 complete examples, February 2020 W4 to December 2025 W4.
- Holdout: 820 comparisons, January 2026 W1 to November 2026 W1.

DCS uses four reporting periods per month. W1/W2/W3/W4 are encoded as days 1/8/15/22 for plotting; they are not exact collection dates or ISO calendar weeks. Missing reports and prices stay missing. Examples without required lag features are excluded.

## Methods and results

Bagging uses a 120-tree random forest. Boosting uses XGBoost with 140 shallow trees. Stacking uses random forest, XGBoost and ridge as base learners, with a ridge combiner fitted on three chronological validation folds. All methods use the same past-only features and holdout observations. Settings are fixed with seed 42; no 2026 outcomes tune them.

| Model | MAE (LKR/kg) | RMSE (LKR/kg) | MAPE | Direction |
|---|---:|---:|---:|---:|
| Random forest | 19.05 | 38.80 | 3.98% | 54.88% |
| XGBoost | 18.77 | 38.95 | 3.92% | 54.51% |
| Temporal stacking | 18.75 | 38.93 | 4.00% | 54.63% |
| Previous-report baseline | 19.00 | 42.31 | 3.93% | 0.00% |

Stacking has the lowest MAE, about 1.3% below persistence. Random forest has the lowest ensemble RMSE and highest direction score; XGBoost has the lowest MAPE. The differences are small and descriptive, without a statistical significance claim. Direction uses the exact sign of change; persistence always predicts unchanged.

## Dashboard

- **Overview:** price curves, food filters, baseline comparison and metrics.
- **Models:** full metric names and explanations; direct model-comparison bars for Mean Absolute Error (MAE), Root Mean Squared Error (RMSE), Mean Absolute Percentage Error (MAPE) and Direction Accuracy; linked per-food comparisons and feature diagnostics.
- **Prediction lab - known prices:** frozen pre-2026 models compared with recorded 2026 outcomes, including a compact bar chart. Earlier observed 2026 prices may become inputs for later predictions; models are not refitted on holdout targets.
- **Prediction lab - future prices:** separate models fitted on all available observations. Each method recursively uses its own previous estimates for later steps. Unpublished intervening periods are estimated too. Future actuals and accuracy are unknown; the horizon is capped at 12 reporting steps.
- **Data:** source, chronology, stacking folds and limitations. CSV export uses the selected food filter.

## Project structure

```text
frontend/                 React application and npm lockfile
backend/app/              FastAPI endpoints and shared ML implementation
backend/artifacts/        Evaluation models, future models and held-out predictions
data/processed/           Extracted prices with row-level provenance and lag features
data/raw/dcs/             Source manifest, captured index and extraction summary
notebooks/                Executed training and evaluation notebook
scripts/                  Data import, launch and notebook helpers
SOURCES.md                Dataset provenance and technical references
AI_USAGE.md               Contribution acknowledgement
```

The compact source archive includes processed data and provenance, while excluding the 170 MB of original report PDFs, installed dependencies and caches. Original PDFs are retained in the development workspace and can also be retrieved with the downloader. Offline training and inference use the included processed CSV. Re-extracting prices requires the PDFs.

## Reproduce

Open `notebooks/food_price_ensembles.ipynb` and select the project's `.venv` interpreter. The notebook contains the full implementation and saved results.

```bash
.venv/bin/python -m backend.app.ml
.venv/bin/python scripts/execute_notebook.py
npm run build --prefix frontend
```

To refresh the source data, run `scripts/download_dcs.py` followed by `scripts/prepare_dcs.py`, then retrain. A refresh can change coverage and results. If editing `backend/app/ml.py`, regenerate notebook source with `scripts/build_notebook.py` before executing it; regeneration clears its saved outputs.

The application uses separate evaluation and forecast model artifacts. Load only trusted joblib files with the pinned Python packages. Source revisions, extraction errors, changing market conditions and missing external drivers limit the results; future paths have no calibrated prediction intervals.
