import React, { useEffect, useRef, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, BarChart, Bar, Cell, ReferenceLine } from 'recharts';
import { Leaf, ChevronDown, Download, Info, LoaderCircle, Check, ArrowUpRight, ArrowDownRight } from 'lucide-react';

const colors = { actual: '#242426', bagging: '#219575', boosting: '#007aff', stacking: '#9565cf', baseline: '#a4a4ad' };
const names = { actual: 'Recorded', bagging: 'Bagging', boosting: 'Boosting', stacking: 'Stacking', baseline: 'Previous report' };
const methods = ['bagging', 'boosting', 'stacking'];
const metricDefinitions = {
  mae: { short: 'MAE', name: 'Mean Absolute Error', unit: 'LKR/kg', description: 'Average absolute difference between predicted and recorded prices.', higher: false },
  rmse: { short: 'RMSE', name: 'Root Mean Squared Error', unit: 'LKR/kg', description: 'Price error that gives larger misses more weight.', higher: false },
  mape: { short: 'MAPE', name: 'Mean Absolute Percentage Error', unit: '%', description: 'Average absolute price error relative to the recorded price.', higher: false },
  direction_accuracy: { short: 'Direction', name: 'Direction Accuracy', unit: '%', description: 'Share of predictions matching the recorded direction: down, unchanged or up.', higher: true }
};
const number = value => Number(value).toLocaleString('en-LK', { maximumFractionDigits: 2, minimumFractionDigits: 2 });
const dateLabel = value => new Date(value).toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });
const periodLabel = value => value ? `Week ${value.at(-1)} · ${dateLabel(`${value.slice(0, 7)}-01`)}` : '';
const descriptions = {
  bagging: { name: 'Random forest', text: 'Bagging means bootstrap aggregation. It averages 120 trees trained on bootstrap samples. Random feature subsets help the trees make different mistakes.', factors: 'Tree depth, leaf size and variety between trees control the balance between fitting detail and smoothing noise.' },
  boosting: { name: 'XGBoost', text: 'XGBoost means Extreme Gradient Boosting. It adds 140 small trees in sequence. Each tree improves the regularized loss left by the current ensemble.', factors: 'Learning rate, tree depth, number of trees and regularization affect how quickly the model learns and how much it fits noise.' },
  stacking: { name: 'Temporal stacking', text: 'A ridge model learns to combine random forest, XGBoost and ridge predictions from three chronological validation folds.', factors: 'Base-model diversity, the validation periods and the ridge penalty affect the learned combination. Similar errors limit the benefit.' }
};

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : 'Check the selected values and try again.');
  return body;
}

function Select({ label, value, onChange, children, disabled = false }) {
  return <label className="field"><span>{label}</span><div className="select-box"><select disabled={disabled} value={value} onChange={e => onChange(e.target.value)}>{children}</select><ChevronDown size={15} /></div></label>;
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return <div className="tooltip"><strong>{label?.includes('-W') ? periodLabel(label) : label}</strong>{payload.filter(p => p.value !== null).map(p => <div key={p.dataKey}><i style={{ background: p.color }} /><span>{names[p.dataKey] || p.name}</span><b>Rs. {number(p.value)}</b></div>)}</div>;
}

function Legend({ keys, selected, onToggle }) {
  return <div className="legend">{keys.map(key => onToggle ? <button key={key} onClick={() => onToggle(key)} aria-pressed={selected.includes(key)} className={selected.includes(key) ? '' : 'muted'}><i style={{ background: colors[key] }} />{names[key]}</button> : <span key={key}><i style={{ background: colors[key] }} />{names[key]}</span>)}</div>;
}

function PriceChart({ rows, visible = methods, future = false, origin }) {
  return <div className="line-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={rows} margin={{ top: 15, right: 20, bottom: 12, left: 0 }}>
    <CartesianGrid vertical={false} stroke="#eeeef1" />
    <XAxis dataKey="period" tickFormatter={v => `${v.slice(5, 7)}/W${v.at(-1)}`} minTickGap={32} tickLine={false} axisLine={false} tickMargin={14} />
    <YAxis domain={['auto', 'auto']} tickFormatter={v => Math.round(v)} tickLine={false} axisLine={false} width={50} />
    <Tooltip content={<ChartTooltip />} />
    {origin && <ReferenceLine x={origin} stroke="#c4c4ca" strokeDasharray="4 4" />}
    <Line dataKey="actual" name="Recorded" stroke={colors.actual} strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
    {visible.map(key => <Line key={key} dataKey={key} stroke={colors[key]} strokeWidth={2} dot={false} strokeDasharray={future || key === 'baseline' ? '5 4' : undefined} />)}
  </LineChart></ResponsiveContainer></div>;
}

