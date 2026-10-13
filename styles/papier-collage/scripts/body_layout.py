#!/usr/bin/env python3
"""Lagevorlage für die Nachbesserung des Rumpfteils (Bildauftrag badger_body).

Das KI-Bild assets/raw/badger_torso.png hat Kopf und Paket weggelassen, aber den nahen Arm und die Beine
behalten und über dem Schal eine dunkle Halskuppe ergänzt. Hier wird daraus eine grobe Vorlage: Kuppe über der
Schaloberkante weg, Beine unter dem Hüftfell weg, Arm (Ärmel, Unterarm, Pfote) durch flache Flecken in
Westen- bzw. Taschenfarbe ersetzt. agy zeichnet diese Flecken dann als Weste und Tasche fertig.

    .venv/bin/python styles/papier-collage/scripts/body_layout.py
"""
import pathlib
import numpy as np
from PIL import Image, ImageDraw

HERE = pathlib.Path(__file__).resolve().parent.parent
RAW = HERE / "assets" / "raw"
MAG = np.array([255, 0, 255])

src = np.asarray(Image.open(RAW / "badger_torso.keyed-src.png").convert("RGB")).astype(int)
alpha = np.asarray(Image.open(RAW / "badger_torso.png"))[..., 3] > 40
H, W = alpha.shape
out = src.copy()
out[~alpha] = MAG  # einheitlicher Grund (JPEG-Magenta schwankt)
r, g, b = src[..., 0], src[..., 1], src[..., 2]
red = (r > 140) & (g < 100) & (b < 110) & (r - g > 70)
yy, xx = np.mgrid[0:H, 0:W]

# 1) Halskuppe: in jeder Spalte des Schals alles oberhalb der ersten roten Zeile weg
top = np.full(W, -1)
for x in range(255, 600):
    ys = np.where(red[300:540, x])[0]
    if len(ys):
        top[x] = 300 + ys[0]
cols = np.where(top >= 0)[0]
med = top.copy()
for x in cols:  # Median über 9 Spalten glättet den Rand
    win = top[max(0, x - 4):x + 5]
    med[x] = int(np.median(win[win >= 0]))
for x in cols:
    out[:med[x], x] = MAG
# links und rechts des Schals stehen noch Kuppenränder (weißer Fellrand links)
dome = (xx >= 250) & (xx < 610) & (yy < 470) & alpha & ~red
dome &= (yy < np.where(top[np.clip(xx, 0, W - 1)] >= 0, med[np.clip(xx, 0, W - 1)], 470))
out[dome] = MAG
out[(xx >= 250) & (xx < 300) & (yy < 400) & (xx > 255)] = MAG  # Fellrand links der Kuppe

# 2) Beine: unterhalb des Hüftfells nur dunkles Fell behalten
L = src.mean(-1)
legs = (yy > 1030) & alpha & (L > 92)
out[legs] = MAG
out[(yy > 1068)] = MAG

# Reste: kleine Inseln (Krallen, Fellränder der Beine) unter der Hüfte entfernen
from collections import deque
keep = ~(out == MAG).all(-1)
seen = np.zeros_like(keep)
for y0 in range(980, H):
    for x0 in range(W):
        if keep[y0, x0] and not seen[y0, x0]:
            comp, q = [], deque([(y0, x0)])
            seen[y0, x0] = True
            while q:
                y, x = q.popleft(); comp.append((y, x))
                for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    v, u = y + dy, x + dx
                    if 0 <= v < H and 0 <= u < W and keep[v, u] and not seen[v, u]:
                        seen[v, u] = True; q.append((v, u))
            if len(comp) < 3000:
                for y, x in comp:
                    out[y, x] = MAG

# 3) Arm durch flache Flecken ersetzen (Polygone an der Rasteransicht abgelesen)
im = Image.fromarray(out.astype(np.uint8))
d = ImageDraw.Draw(im)
vest = (60, 110, 74)
leather = (136, 88, 56)
sleeve = [(240, 650), (246, 520), (282, 492), (350, 486), (404, 500), (422, 540), (424, 726), (246, 726)]
d.polygon(sleeve, fill=vest)
fore = [(262, 718), (428, 718), (444, 790), (462, 860), (446, 920), (352, 922), (318, 860), (276, 790)]
d.polygon(fore, fill=leather)
# Kante der Taschenklappe weiterführen (links bei y 885, rechts bei y 880)
d.line([(300, 886), (470, 878)], fill=(104, 64, 40), width=5)
im.save(HERE / "assets" / "refs" / "layout_body.png")
print("ok", HERE / "assets" / "refs" / "layout_body.png")
