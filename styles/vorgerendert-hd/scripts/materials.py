"""Deterministic, tileable fabric and leather detail for the shared character's PBR materials."""
from pathlib import Path
import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / 'demo/textures'
OUT.mkdir(exist_ok=True)
y, x = np.mgrid[:256, :256]
for name, height in {
    'cloth': 0.5 + 0.20 * np.sin(x * np.pi / 4) * np.sin(y * np.pi / 4),
    'knit': 0.5 + 0.25 * np.cos((x + 3 * np.sin(y * np.pi / 16)) * np.pi / 8) * np.cos(y * np.pi / 16),
    'leather': 0.5 + 0.10 * np.sin(x * np.pi / 8 + np.sin(y * np.pi / 16)) + 0.08 * np.cos(y * np.pi / 4),
}.items():
    color = np.clip(0.86 + 0.18 * height, 0, 1)
    Image.fromarray(np.repeat((color * 255).astype(np.uint8)[..., None], 3, axis=2)).save(OUT / f'{name}.png')
    dx = np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)
    dy = np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)
    normal = np.stack([-dx * 0.6, -dy * 0.6, np.ones_like(dx)], axis=2)
    normal /= np.linalg.norm(normal, axis=2)[..., None]
    Image.fromarray(np.rint((normal * 0.5 + 0.5) * 255).astype(np.uint8)).save(OUT / f'{name}_normal.png')
