"""Lage und Paletten des BG3-Textfensters wie in demo/scripts/bg3.gd und main.gd (für probe.py)."""
import re, pathlib

DEMO = pathlib.Path(__file__).resolve().parent.parent / 'demo'


def _rect(name):
    s = (DEMO / 'scripts/bg3.gd').read_text()
    m = re.search(rf'const {name} := Rect2i\((\d+), (\d+), (\d+), (\d+)\)', s)
    return tuple(int(v) for v in m.groups())


BOX = _rect('BOX')
TITLE = _rect('TITLE')


def _c5(v):
    return (v << 3) | (v >> 2)


def bg3_palettes():
    s = (DEMO / 'scripts/main.gd').read_text()
    fills = re.search(r'const BG3_FILL := \[(.*)\]\n', s).group(1)
    fills = [tuple(int(x) for x in g.split(',')) for g in re.findall(r'\[([\d, ]+)\]', fills)]
    light = tuple(int(x) for x in re.search(r'const BG3_LIGHT := \[([\d, ]+)\]', s).group(1).split(','))
    dark = tuple(int(x) for x in re.search(r'const BG3_DARK := \[([\d, ]+)\]', s).group(1).split(','))
    out = []
    for f in fills:
        out.append({tuple(_c5(v) for v in f), tuple(_c5(v) for v in light), tuple(_c5(v) for v in dark)})
    return out
