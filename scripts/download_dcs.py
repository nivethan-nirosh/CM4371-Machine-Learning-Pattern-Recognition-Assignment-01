"""Download the weekly reports linked by the DCS retail-price page."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen, Request
from datetime import datetime
from zoneinfo import ZoneInfo
import hashlib
import json
import re
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'data/raw/dcs'
INDEX = 'https://www.statistics.gov.lk/InflationAndPrices/StaticalInformation/RetailPrices'


def get(url):
    with urlopen(Request(url, headers={'User-Agent': 'FoodLens Academic Project/1.0'}), timeout=8) as response:
        return response.read()


def download(item):
    code, label = item
    path = FOLDER / f'{code}.pdf'
    url = f'https://www.statistics.gov.lk/Resource/en/InflationAndPrices/retail/{code}.pdf'
    result = {'report': code, 'label': label, 'url': url}
    try:
        content = path.read_bytes() if path.exists() else get(url)
        if not content.startswith(b'%PDF'):
            result['status'] = 'unavailable'
        else:
            path.write_bytes(content)
            result.update(status='downloaded', sha256=hashlib.sha256(content).hexdigest(), bytes=len(content))
    except Exception as error:
        result.update(status='unavailable', error=str(error))
    return result


if __name__ == '__main__':
    FOLDER.mkdir(parents=True, exist_ok=True)
    html = get(INDEX)
    (FOLDER / 'index.html').write_bytes(html)
    soup = BeautifulSoup(html, 'html.parser')
    links = {}
    for a in soup.select('a[href]'):
        match = re.search(r'DCSB-WRP-(20\d{2})-(\d{2})-W([1-4])', a['href'])
        if match and int(match[1]) >= 2018:
            links[match[0]] = a.get_text(strip=True)
    results = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks = [pool.submit(download, item) for item in sorted(links.items(), reverse=True)]
        for future in as_completed(tasks):
            results.append(future.result())
            if len(results) % 40 == 0:
                print(f'{len(results)}/{len(tasks)} reports checked', flush=True)
    results.sort(key=lambda r: r['report'])
    (FOLDER / 'manifest.json').write_text(json.dumps({'index_url': INDEX, 'retrieved': datetime.now(ZoneInfo('Asia/Colombo')).date().isoformat(), 'reports': results}, indent=2))
    print('Downloaded', sum(r['status'] == 'downloaded' for r in results), 'of', len(results), flush=True)
