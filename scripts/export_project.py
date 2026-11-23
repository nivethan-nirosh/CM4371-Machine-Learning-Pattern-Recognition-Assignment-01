from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import json

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / '224138H_FoodLens.zip'
PACKAGE = Path('224138H_FoodLens')
EXCLUDE = {'node_modules', 'dist', '__pycache__', '.ipynb_checkpoints', '.DS_Store'}
notebook = json.loads((ROOT / 'notebooks/food_price_ensembles.ipynb').read_text())
assert 'Nivethan R.' in ''.join(notebook['cells'][0]['source'])
assert '224138H' in ''.join(notebook['cells'][0]['source'])
for cell in notebook['cells']:
    if cell['cell_type'] == 'code':
        assert cell['execution_count'] is not None, 'Execute the notebook before exporting.'
        assert not any(o['output_type'] == 'error' for o in cell['outputs'])

files = [ROOT / name for name in ['README.md', 'SOURCES.md', 'AI_USAGE.md', 'requirements.txt', '.gitignore']]
for folder in ['frontend', 'backend', 'notebooks', 'scripts', 'data/processed']:
    files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and not any(part in EXCLUDE for part in p.relative_to(ROOT).parts))
files.extend(ROOT / 'data/raw/dcs' / name for name in ['manifest.json', 'index.html', 'extraction_summary.json'])
with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
    for path in sorted(set(files)):
        archive.write(path, PACKAGE / path.relative_to(ROOT))
with ZipFile(OUTPUT) as archive:
    assert archive.testzip() is None
    assert not any('/learning/' in name or 'VOICEOVER' in name or '/node_modules/' in name for name in archive.namelist())
print(OUTPUT)
print(f'{OUTPUT.stat().st_size / 1024**2:.2f} MiB, {len(files)} files')
