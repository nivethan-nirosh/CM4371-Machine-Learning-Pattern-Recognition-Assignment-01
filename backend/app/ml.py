from pathlib import Path
import hashlib
import json
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.inspection import permutation_importance
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / 'backend/artifacts'
DATA = ROOT / 'data/processed/dcs_weekly_prices.csv'
SOURCE_URL = 'https://www.statistics.gov.lk/InflationAndPrices/StaticalInformation/RetailPrices'
NUMERIC = ['lag_1', 'lag_2', 'lag_4', 'lag_8', 'mean_4', 'std_4', 'change_1', 'trend_4', 'season_sin', 'season_cos']
FEATURES = NUMERIC + ['commodity']
LABELS = {'bagging': 'Random forest', 'boosting': 'XGBoost', 'stacking': 'Temporal stacking', 'baseline': 'Previous report'}
MODEL_KEYS = ['bagging', 'boosting', 'stacking']
CUTOFF = '2026-01-01'


def slot_date(slot):
    year, remainder = divmod(int(slot), 48)
    month, week = divmod(remainder, 4)
    return pd.Timestamp(year=year, month=month + 1, day=1 + week * 7)


def period_label(slot):
    date = slot_date(slot)
    return f'{date:%Y-%m}-W{(date.day - 1) // 7 + 1}'


def load_panel():
    return pd.read_csv(DATA, parse_dates=['date']).sort_values(['slot', 'commodity']).reset_index(drop=True)


def make_features(panel, require_target=True):
    pieces = []
    for food, group in panel.groupby('commodity'):
        g = group.set_index('slot').reindex(range(int(group.slot.min()), int(group.slot.max()) + 1))
        g.index.name = 'slot'
        g['commodity'] = food
        g['date'] = [slot_date(s) for s in g.index]
        g['market'] = 'Colombo district'
        for lag in [1, 2, 4, 8]:
            g[f'lag_{lag}'] = g.price.shift(lag)
        past = g.price.shift(1)
        g['mean_4'] = past.rolling(4).mean()
        g['std_4'] = past.rolling(4).std()
        g['change_1'] = g.lag_1 / g.lag_2 - 1
        g['trend_4'] = g.lag_1 / g.lag_4 - 1
        season = (g.index % 48) / 48
        g['season_sin'], g['season_cos'] = np.sin(2 * np.pi * season), np.cos(2 * np.pi * season)
        g['target'] = g.price / g.lag_1 - 1
        pieces.append(g.reset_index())
    required = FEATURES + (['price', 'target'] if require_target else [])
    return pd.concat(pieces, ignore_index=True).dropna(subset=required).sort_values(['slot', 'commodity']).reset_index(drop=True)


def estimator(kind):
    prep = ColumnTransformer([
        ('numeric', StandardScaler(), NUMERIC),
        ('food', OneHotEncoder(handle_unknown='ignore', sparse_output=False), ['commodity'])
    ])
    if kind == 'bagging':
        model = RandomForestRegressor(n_estimators=120, max_depth=9, min_samples_leaf=5,
                                      max_features=0.8, bootstrap=True, random_state=42, n_jobs=2)
    elif kind == 'boosting':
        model = XGBRegressor(n_estimators=140, max_depth=3, learning_rate=0.035,
                             subsample=0.85, colsample_bytree=0.85, reg_lambda=8,
                             objective='reg:squarederror', random_state=42, n_jobs=2)
    else:
        model = Ridge(alpha=20)
    return make_pipeline(prep, model)


