from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo
import json
import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from .ml import ARTIFACTS, ROOT, CUTOFF, metrics, predict, forecast, slot_date, period_label


@asynccontextmanager
async def lifespan(app):
    app.state.report = json.loads((ARTIFACTS / 'report.json').read_text())
    app.state.predictions = pd.read_csv(ARTIFACTS / 'predictions.csv')
    app.state.features = pd.read_csv(ROOT / 'data/processed/features.csv', parse_dates=['date'])
    app.state.panel = pd.read_csv(ROOT / 'data/processed/dcs_weekly_prices.csv', parse_dates=['date'])
    app.state.bundle = joblib.load(ARTIFACTS / 'models.joblib')
    app.state.future_bundle = joblib.load(ARTIFACTS / 'forecast_models.joblib')
    yield


app = FastAPI(title='Food Lens API', version='2.0.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'],
                   allow_methods=['GET', 'POST'], allow_headers=['Content-Type'])


def filtered(commodity=None):
    rows = app.state.predictions
    if commodity:
        rows = rows.loc[rows.commodity == commodity]
    if rows.empty:
        raise HTTPException(404, 'No recorded comparisons for this food.')
    return rows


@app.get('/api/health')
def health():
    return {'status': 'ok', 'evaluation_trained_through': app.state.report['train_end'],
            'forecast_trained_through': app.state.report['forecast_trained_through']}


@app.get('/api/overview')
def overview(commodity: str | None = None):
    rows = filtered(commodity)
    timeline = rows.groupby(['date', 'period'], as_index=False)[['actual', 'previous', 'bagging', 'boosting', 'stacking', 'baseline']].mean()
    breakdown = [{'commodity': food, 'metrics': metrics(group)} for food, group in rows.groupby('commodity')]
    return {'report': app.state.report, 'metrics': metrics(rows), 'timeline': timeline.to_dict('records'),
            'breakdown': breakdown, 'rows': rows.to_dict('records')}


def period_slot(period):
    year, month, week = int(period[:4]), int(period[5:7]), int(period[-1])
    if not 1 <= month <= 12:
        raise HTTPException(422, 'Choose a valid month.')
    return year * 48 + (month - 1) * 4 + week - 1


@app.get('/api/options')
def options(commodity: str):
    rows = filtered(commodity)
    history = app.state.panel.loc[app.state.panel.commodity == commodity]
    origin = int(history.slot.max())
    today = datetime.now(ZoneInfo('Asia/Colombo')).date()
    future = [{'period': period_label(origin + step), 'date': str(slot_date(origin + step).date()), 'steps': step}
              for step in range(1, 13) if slot_date(origin + step).date() > today]
    return {'known': rows[['period', 'date']].to_dict('records'), 'future': future,
            'origin': period_label(origin), 'today': str(today)}


class PredictionRequest(BaseModel):
    commodity: str = Field(min_length=1, max_length=100)
    mode: Literal['historical', 'future'] = 'historical'
    period: str = Field(pattern=r'^20\d{2}-\d{2}-W[1-4]$')


@app.post('/api/predict')
def prediction(request: PredictionRequest):
    slot = period_slot(request.period)
    if request.commodity not in app.state.report['commodities']:
        raise HTTPException(404, 'Unknown food.')
    if request.mode == 'future':
        panel = app.state.panel
        origin = int(panel.loc[panel.commodity == request.commodity].slot.max())
        steps = slot - origin
        if not 1 <= steps <= 12:
            raise HTTPException(422, 'Choose a period within 12 reporting steps of the last observation.')
        if slot_date(slot).date() <= datetime.now(ZoneInfo('Asia/Colombo')).date():
            raise HTTPException(422, 'Future mode needs a period after today. Use historical mode for recorded outcomes.')
        try:
            result = forecast(app.state.future_bundle, panel, request.commodity, steps)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        result.update(mode='future', target=result['rows'][-1], trained_through=app.state.report['forecast_trained_through'])
        return result
    rows = app.state.features
    selected = rows.loc[(rows.commodity == request.commodity) & (rows.slot == slot) & (rows.date >= CUTOFF)]
    if selected.empty:
        raise HTTPException(404, 'No complete historical comparison for this food and period.')
    target = predict(app.state.bundle, selected).iloc[0].to_dict()
    target['date'] = str(target['date'].date())
    target['inputs'] = selected[['lag_1', 'lag_2', 'lag_4', 'lag_8', 'mean_4', 'std_4', 'change_1']].iloc[0].to_dict()
    history = app.state.panel.loc[(app.state.panel.commodity == request.commodity) & (app.state.panel.slot <= slot)].tail(16)
    return {'mode': 'historical', 'commodity': request.commodity, 'target': target,
            'trained_through': period_label(rows.loc[rows.date < CUTOFF, 'slot'].max()),
            'history': [{'date': str(r.date.date()), 'period': r.period, 'actual': r.price} for r in history.itertuples()]}


@app.get('/api/export')
def export(commodity: str | None = None):
    return StreamingResponse(iter([filtered(commodity).to_csv(index=False)]), media_type='text/csv',
                             headers={'Content-Disposition': 'attachment; filename="food-prices-2026.csv"'})
