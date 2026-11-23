"""Extract the current-week column, keeping each PDF and page as provenance."""
from pathlib import Path
import json
import re
import pandas as pd
import pdfplumber

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/raw/dcs'
FOODS = {
    'rawredaverage': 'Red rice', 'sambaaverage': 'Samba rice',
    'wheatflour': 'Wheat flour', 'mysoredhallaverage': 'Lentils', 'sugar': 'Sugar',
    'potatoeslocal': 'Local potatoes', 'potatoesimported': 'Imported potatoes',
    'bonionsimported': 'Imported big onions', 'redonionsaverage': 'Red onions',
    'tomatoeno1': 'Tomatoes', 'tomatono1': 'Tomatoes',
    'beansgreen': 'Green beans', 'carrot': 'Carrots', 'cabbaggeseed': 'Cabbage',
    'brinjal': 'Brinjal', 'bandakka': 'Okra', 'greenchillies': 'Green chillies',
    'leeks': 'Leeks', 'redpumpkin': 'Red pumpkin', 'snakegourd': 'Snake gourd',
    'garlic': 'Garlic',
}


def clean(text):
    return re.sub('[^a-z0-9]', '', (text or '').lower())


def extract(path):
    year, month, week = map(int, re.search(r'(20\d{2})-(\d{2})-W([1-4])', path.stem).groups())
    date = f'{year}-{month:02d}-{1 + 7 * (week - 1):02d}'
    records = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            words = page.extract_words()
            for table in page.find_tables():
                rows = table.extract()
                if not rows or len(rows[0]) < 3 or clean(rows[0][0]) != 'item':
                    continue
                avg = table.rows[0].cells[2]
                if avg is None:
                    continue
                x0, _, x1, _ = avg
                current_x = x0 + (x1 - x0) * 2 / 3
                section = ''
                for row, geometry in zip(rows, table.rows):
                    name, unit = row[0], row[1]
                    key = clean(name)
                    if key.startswith('potatoes'): section = 'potatoes'
                    elif key.startswith('bonions'): section = 'bonions'
                    elif key and key != 'imported': section = ''
                    if key == 'imported': key = section + key
                    food = FOODS.get(key)
                    box = geometry.cells[0]
                    if not food or not box or clean(unit) not in ['1kg', '1kgpkt']:
                        continue
                    mid_y = (box[1] + box[3]) / 2
                    values = [w['text'] for w in words if current_x <= (w['x0'] + w['x1']) / 2 < x1
                              and abs((w['top'] + w['bottom']) / 2 - mid_y) < (box[3] - box[1]) / 2]
                    value = ''.join(values).replace(',', '').strip()
                    if not re.fullmatch(r'\d+(\.\d+)?', value) or float(value) <= 0:
                        continue
                    records.append({'date': date, 'period': f'{year}-{month:02d}-W{week}',
                                    'slot': year * 48 + (month - 1) * 4 + week - 1,
                                    'commodity': food, 'market': 'Colombo district', 'price': float(value),
                                    'unit': 'LKR/kg', 'source_file': path.name, 'source_page': page_number,
                                    'source_url': f'https://www.statistics.gov.lk/Resource/en/InflationAndPrices/retail/{path.name}'})
    return records


if __name__ == '__main__':
    records, failures = [], []
    paths = sorted(FOLDER.glob('*.pdf'))
    if not paths:
        raise SystemExit('No source PDFs found. Run scripts/download_dcs.py first. The existing processed dataset has not been changed.')
    for i, path in enumerate(paths, 1):
        try:
            records.extend(extract(path))
        except Exception as error:
            failures.append({'file': path.name, 'error': str(error)})
        if i % 50 == 0: print(f'Parsed {i}/{len(paths)} PDFs', flush=True)
    frame = pd.DataFrame(records).drop_duplicates(['slot', 'commodity']).sort_values(['slot', 'commodity'])
    (ROOT / 'data/processed').mkdir(exist_ok=True)
    frame.to_csv(ROOT / 'data/processed/dcs_weekly_prices.csv', index=False)
    summary = {'pdfs': len(paths), 'rows': len(frame), 'first_period': frame.period.min(), 'last_period': frame.period.max(),
               'foods': frame.groupby('commodity').size().to_dict(), 'parse_failures': failures}
    (FOLDER / 'extraction_summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