function MetricTable({ rows }) {
  return <div className="table-scroll"><table><thead><tr><th>Model</th>{Object.entries(metricDefinitions).map(([key, info]) => <th key={key}><span>{info.short} {info.higher ? '↑' : '↓'}</span><small>{info.name}</small></th>)}<th><span>R² ↑</span><small>Coefficient of Determination</small></th></tr></thead><tbody>{rows.map(row => <tr key={row.key}><td><i style={{ background: colors[row.key] }} />{names[row.key]}</td><td>{number(row.mae)}</td><td>{number(row.rmse)}</td><td>{row.mape.toFixed(2)}%</td><td>{row.direction_accuracy.toFixed(1)}%</td><td>{row.r2 === null ? '—' : row.r2.toFixed(3)}</td></tr>)}</tbody></table></div>;
}

function MetricComparison({ rows, metric, onChange }) {
  const info = metricDefinitions[metric];
  const values = rows.map(row => ({ key: row.key, model: names[row.key], value: row[metric] }));
  const winner = values.reduce((best, row) => (info.higher ? row.value > best.value : row.value < best.value) ? row : best);
  const formatted = value => `${number(value)}${info.unit === '%' ? '%' : ' LKR/kg'}`;
  return <section className="card">
    <div className="section-heading metric-heading"><div><h2>Compare techniques</h2><p>{info.name} · {info.unit} · {info.higher ? 'higher' : 'lower'} is better</p></div>
      <div className="metric-picker"><Select label="Comparison metric" value={metric} onChange={onChange}>{Object.entries(metricDefinitions).map(([key, definition]) => <option key={key} value={key}>{definition.name}{key === 'direction_accuracy' ? '' : ` (${definition.short})`}</option>)}</Select></div>
    </div>
    <div className="metric-explanation"><p>{info.description}</p><span className="metric-winner">{info.higher ? 'Highest score' : 'Lowest error'}: {winner.model} · {formatted(winner.value)}</span></div>
    <div className="metric-comparison" role="img" aria-label={`${info.name} comparison. ${values.map(row => `${row.model}: ${formatted(row.value)}`).join('; ')}. ${info.higher ? 'Higher' : 'Lower'} is better.`}>
      <ResponsiveContainer width="100%" height="100%"><BarChart data={values} layout="vertical" margin={{ left: 0, right: 65, top: 6, bottom: 8 }}>
        <CartesianGrid horizontal={false} stroke="#eeeef1" />
        <XAxis type="number" domain={metric === 'direction_accuracy' ? [0, 100] : [0, 'auto']} tickFormatter={value => info.unit === '%' ? `${value}%` : value} axisLine={false} tickLine={false} />
        <YAxis type="category" dataKey="model" width={105} axisLine={false} tickLine={false} />
        <Tooltip formatter={value => [formatted(value), info.name]} cursor={{ fill: '#f7f7f9' }} />
        <Bar dataKey="value" radius={[0, 5, 5, 0]} barSize={23} isAnimationActive={false} label={{ position: 'right', formatter: value => `${Number(value).toFixed(2)}${info.unit === '%' ? '%' : ''}`, fontSize: 12, fill: '#6e6e73' }}>{values.map(row => <Cell key={row.key} fill={colors[row.key]} />)}</Bar>
      </BarChart></ResponsiveContainer>
    </div>
    <p className="chart-note">All methods use the same selected holdout observations. The previous-report baseline always predicts unchanged; its direction score measures unchanged actual prices.</p>
  </section>;
}

