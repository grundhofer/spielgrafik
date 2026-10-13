#!/usr/bin/env python3
"""Bilder als Zeichenbefehle wie in den Parser-Adventures 1984–1988 (Bildformat aus Linien und Flutfüllungen).

Ein Bild ist eine Liste von Befehlen auf zwei Ebenen, 160×168:
  sichtbare Ebene (Farben 0–15, startet weiß = 15) und Prioritätsebene (4–15, startet 4).
Befehle (JSON, so liest sie auch die Godot-Demo):
  ["c", v]            Farbe der sichtbaren Ebene setzen (v = -1: sichtbare Ebene aus)
  ["p", p]            Prioritätsfarbe setzen (p = -1: Prioritätsebene aus)
  ["l", [x0,y0,x1,y1,...]]   Linienzug (Linienalgorithmus wie unten, in GDScript identisch)
  ["s", [x,y,...]]    einzelne Punkte setzen
  ["f", [x,y,...]]    Flutfüllung je Startpunkt: füllt 4-zusammenhängend alle Pixel, die auf der sichtbaren
                      Ebene noch weiß sind (bzw. bei abgeschalteter sichtbarer Ebene auf der Prioritätsebene
                      noch 4); weiß lässt sich daher nicht füllen, sondern nur stehen lassen.
"""
import json

import numpy as np
from PIL import Image

W, H = 160, 168
EGA = ["000000", "0000aa", "00aa00", "00aaaa", "aa0000", "aa00aa", "aa5500", "aaaaaa",
       "555555", "5555ff", "55ff55", "55ffff", "ff5555", "ff55ff", "ffff55", "ffffff"]
EGA_RGB = np.array([[int(h[i:i + 2], 16) for i in (0, 2, 4)] for h in EGA], np.uint8)


def band(y):
    """Prioritätsband einer Fußzeile (wie im Original: unter y=48 Priorität 4, dann alle 12 Zeilen +1)."""
    return 4 if y < 48 else min(15, 5 + (y - 48) // 12)


def line_points(x1, y1, x2, y2):
    """Linienalgorithmus mit Fehlerakkumulator; GDScript-Fassung in demo/scripts/pic.gd ist identisch."""
    pts = []
    if x1 == x2:
        s = 1 if y2 >= y1 else -1
        return [(x1, y) for y in range(y1, y2 + s, s)]
    if y1 == y2:
        s = 1 if x2 >= x1 else -1
        return [(x, y1) for x in range(x1, x2 + s, s)]
    dy, sy = abs(y2 - y1), (1 if y2 >= y1 else -1)
    dx, sx = abs(x2 - x1), (1 if x2 >= x1 else -1)
    if dy > dx:
        i, det, ey, ex = dy, dy, dy // 2, 0
    else:
        i, det, ex, ey = dx, dx, dx // 2, 0
    x, y = x1, y1
    pts.append((x, y))
    while i > 0:
        ey += dy
        if ey >= det:
            ey -= det
            y += sy
        ex += dx
        if ex >= det:
            ex -= det
            x += sx
        pts.append((x, y))
        i -= 1
    return pts


class Pic:
    """Baukasten für Bilder; schreibt Befehle mit, führt sie zugleich aus (für Vorschau und Prüfung)."""

    def __init__(self):
        self.cmds = []
        self.vis = np.full((H, W), 15, np.uint8)
        self.pri = np.full((H, W), 4, np.uint8)
        self.v = -1
        self.p = -1
        self.work = 0          # berührte Pixel (für das Tempo des Bildaufbaus)
        self.notes = []        # (Befehlsindex, Text) zur Orientierung

    # --- Zustand ---
    def note(self, text):
        self.notes.append((len(self.cmds), text))
        return self

    def color(self, v):
        if v != self.v:
            self.v = v
            self.cmds.append(["c", v])
        return self

    def prio(self, p):
        if p != self.p:
            self.p = p
            self.cmds.append(["p", p])
        return self

    # --- Zeichnen ---
    def _plot(self, x, y):
        if 0 <= x < W and 0 <= y < H:
            if self.v >= 0:
                self.vis[y, x] = self.v
            if self.p >= 0:
                self.pri[y, x] = self.p
            self.work += 1

    def line(self, *pts):
        pts = [int(round(v)) for v in np.array(pts).flatten()]
        assert len(pts) >= 4 and len(pts) % 2 == 0, pts
        for k in range(0, len(pts) - 2, 2):
            for i, (x, y) in enumerate(line_points(*pts[k:k + 4])):
                if k > 0 and i == 0:
                    continue
                self._plot(x, y)
        self.cmds.append(["l", pts])
        return self

    def poly(self, *pts):
        """geschlossener Linienzug"""
        pts = [tuple(p) for p in pts]
        return self.line(*(pts + [pts[0]]))

    def dots(self, *pts):
        flat = [int(v) for v in np.array(pts).flatten()]
        for k in range(0, len(flat), 2):
            self._plot(flat[k], flat[k + 1])
        self.cmds.append(["s", flat])
        return self

    def fill(self, *pts):
        flat = [int(v) for v in np.array(pts).flatten()]
        for k in range(0, len(flat), 2):
            self._fill(flat[k], flat[k + 1])
        self.cmds.append(["f", flat])
        return self

    def _fill(self, x, y):
        if self.v >= 0:
            if self.v == 15:
                return
            plane, target = self.vis, 15
        elif self.p >= 0:
            if self.p == 4:
                return
            plane, target = self.pri, 4
        else:
            return
        if plane[y, x] != target:
            return
        stack = [(x, y)]
        while stack:
            cx, cy = stack.pop()
            if plane[cy, cx] != target:
                continue
            self._plot(cx, cy)
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if 0 <= nx < W and 0 <= ny < H and plane[ny, nx] == target:
                    stack.append((nx, ny))

    # --- Ausgabe ---
    def to_json(self):
        return {"w": W, "h": H, "work": self.work, "commands": self.cmds}

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_json(), f, separators=(",", ":"))


def replay(cmds):
    """Führt eine Befehlsliste aus (wie die Godot-Demo) und gibt (vis, pri) zurück."""
    p = Pic()
    for c in cmds:
        op, arg = c
        if op == "c":
            p.color(arg)
        elif op == "p":
            p.prio(arg)
        elif op == "l":
            p.line(*arg)
        elif op == "s":
            p.dots(*arg)
        elif op == "f":
            p.fill(*arg)
    return p.vis, p.pri


def to_rgb(idx, double=True):
    rgb = EGA_RGB[idx]
    if double:
        rgb = np.repeat(rgb, 2, axis=1)
    return Image.fromarray(rgb)