def fit_models(train):
    slots = np.array(sorted(train.slot.unique()))
    warmup = max(16, len(slots) // 3)
    folds, oof_x, oof_y = [], [], []
    started = time.perf_counter()
    # All foods in a reporting period stay in the same fold.
    for block in np.array_split(slots[warmup:], 3):
        before, valid = train.loc[train.slot < block[0]], train.loc[train.slot.isin(block)]
        predictions = []
        for kind in ['bagging', 'boosting', 'ridge']:
            m = estimator(kind).fit(before[FEATURES], before.target)
            predictions.append(m.predict(valid[FEATURES]))
        oof_x.append(np.column_stack(predictions))
        oof_y.append(valid.target.to_numpy())
        folds.append({'train_end': period_label(before.slot.max()), 'validation_start': period_label(valid.slot.min()),
                      'validation_end': period_label(valid.slot.max()), 'rows': len(valid)})
    meta = Ridge(alpha=1).fit(np.vstack(oof_x), np.concatenate(oof_y))
    stacking_fold_seconds = time.perf_counter() - started
    models, timings = {}, {}
    for kind in ['bagging', 'boosting', 'ridge']:
        start = time.perf_counter()
        models[kind] = estimator(kind).fit(train[FEATURES], train.target)
        timings[kind] = round(time.perf_counter() - start, 3)
    timings['stacking_folds'] = round(stacking_fold_seconds, 3)
    return {'models': models, 'meta': meta}, folds, timings


def predict_returns(bundle, rows):
    values = {k: m.predict(rows[FEATURES]) for k, m in bundle['models'].items()}
    values['stacking'] = bundle['meta'].predict(np.column_stack([values[k] for k in ['bagging', 'boosting', 'ridge']]))
    return values


def predict(bundle, rows):
    changes = predict_returns(bundle, rows)
    result = rows[['date', 'slot', 'commodity', 'market', 'price', 'lag_1']].rename(columns={'price': 'actual', 'lag_1': 'previous'}).copy()
    result['period'] = [period_label(s) for s in result.slot]
    for key in MODEL_KEYS:
        result[key] = np.maximum(0.01, result.previous.to_numpy() * (1 + changes[key]))
    result['baseline'] = result.previous
    return result


def metrics(rows):
    result = []
    actual_direction = np.sign(rows.actual - rows.previous)
    for key, name in LABELS.items():
        estimate = rows[key]
        result.append({'key': key, 'name': name, 'mae': float(mean_absolute_error(rows.actual, estimate)),
                       'rmse': float(np.sqrt(mean_squared_error(rows.actual, estimate))),
                       'mape': float(np.mean(np.abs((rows.actual - estimate) / rows.actual)) * 100),
                       'r2': float(r2_score(rows.actual, estimate)) if len(rows) > 1 else None,
                       'direction_accuracy': float(np.mean(np.sign(estimate - rows.previous) == actual_direction) * 100),
                       'bias': float(np.mean(estimate - rows.actual)), 'n': len(rows)})
    return result


def forecast(bundle, panel, food, steps):
    if not 1 <= steps <= 12:
        raise ValueError('Choose between 1 and 12 reporting steps.')
    history = panel.loc[panel.commodity == food, ['slot', 'commodity', 'price']].sort_values('slot').copy()
    if history.empty:
        raise ValueError('Unknown food.')
    origin = int(history.slot.max())
    histories = {key: history.copy() for key in MODEL_KEYS}
    predictions = []
    for step in range(1, steps + 1):
        slot = origin + step
        result = {'date': str(slot_date(slot).date()), 'period': period_label(slot), 'step': step,
                  'actual': None, 'baseline': float(history.price.iloc[-1])}
        for key in MODEL_KEYS:
            next_row = pd.DataFrame([{'slot': slot, 'commodity': food, 'price': np.nan}])
            expanded = pd.concat([histories[key], next_row], ignore_index=True)
            features = make_features(expanded, require_target=False)
            features = features.loc[features.slot == slot]
            if features.empty:
                raise ValueError('The latest reporting periods do not have the required lag history.')
            change = predict_returns(bundle, features)[key][0]
            price = max(0.01, float(features.lag_1.iloc[0] * (1 + change)))
            result[key] = price
            expanded.loc[expanded.slot == slot, 'price'] = price
            histories[key] = expanded
        predictions.append(result)
    recorded = history.tail(16)
    return {'commodity': food, 'origin': period_label(origin), 'origin_date': str(slot_date(origin).date()),
            'origin_price': float(history.price.iloc[-1]), 'rows': predictions,
            'history': [{'date': str(slot_date(r.slot).date()), 'period': period_label(r.slot), 'actual': r.price} for r in recorded.itertuples()],
            'warning': 'Recursive estimates from the latest available report. Earlier missing releases are also estimated; errors can grow with each step. Actual future prices and accuracy are unknown.'}


def feature_factors(bundle, test):
    factors = {}
    sample = test.sample(min(400, len(test)), random_state=42)
    for key in ['bagging', 'boosting']:
        importance = permutation_importance(bundle['models'][key], sample[FEATURES], sample.target,
                                            scoring='neg_mean_absolute_error', n_repeats=3, random_state=42)
        factors[key] = sorted([{'feature': feature, 'increase_in_return_mae': float(value)}
                               for feature, value in zip(FEATURES, importance.importances_mean)],
                              key=lambda r: r['increase_in_return_mae'], reverse=True)
    return factors


def train_and_export():
    ARTIFACTS.mkdir(exist_ok=True)
    panel = load_panel()
    rows = make_features(panel)
    train, test = rows.loc[rows.date < CUTOFF], rows.loc[rows.date >= CUTOFF]
    assert train.slot.max() < test.slot.min()
    bundle, folds, timings = fit_models(train)
    output = predict(bundle, test)
    future_bundle, future_folds, _ = fit_models(rows)
    manifest = json.loads((ROOT / 'data/raw/dcs/manifest.json').read_text())
    valid = [r for r in manifest['reports'] if r['status'] == 'downloaded']
    report = {
        'title': 'Essential Food Price Movement Prediction', 'currency': 'LKR', 'unit': 'kg',
        'source': 'Department of Census and Statistics, Sri Lanka', 'source_url': SOURCE_URL,
        'raw_sha256': hashlib.sha256(DATA.read_bytes()).hexdigest(), 'raw_rows': len(panel),
        'reports_downloaded': len(valid), 'reports_unavailable': len(manifest['reports']) - len(valid),
        'feature_rows': len(rows), 'train_rows': len(train), 'test_rows': len(test),
        'train_start': str(train.date.min().date()), 'train_end': str(train.date.max().date()),
        'test_start': str(test.date.min().date()), 'test_end': str(test.date.max().date()),
        'raw_start': str(panel.date.min().date()), 'raw_end': str(panel.date.max().date()),
        'latest_period': period_label(panel.slot.max()), 'forecast_trained_through': period_label(rows.slot.max()),
        'markets': ['Colombo district'], 'commodities': sorted(test.commodity.unique()),
        'features': FEATURES, 'folds': folds, 'future_folds': future_folds, 'fit_seconds': timings,
        'metrics': metrics(output), 'meta_coefficients': bundle['meta'].coef_.tolist(),
        'feature_factors': feature_factors(bundle, test),
        'protocol': 'Train through 2025; frozen one-report-ahead comparisons on recorded 2026 prices. Future forecasts use a separate refit on all available observations.',
        'limitations': ['Colombo district market averages only; not district-by-district or national prices.',
                        'DCS uses four reporting periods per month. Dates encode W1/W2/W3/W4 as days 1/8/15/22, not exact collection dates.',
                        'Unavailable releases and missing prices remain missing; incomplete lag rows are excluded.',
                        'Historical source revisions and extraction errors remain possible; PDFs and page provenance are included.',
                        'Forecasts are recursive, have no calibrated intervals, and cannot anticipate unmodeled weather, exchange rates, supply or policy shocks.'],
    }
    output.to_csv(ARTIFACTS / 'predictions.csv', index=False)
    rows.to_csv(ROOT / 'data/processed/features.csv', index=False)
    (ARTIFACTS / 'report.json').write_text(json.dumps(report, indent=2))
    joblib.dump(bundle, ARTIFACTS / 'models.joblib')
    joblib.dump(future_bundle, ARTIFACTS / 'forecast_models.joblib')
    return report, output


if __name__ == '__main__':
    report, _ = train_and_export()
    print(json.dumps({k: report[k] for k in ['train_rows', 'test_rows', 'train_start', 'test_end', 'metrics']}, indent=2))
