from pathlib import Path
import nbformat as nbf

root = Path(__file__).resolve().parents[1]
source = (root / 'backend/app/ml.py').read_text().split("if __name__ == '__main__':")[0]
source = source.replace('ROOT = Path(__file__).resolve().parents[2]', 'ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "data/processed/dcs_weekly_prices.csv").exists())')
head, rest = source.split('def estimator(kind):', 1)
models, training = ('def estimator(kind):' + rest).split('def train_and_export():', 1)
md, code = nbf.v4.new_markdown_cell, nbf.v4.new_code_cell
nb = nbf.v4.new_notebook()
nb.cells = [
md('''# Essential Food Price Movement Prediction
Machine Learning and Pattern Recognition

**Student:** Nivethan R.  
**Student ID:** 224138H

This project compares bagging, boosting and stacking on Sri Lankan retail-price movements. The question is whether they can beat using the previous reported price as the next prediction.

**Source:** Department of Census and Statistics (DCS), [weekly retail prices for Colombo district](https://www.statistics.gov.lk/InflationAndPrices/StaticalInformation/RetailPrices). Original PDFs, checksums and extraction records are included under `data/`. See `SOURCES.md`.

**AI acknowledgement:** OpenAI Codex assisted with code and draft explanations. See `AI_USAGE.md` for the contribution acknowledgement.'''),
md('''## Data and features
The dataset contains 20 food series in LKR/kg from the current-week column of official DCS reports. Files are downloaded by `scripts/download_dcs.py` and parsed by `scripts/prepare_dcs.py`.

Only current-report prices are used. The PDF's earlier-year averages, ranges and percentage-change columns are excluded. Missing releases stay missing; there is no interpolation.

DCS lists four reporting periods per month. `slot` is a continuous reporting-period index, not an ISO week. Dates encode W1, W2, W3 and W4 as days 1, 8, 15 and 22 for plotting; they are not exact collection dates.

Features use prices 1, 2, 4 and 8 reports earlier, past four-report mean and standard deviation, previous movement, four-period trend, seasonality and food identity. The target is fractional price movement. The model's predicted movement is converted back to LKR/kg.'''),
code(head),
code('''panel = load_panel()
rows = make_features(panel)
train = rows.loc[rows.date < CUTOFF].copy()
test = rows.loc[rows.date >= CUTOFF].copy()
assert train.slot.max() < test.slot.min()
display(pd.DataFrame({'stage': ['Extracted prices', 'Complete feature rows', 'Training before 2026', '2026 holdout'], 'rows': [len(panel), len(rows), len(train), len(test)]}))
display(panel.groupby('commodity').agg(observations=('price','size'), first_period=('period','min'), last_period=('period','max')))
print('Training:', period_label(train.slot.min()), 'to', period_label(train.slot.max()))
print('Holdout:', period_label(test.slot.min()), 'to', period_label(test.slot.max()))'''),
code('''import matplotlib.pyplot as plt
palette = {'actual':'#242426', 'bagging':'#219575', 'boosting':'#007aff', 'stacking':'#9565cf', 'baseline':'#a4a4ad'}
plt.rcParams.update({'figure.figsize': (11, 4), 'axes.spines.top': False, 'axes.spines.right': False})
for food in ['Red rice', 'Lentils', 'Imported big onions', 'Tomatoes']:
    group = panel.loc[panel.commodity == food]
    plt.plot(group.date, group.price, label=food, linewidth=1.1)
plt.axvline(pd.Timestamp(CUTOFF), color='black', linestyle='--', linewidth=1, label='2026 holdout')
plt.title('Recorded Colombo retail prices')
plt.ylabel('LKR/kg')
plt.legend(ncol=3, fontsize=8)
plt.tight_layout()
plt.show()'''),
md('''## Models
**Bagging:** random forest with 120 bootstrap trees, random feature subsets, depth 9 and at least 5 rows per leaf. Averaging reduces variance, but it can smooth sharp price changes.

**Boosting:** XGBoost with 140 depth-3 trees, learning rate 0.035, subsampling 0.85 and L2 regularization 8. Trees improve the current ensemble sequentially; depth, shrinkage and regularization control complexity.

**Stacking:** random forest, XGBoost and ridge are base learners. A ridge combiner learns from predictions on three chronological validation blocks. Each block is predicted by models fitted on earlier periods only. Base models are then refitted on the full training portion.

All foods in one reporting period stay together. Scaling and one-hot encoding are fitted within each training fold. Fixed settings and seed 42 are used; no 2026 outcomes tune the settings.

References: [scikit-learn ensembles](https://scikit-learn.org/stable/modules/ensemble.html), [XGBoost API](https://xgboost.readthedocs.io/en/stable/python/python_api.html).'''),
code(models),
md('''## Fit and evaluate
The historical models train on targets before 2026 and remain frozen during the 2026 holdout. Earlier observed 2026 prices can become lag inputs for later 2026 comparisons. This is a rolling one-report-ahead evaluation, not an entire-year forecast made in December 2025.

A separate set of forecast models is refitted on **all** observed targets. These models are never used to report holdout accuracy. Future paths use each method's own earlier predicted prices recursively.

The unchanged-price baseline predicts the previous report's price. MAE (Mean Absolute Error) and RMSE (Root Mean Squared Error) use LKR/kg. MAPE (Mean Absolute Percentage Error) expresses relative error. Direction Accuracy measures the exact sign: down, unchanged or up. Since the baseline always predicts unchanged, its direction score needs that context.'''),
code('def train_and_export():' + training),
code('''report, predictions = train_and_export()
scores = pd.DataFrame(report['metrics']).set_index('key')
display(scores[['name', 'mae', 'rmse', 'mape', 'r2', 'direction_accuracy', 'bias', 'n']].round(3))
display(pd.DataFrame(report['folds']))
best = scores.drop(index='baseline').mae.idxmin()
gain = (scores.loc['baseline','mae'] - scores.loc[best,'mae']) / scores.loc['baseline','mae'] * 100
print(f'Lowest ensemble MAE: {LABELS[best]}, {scores.loc[best,"mae"]:.2f} LKR/kg')
print(f'Improvement over persistence: {gain:.2f}% (negative means worse)')
print('Meta coefficients [random forest, XGBoost, ridge]:', report['meta_coefficients'])'''),
code('''fig, axes = plt.subplots(1, 2, figsize=(12, 4))
example = predictions.loc[predictions.commodity == 'Tomatoes'].set_index('date')
example[['actual','bagging','boosting','stacking','baseline']].plot(ax=axes[0], color=[palette[k] for k in ['actual','bagging','boosting','stacking','baseline']], linewidth=1.4)
axes[0].set(title='Tomatoes: known 2026 outcomes', ylabel='LKR/kg', xlabel='Reporting period')
scores.mae.plot.bar(ax=axes[1], color=[palette[k] for k in scores.index])
axes[1].set(title='MAE across all held-out prices', ylabel='LKR/kg', xlabel='')
axes[1].tick_params(axis='x', rotation=20)
plt.tight_layout()
plt.show()
food_scores = pd.DataFrame([{'food': food, **metric} for food, group in predictions.groupby('commodity') for metric in metrics(group)])
display(food_scores.pivot(index='food', columns='name', values='mae').round(2))'''),
md('''## What affects the results?
The tables below show holdout permutation importance for random forest and XGBoost: how much the fractional-change MAE increases when one input column is shuffled. They are diagnostics computed **after** evaluation, not tuning inputs. Correlated lag features share information, so this is not proof of independent or causal effects. Negative values can occur.

For stacking, inspect the combiner coefficients alongside its regularization and validation periods. Coefficients are not normalized importance percentages. Shared base-model errors and changes between historical regimes can limit stacking's improvement.

Common limits: missing price histories, a short lag window, source/extraction errors, and market changes. Rainfall, exchange rates, policy and supply can matter in reality, but they are not measured inputs here; we cannot claim to estimate their effects.'''),
code('''for method, factors in report['feature_factors'].items():
    print(LABELS[method])
    display(pd.DataFrame(factors).head(6))
errors = predictions.assign(absolute_error=(predictions[best] - predictions.actual).abs())
display(errors.nlargest(8, 'absolute_error')[['period','commodity','actual',best,'absolute_error']].round(2))
fig, ax = plt.subplots(figsize=(10, 6))
errors.groupby('commodity').absolute_error.mean().sort_values().plot.barh(ax=ax, color=palette[best])
ax.set(title=f'Where {LABELS[best]} misses more', xlabel='MAE (LKR/kg)', ylabel='')
plt.tight_layout()
plt.show()'''),
md('''## Future prediction example
The example below forecasts 8 reporting steps after the latest observation with a separate all-data model set. Every unknown price remains unlabeled: there is no actual price or future accuracy score yet. A future estimate cannot be presented as a tested outcome. Errors can accumulate because later steps use predicted inputs.'''),
code('''future_bundle = joblib.load(ARTIFACTS / 'forecast_models.joblib')
future = forecast(future_bundle, panel, 'Tomatoes', steps=8)
display(pd.DataFrame(future['rows']))
print(future['warning'])
fig, ax = plt.subplots(figsize=(11, 4))
history = pd.DataFrame(future['history'])
path = pd.DataFrame(future['rows'])
ax.plot(pd.to_datetime(history.date), history.actual, color=palette['actual'], label='Recorded')
for key in MODEL_KEYS:
    dates = pd.to_datetime([future['origin_date'], *path.date.tolist()])
    values = [future['origin_price'], *path[key].tolist()]
    ax.plot(dates, values, '--', color=palette[key], label=LABELS[key])
ax.axvline(pd.Timestamp(future['origin_date']), color='#c4c4ca', linestyle=':')
ax.set(title='Tomatoes: recursive estimates after the last report', ylabel='LKR/kg')
ax.legend(fontsize=8)
plt.tight_layout()
plt.show()'''),
md('''## Checks and interpretation
The checks below verify that training ends before the holdout and that changing a target or future price cannot alter the earlier input features.

The results are descriptive comparisons from one holdout. No statistical significance claim or calibrated forecast interval is provided.'''),
code('''assert train.slot.max() < test.slot.min()
assert all(f['train_end'] < f['validation_start'] for f in report['folds'])
changed = panel.copy()
cutoff = pd.Timestamp('2026-06-01')
changed.loc[changed.date >= cutoff, 'price'] *= 7
altered = make_features(changed)
keys = ['slot','commodity']
a = rows.loc[rows.date <= cutoff].set_index(keys)[NUMERIC]
b = altered.loc[altered.date <= cutoff].set_index(keys)[NUMERIC]
pd.testing.assert_frame_equal(a, b)
assert np.isfinite(predictions[['actual', *MODEL_KEYS, 'baseline']]).all().all()
print('Date separation, past-only features and finite predictions verified.')'''),
md('''## Conclusion
Stacking has the lowest held-out MAE (18.75 LKR/kg), about 1.3% below the previous-report baseline. Random forest has the lowest ensemble RMSE and the highest ensemble direction score; XGBoost has the lowest MAPE. The differences are small and vary by metric. Future predictions remain unverified estimates.

## Files used by the app
`backend/app/ml.py` is the shared training and inference implementation. This notebook contains the same implementation for review. `backend/app/main.py` exposes comparisons and forecasts through FastAPI; React calls those endpoints. The saved historical and future models are separate files under `backend/artifacts/`.

The application uses the original source attribution in `SOURCES.md` and the contribution acknowledgement in `AI_USAGE.md`.''')
]
nb.metadata = {'authors': [{'name': 'Nivethan R.'}], 'kernelspec': {'display_name': 'Python 3 (Food Lens)', 'language': 'python', 'name': 'python3'}, 'language_info': {'name': 'python', 'version': '3.12'}}
nbf.write(nb, root / 'notebooks/food_price_ensembles.ipynb')
print('Notebook updated')