function PredictionLab({ report }) {
  const [mode, setMode] = useState('historical');
  const [food, setFood] = useState(report.commodities[0]);
  const [options, setOptions] = useState(null);
  const [period, setPeriod] = useState('');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const activeRequest = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    setOptions(null); setError('');
    request(`/api/options?commodity=${encodeURIComponent(food)}`, { signal: controller.signal }).then(setOptions).catch(e => { if (e.name !== 'AbortError') setError(e.message); });
    return () => controller.abort();
  }, [food]);
  useEffect(() => {
    activeRequest.current?.abort();
    setBusy(false); setResult(null); setError('');
    const choices = mode === 'historical' ? options?.known : options?.future;
    setPeriod(choices?.length ? (mode === 'historical' ? choices.at(-1).period : choices[0].period) : '');
  }, [food, mode, options]);
  useEffect(() => () => activeRequest.current?.abort(), []);

  const choices = mode === 'historical' ? options?.known || [] : options?.future || [];
  async function run() {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;
    setBusy(true); setError(''); setResult(null);
    try {
      const value = await request('/api/predict', { method: 'POST', signal: controller.signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ commodity: food, mode, period }) });
      setResult(value);
    } catch (e) { if (e.name !== 'AbortError') setError(e.message); }
    finally { if (!controller.signal.aborted) setBusy(false); }
  }
  function changePeriod(value) { activeRequest.current?.abort(); setBusy(false); setResult(null); setError(''); setPeriod(value); }
  const target = result?.target;
  const futureChart = result?.mode === 'future' ? [
    ...result.history.map((r, index) => index === result.history.length - 1 ? { ...r, ...Object.fromEntries(methods.map(k => [k, r.actual])) } : r),
    ...result.rows
  ] : [];
  const targetPrices = target ? ['actual', ...methods].filter(key => target[key] !== null && target[key] !== undefined).map(key => ({ model: names[key], price: target[key], key })) : [];

  return <>
    <section className="card lab-form"><div className="segmented" aria-label="Prediction mode">{[['historical', 'Known prices'], ['future', 'Future prices']].map(([key, label]) => <button key={key} aria-pressed={mode === key} className={mode === key ? 'selected' : ''} onClick={() => setMode(key)}>{label}</button>)}</div>
      <p className="mode-description">{mode === 'historical' ? 'Compare a saved model prediction with a recorded 2026 price.' : 'Estimate an unobserved future price using models refitted on all available reports.'}</p>
      <div className="lab-fields"><Select label="Food" value={food} onChange={setFood}>{report.commodities.map(c => <option key={c}>{c}</option>)}</Select><Select label={mode === 'historical' ? 'Recorded period' : 'Future period'} value={period} onChange={changePeriod} disabled={!choices.length}>{!choices.length && <option value="">{options ? 'No available periods' : 'Loading…'}</option>}{choices.map(p => <option key={p.period} value={p.period}>{periodLabel(p.period)}</option>)}</Select><button className="button primary" onClick={run} disabled={busy || !period}>{busy ? <><LoaderCircle className="spin" size={17} /> Running</> : mode === 'historical' ? 'Compare prices' : 'Forecast price'}</button></div>
      {mode === 'future' && options && <div className="helper"><Info size={15} /><span>Latest observation: {periodLabel(options.origin)}. Missing releases between that report and your target are estimated recursively.</span></div>}
      {options && mode === 'future' && !choices.length && <p className="error">The dataset is too old for a future forecast within 12 reporting steps. Refresh the DCS data first.</p>}
      {error && <p className="error" role="alert">{error}</p>}
    </section>
    {!result ? <div className="lab-placeholder"><div className="placeholder-lines"><span /><span /><span /></div><h2>{mode === 'historical' ? 'Select a price to compare.' : 'Select a future period.'}</h2><p>{mode === 'historical' ? 'Recorded price, three predictions and their errors in one view.' : 'A short forecast, with the last recorded price kept in view.'}</p></div> : <>
      <section className="result-heading"><div><span className="overline">{food} · {periodLabel(target.period)}</span><h2>{mode === 'historical' ? <>Rs. {number(target.actual)}<small> / kg recorded</small></> : <>Future estimate<small> · actual price unknown</small></>}</h2><p>{mode === 'historical' ? `Previous report: Rs. ${number(target.previous)} / kg` : `Last recorded price: Rs. ${number(result.origin_price)} / kg · ${target.step} reporting steps ahead`}</p></div><span className="badge">{mode === 'historical' ? '2026 holdout' : 'Unverified forecast'}</span></section>
      <section className="card"><div className="section-heading"><div><h2>{mode === 'historical' ? 'Recorded vs predicted' : 'Price forecast'}</h2><p>LKR per kilogram</p></div></div>
        {mode === 'historical' ? <div className="prediction-bars"><ResponsiveContainer width="100%" height="100%"><BarChart data={targetPrices} layout="vertical" margin={{ left: 12, right: 35 }}><CartesianGrid horizontal={false} stroke="#eeeef1" /><XAxis type="number" axisLine={false} tickLine={false} /><YAxis type="category" dataKey="model" width={86} axisLine={false} tickLine={false} /><Tooltip formatter={v => [`Rs. ${number(v)}`, 'Price']} cursor={{ fill: '#f7f7f9' }} /><Bar dataKey="price" radius={[0, 5, 5, 0]} barSize={22} label={{ position: 'right', formatter: v => Number(v).toFixed(1), fontSize: 12, fill: '#6e6e73' }}>{targetPrices.map(row => <Cell key={row.key} fill={colors[row.key]} />)}</Bar></BarChart></ResponsiveContainer></div> : <><Legend keys={['actual', ...methods]} /><PriceChart rows={futureChart} future origin={result.origin} /></>}
        <p className="chart-note">{mode === 'historical' ? 'The recorded target price is used only for comparison. It is not an input to these predictions.' : 'Dashed lines are model estimates after the last recorded report. Later steps use each model’s own earlier predictions.'}</p>
      </section>
      <div className="three-columns">{methods.map(key => {
        const reference = mode === 'historical' ? target.previous : result.origin_price;
        const change = (target[key] / reference - 1) * 100;
        return <article className="card estimate-card" key={key}><div className="model-label"><i style={{ background: colors[key] }} />{names[key]}</div><h2>Rs. {number(target[key])}<small> / kg</small></h2><span className="movement">{change >= 0 ? <ArrowUpRight size={15} /> : <ArrowDownRight size={15} />}{Math.abs(change).toFixed(2)}% {mode === 'historical' ? 'vs previous report' : 'vs last recorded'}</span>{mode === 'historical' && <div className="estimate-error"><span>Absolute error</span><strong>Rs. {number(Math.abs(target[key] - target.actual))}</strong><span>Direction</span><strong>{Math.sign(target[key] - target.previous) === Math.sign(target.actual - target.previous) ? 'Correct' : 'Missed'}</strong></div>}</article>;
      })}</div>
      {mode === 'historical' ? <section className="card"><h2>Earlier prices used as inputs</h2><div className="input-grid">{[['lag_1', '1 report earlier'], ['lag_2', '2 reports earlier'], ['lag_4', '4 reports earlier'], ['lag_8', '8 reports earlier'], ['mean_4', 'Past 4-report mean']].map(([key, label]) => <div key={key}><span>{label}</span><strong>Rs. {number(target.inputs[key])}</strong></div>)}</div><p className="chart-note">Comparison models were trained through December 2025. Earlier observed 2026 prices may become inputs for later holdout periods.</p></section> : <div className="notice"><Info size={18} /><p>{result.warning} No error or accuracy score can be reported until those prices are observed.</p></div>}
    </>}
  </>;
}

