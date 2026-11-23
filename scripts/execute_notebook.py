from pathlib import Path
import os
import nbformat
from nbclient import NotebookClient

root = Path(__file__).resolve().parents[1]
local_jupyter = root / '.jupyter'
os.environ['JUPYTER_PATH'] = str(local_jupyter)
os.environ['JUPYTER_RUNTIME_DIR'] = str(local_jupyter / 'runtime')
os.environ['IPYTHONDIR'] = str(local_jupyter / 'ipython')
os.environ['MPLCONFIGDIR'] = str(local_jupyter / 'matplotlib')
import json
kernel = local_jupyter / 'kernels/python3'
kernel.mkdir(parents=True, exist_ok=True)
(kernel / 'kernel.json').write_text(json.dumps({'argv': [str(root / '.venv/bin/python'), '-m', 'ipykernel_launcher', '-f', '{connection_file}'], 'display_name': 'Food Lens', 'language': 'python'}))
path = root / 'notebooks/food_price_ensembles.ipynb'
nb = nbformat.read(path, as_version=4)
NotebookClient(nb, timeout=300, kernel_name='python3', resources={'metadata': {'path': str(root)}}, allow_errors=False).execute()
nbformat.write(nb, path)
print('Notebook executed and saved with outputs.')
