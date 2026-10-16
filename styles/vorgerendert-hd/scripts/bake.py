"""Pack camera Z into lossless RGB24; copy linear HDR plates into the standalone demo."""
import json
import shutil
from pathlib import Path
import numpy as np
from PIL import Image

STYLE = Path(__file__).resolve().parent.parent
RAW = STYLE / 'assets/raw/render'
DEMO = STYLE / 'demo/bg'
DEMO.mkdir(parents=True, exist_ok=True)
shutil.copy2(RAW / 'panorama.exr', DEMO / 'panorama.exr')
for shot in ('totale', 'nah'):
    dst = DEMO / shot
    dst.mkdir(exist_ok=True)
    z = np.load(RAW / shot / 'depth.npy')
    encoded = np.rint(np.clip(z / 1000, 0, 1) * 16777215).astype(np.uint32)
    rgb = np.stack([(encoded >> 16) & 255, (encoded >> 8) & 255, encoded & 255], axis=2).astype(np.uint8)
    Image.fromarray(rgb).save(dst / 'depth.png')
    preview = np.clip(1 - np.log1p(np.minimum(z, 200)) / np.log1p(200), 0, 1)
    Image.fromarray((preview * 255).astype(np.uint8)).save(STYLE / 'assets/preview' / f'depth_{shot}.png')
    shutil.copy2(RAW / shot / 'preview.png', STYLE / 'assets/preview' / f'{shot}.png')
    for name in ('base.exr', 'camera.json'):
        shutil.copy2(RAW / shot / name, dst / name)
    print(shot, '1280×960 HDR + RGB24 depth', float(z.min()))