export default function App() {
  const [page, setPage] = useState('Overview');
  const [food, setFood] = useState('');
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(true);
  const [retry, setRetry] = useState(0);
  const [visible, setVisible] = useState(methods);
  const [metric, setMetric] = useState('mae');
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true); setError('');
    request(`/api/overview?${new URLSearchParams(food ? { commodity: food } : {})}`, { signal: controller.signal }).then(setData).catch(e => { if (e.name !== 'AbortError') setError(e.message); }).finally(() => { if (!controller.signal.aborted) setBusy(false); });
    return () => controller.abort();
  }, [food, retry]);
  const report = data?.report;
  const best = data && [...data.metrics].filter(m => m.key !== 'baseline').sort((a, b) => a.mae - b.mae)[0];
  const baseline = data?.metrics.find(m => m.key === 'baseline');
  const gain = best ? (baseline.mae - best.mae) / baseline.mae * 100 : 0;
  const titles = { Overview: ['Food prices', 'Recorded Sri Lankan prices and ensemble predictions.'], Models: ['Model comparison', 'Three methods, the same features and the same holdout.'], 'Prediction lab': ['Prediction lab', 'Compare a known outcome or estimate a future price.'], Data: ['Data & method', 'Official reports, a longer history and a chronological split.'] };

  const bars = data?.breakdown.map(b => ({ food: b.commodity, ...Object.fromEntries(b.metrics.map(m => [m.key, m[metric]])) }));
  return <><header className="navigation"><div className="nav-inner"><a className="brand" href="#" onClick={e => { e.preventDefault(); setPage('Overview'); }}><Leaf size={23} strokeWidth={1.7} />Food Lens</a><nav aria-label="Main navigation">{Object.keys(titles).map(name => <button key={name} className={page === name ? 'active' : ''} onClick={() => setPage(name)}>{name}</button>)}</nav><span className="location">Sri Lanka</span></div></header>
    <main className="content"><div className="page-heading"><div><span className="overline">Colombo district · Retail prices</span><h1>{titles[page][0]}</h1><p>{titles[page][1]}</p></div>{data && page !== 'Prediction lab' && <a className="button secondary" href={`/api/export?${new URLSearchParams(food ? { commodity: food } : {})}`}><Download size={16} />Export CSV</a>}</div>
      {error ? <div className="card error-state"><h2>Couldn’t load the prices</h2><p>{error} Check that FastAPI is running on port 8000.</p><button className="button primary" onClick={() => { setFood(''); setRetry(v => v + 1); }}>Try again</button></div> : !data ? <div className="loading"><LoaderCircle className="spin" size={24} /><span>Loading prices…</span></div> : <>
      {(page === 'Overview' || page === 'Models') && <section className="filters"><Select label="Food" value={food} onChange={setFood}><option value="">All {report.commodities.length} foods</option>{report.commodities.map(c => <option key={c}>{c}</option>)}</Select><div className="filter-context"><span>Known outcomes</span><strong>{dateLabel(report.test_start)} – {dateLabel(report.test_end)}</strong></div><span className="badge">{busy ? 'Updating…' : `${best.n.toLocaleString()} comparisons`}</span></section>}
      <div className={busy ? 'results updating' : 'results'} aria-busy={busy}>
      {page === 'Overview' && <>
        <section className="summary-grid"><article><span>Lowest ensemble MAE</span><h2>{names[best.key]}</h2><p>{best.name}</p></article><article><span>Average absolute error</span><h2>{number(best.mae)}<small> LKR/kg</small></h2><p>Across individual held-out prices</p></article><article><span>Compared with persistence</span><h2>{Math.abs(gain).toFixed(1)}<small>% {gain >= 0 ? 'lower' : 'higher'}</small></h2><p>MAE vs the previous-report baseline</p></article></section>
        <section className="card"><div className="section-heading"><div><h2>Price comparison</h2><p>{food || 'Mean across selected foods'} · LKR/kg</p></div><span className="badge">One report ahead</span></div><Legend keys={['actual', ...methods, 'baseline']} selected={['actual', ...visible]} onToggle={key => { if (key !== 'actual') setVisible(v => v.includes(key) ? v.filter(k => k !== key) : [...v, key]); }} /><PriceChart rows={data.timeline} visible={visible} /><p className="chart-note">Four reporting periods per month. The chart averages available foods; metrics use individual price observations.</p></section>
        <section className="card"><div className="section-heading"><div><h2>Results at a glance</h2><p>Training ends December 2025. Comparisons use recorded 2026 prices.</p></div><button className="text-button" onClick={() => setPage('Models')}>Explore models</button></div><MetricTable rows={data.metrics} /><p className="chart-note">MAE and RMSE are LKR/kg. Lower is better. Direction measures the exact sign: down, unchanged or up.</p></section>
      </>}
      {page === 'Models' && <>
        <div className="three-columns">{methods.map(key => <article className="card method-card" key={key}><div className="model-label"><i style={{ background: colors[key] }} />{names[key]}</div><h2>{descriptions[key].name}</h2><p>{descriptions[key].text}</p><details><summary>What affects the result?</summary><p>{descriptions[key].factors}</p>{key !== 'stacking' && <div className="factor-list"><span>Whole-study permutation factors</span>{report.feature_factors[key].slice(0, 3).map(row => <strong key={row.feature}>{row.feature.replaceAll('_', ' ')}</strong>)}</div>}</details></article>)}</div>
        <MetricComparison rows={data.metrics} metric={metric} onChange={setMetric} />
        <section className="card"><h2>Holdout scores</h2><MetricTable rows={data.metrics} /><p className="chart-note">The baseline always predicts no change. Its direction score measures unchanged prices. Permutation rankings are diagnostics, not causal explanations.</p></section>
        <section className="card"><div className="section-heading"><div><h2>Comparison by food</h2><p>{metricDefinitions[metric].name} · {metricDefinitions[metric].unit} · {metricDefinitions[metric].higher ? 'higher' : 'lower'} is better</p></div></div><Legend keys={[...methods, 'baseline']} /><div className="food-chart" style={{ height: Math.max(240, bars.length * 63) }}><ResponsiveContainer width="100%" height="100%"><BarChart data={bars} layout="vertical" margin={{ left: 0, right: 20 }}><CartesianGrid horizontal={false} stroke="#eeeef1" /><XAxis type="number" axisLine={false} tickLine={false} /><YAxis type="category" dataKey="food" width={125} axisLine={false} tickLine={false} /><Tooltip formatter={(v, key) => [`${number(v)}${metricDefinitions[metric].unit === '%' ? '%' : ' LKR/kg'}`, names[key]]} />{[...methods, 'baseline'].map(key => <Bar key={key} dataKey={key} fill={colors[key]} radius={[0, 3, 3, 0]} maxBarSize={9} />)}</BarChart></ResponsiveContainer></div></section>
      </>}
      {page === 'Prediction lab' && <PredictionLab report={report} />}
      {page === 'Data' && <>
        <section className="card source-card"><span className="overline">Primary source</span><h2>Department of Census and Statistics</h2><p>Open-market weekly average retail prices from the main markets in Colombo district. Current-report prices are extracted from the original DCS PDFs, with file and page references retained.</p><a href={report.source_url} className="text-button" target="_blank" rel="noreferrer">View official price reports</a></section>
        <section className="summary-grid"><article><span>Training observations</span><h2>{report.train_rows.toLocaleString()}</h2><p>{dateLabel(report.train_start)} – {dateLabel(report.train_end)}</p></article><article><span>Downloaded reports</span><h2>{report.reports_downloaded}</h2><p>{dateLabel(report.raw_start)} – {dateLabel(report.raw_end)}</p></article><article><span>Food series</span><h2>{report.commodities.length}</h2><p>Comparable LKR/kg prices · Colombo</p></article></section>
        <div className="two-columns"><section className="card"><h2>Training and evaluation</h2><ol className="steps"><li><strong>Read the current-week column.</strong><p>Use reported prices only. Previous-year averages, percentage changes and price ranges are not training targets.</p></li><li><strong>Build past-only features.</strong><p>Prices 1, 2, 4 and 8 reporting periods earlier; past four-period mean and spread; recent movement and seasonality. Missing periods stay missing.</p></li><li><strong>Hold out 2026.</strong><p>All evaluation models train on pre-2026 targets. Earlier observed 2026 prices may be inputs for later one-report-ahead comparisons.</p></li><li><strong>Refit for future forecasts.</strong><p>A separate model set uses all observed data through {periodLabel(report.latest_period)}. Each model then uses its own predicted prices for later forecast steps.</p></li></ol></section>
        <section className="card"><h2>Chronological stacking</h2><p>Each fold predicts later periods using earlier training data. Scaling and encoding are fitted inside the fold.</p><div className="folds">{report.folds.map((f, i) => <div key={i}><Check size={17} /><span>Train through {periodLabel(f.train_end)}<strong>Validate {periodLabel(f.validation_start)} – {periodLabel(f.validation_end)}</strong></span></div>)}</div><p>The ridge combiner learns from those held-out predictions. The base models are then refitted on the full training portion.</p></section></div>
        <section className="card"><h2>Scope and limitations</h2><ul className="limits">{report.limitations.map(text => <li key={text}>{text}</li>)}</ul><p className="chart-note">Settings are fixed, with seed 42 and no tuning on 2026 outcomes. {report.reports_unavailable} archive links were unavailable during download. Full provenance is in SOURCES.md. AI coding assistance is credited in the notebook and AI_USAGE.md.</p></section>
      </>}
      </div><footer><span>DCS Sri Lanka · Colombo district · LKR/kg</span><span>Latest report: {periodLabel(report.latest_period)}</span><span>Nivethan R. · 224138H</span></footer></>}
    </main></>;
}
