"""Textmodus-Bildschirm zum Zeichnen und Prüfen: 80×25 Zellen, je Zelle ein CP437-Zeichen und ein Attributbyte.

Attributbyte wie im PC-Textmodus (Blinken eingeschaltet):
    Bit 0–3  Vordergrund (16 Farben)
    Bit 4–6  Hintergrund (nur 8 Farben)
    Bit 7    Blinken (Vordergrund verschwindet in der Aus-Phase)

Halbblock-Raster: Jede Zelle ist oben/unten zwei „Pixel“ (▀ ▄ █ Leerzeichen). Zwei helle Farben (8–15) in einer
Zelle gehen nicht, weil der Hintergrund nur 0–7 kennt; resolve() dunkelt dann eine Hälfte ab und zählt den Fall.
"""
import json, pathlib

import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = ROOT / "demo" / "fonts"

# Standard-Textmoduspalette (RGBI, Farbe 6 als Braun)
PALETTE = [
    (0x00, 0x00, 0x00), (0x00, 0x00, 0xAA), (0x00, 0xAA, 0x00), (0x00, 0xAA, 0xAA),
    (0xAA, 0x00, 0x00), (0xAA, 0x00, 0xAA), (0xAA, 0x55, 0x00), (0xAA, 0xAA, 0xAA),
    (0x55, 0x55, 0x55), (0x55, 0x55, 0xFF), (0x55, 0xFF, 0x55), (0x55, 0xFF, 0xFF),
    (0xFF, 0x55, 0x55), (0xFF, 0x55, 0xFF), (0xFF, 0xFF, 0x55), (0xFF, 0xFF, 0xFF),
]
BLACK, BLUE, GREEN, CYAN, RED, MAGENTA, BROWN, LGRAY = range(8)
DGRAY, LBLUE, LGREEN, LCYAN, LRED, LMAGENTA, YELLOW, WHITE = range(8, 16)
COLOR_LETTERS = {  # für Sprite-Karten
    "k": BLACK, "b": BLUE, "g": GREEN, "c": CYAN, "r": RED, "m": MAGENTA, "n": BROWN, "l": LGRAY,
    "d": DGRAY, "B": LBLUE, "G": LGREEN, "C": LCYAN, "R": LRED, "M": LMAGENTA, "y": YELLOW, "w": WHITE,
}

_meta = json.loads((FONT_DIR / "cp437.json").read_text(encoding="utf-8"))
CHARS = _meta["chars"]
CW, CH = _meta["cell"]
CODE = {c: i for i, c in enumerate(CHARS)}
SPACE, FULL, UPPER, LOWER, LEFT, RIGHT = (CODE[c] for c in " █▀▄▌▐")
SHADES = (CODE["░"], CODE["▒"], CODE["▓"])


def code(ch):
    if isinstance(ch, int):
        return ch
    if ch not in CODE:
        raise KeyError(f"Zeichen {ch!r} (U+{ord(ch):04X}) gibt es in CP437 nicht")
    return CODE[ch]


def _load_glyphs():
    a = np.asarray(Image.open(FONT_DIR / f"cp437_{CW}x{CH}.png"))[..., 3] > 0
    g = a.reshape(16, CH, 16, CW).transpose(0, 2, 1, 3).reshape(256, CH, CW)
    return g


GLYPHS = _load_glyphs()


def resolve(top, bottom):
    """Zwei Halbpixel-Farben -> (Zeichen, fg, bg, Konflikt). Konflikt: beide hell, unten wird abgedunkelt."""
    if top == bottom:
        return (SPACE, LGRAY, top, False) if top < 8 else (FULL, top, BLACK, False)
    if bottom < 8:
        return UPPER, top, bottom, False
    if top < 8:
        return LOWER, bottom, top, False
    return UPPER, top, bottom - 8, True


class Screen:
    W, H = 80, 25

    def __init__(self, bg=BLACK):
        self.ch = np.full((self.H, self.W), SPACE, np.uint8)
        self.fg = np.full((self.H, self.W), LGRAY, np.uint8)
        self.bg = np.full((self.H, self.W), bg, np.uint8)
        self.blink = np.zeros((self.H, self.W), bool)
        self.conflicts = 0
        self.conflict_cells = []

    def inside(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H

    # --- Zellen -----------------------------------------------------------------------------------------
    def cell(self, x, y, ch=None, fg=None, bg=None, blink=None):
        if not self.inside(x, y):
            return
        if ch is not None:
            self.ch[y, x] = code(ch)
        if fg is not None:
            self.fg[y, x] = fg
        if bg is not None:
            if bg > 7:
                raise ValueError(f"Hintergrund {bg} > 7 bei ({x},{y})")
            self.bg[y, x] = bg
        if blink is not None:
            self.blink[y, x] = blink

    def text(self, x, y, s, fg=None, bg=None, blink=None):
        for i, c in enumerate(s):
            self.cell(x + i, y, c, fg, bg, blink)

    def fill(self, x0, y0, x1, y1, ch=" ", fg=None, bg=None):
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                self.cell(x, y, ch, fg, bg)

    # --- Halbpixel ---------------------------------------------------------------------------------------
    def halves(self, x, y):
        """Farben der oberen und unteren Zellhälfte (bei Schattier- und Textzeichen: Hintergrund)."""
        c, f, b = self.ch[y, x], self.fg[y, x], self.bg[y, x]
        if c == FULL:
            return f, f
        if c == UPPER:
            return f, b
        if c == LOWER:
            return b, f
        if c == SHADES[2]:
            return f, f
        return b, b

    def px(self, x, py, color):
        """Halbpixel setzen; py zählt Halbzeilen ab Bildschirmoberkante (0..49)."""
        y, half = divmod(py, 2)
        if not self.inside(x, y) or color is None:
            return
        t, b = self.halves(x, y)
        if half == 0:
            t = color
        else:
            b = color
        c, f, bg, conflict = resolve(t, b)
        self.ch[y, x], self.fg[y, x], self.bg[y, x] = c, f, bg
        self.blink[y, x] = False
        if conflict:
            self.conflicts += 1
            self.conflict_cells.append((x, y))

    def px_rect(self, x0, py0, x1, py1, color):
        for py in range(py0, py1 + 1):
            for x in range(x0, x1 + 1):
                self.px(x, py, color)

    def sprite(self, x, py, rows, glyphs=None):
        """Sprite aus Buchstabenkarte (COLOR_LETTERS, '.' = durchsichtig) an Halbpixel-Position zeichnen.
        glyphs: Liste gleicher Höhe/2 mit Zeichenkarten; Zeichen dort ersetzen die Zelle (fg aus Karte unten)."""
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != ".":
                    self.px(x + i, py + j, COLOR_LETTERS[ch])

    # --- Ausgabe -------------------------------------------------------------------------------------------
    def attrs(self):
        return (self.fg & 15) | ((self.bg & 7) << 4) | (self.blink.astype(np.uint8) << 7)

    def render(self, blink_on=True, scale=1):
        pal = np.array(PALETTE, np.uint8)
        g = GLYPHS[self.ch]                                     # (H, W, CH, CW)
        vis = g & ~(self.blink & ~blink_on)[..., None, None]
        fg = pal[self.fg][:, :, None, None, :]
        bg = pal[self.bg][:, :, None, None, :]
        img = np.where(vis[..., None], fg, bg)                  # (H, W, CH, CW, 3)
        img = img.transpose(0, 2, 1, 3, 4).reshape(self.H * CH, self.W * CW, 3)
        im = Image.fromarray(img)
        if scale != 1:
            im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        return im

    def copy(self):
        s = Screen()
        s.ch, s.fg, s.bg, s.blink = self.ch.copy(), self.fg.copy(), self.bg.copy(), self.blink.copy()
        s.conflicts = self.conflicts
        return s


# --- ANSI-Datei (.ans) -----------------------------------------------------------------------------------
ANSI_ORDER = [0, 4, 2, 6, 1, 5, 3, 7]   # ANSI-Farbnummer -> PC-Farbe (ANSI 1 = rot, PC 1 = blau)
PC_TO_ANSI = {pc: i for i, pc in enumerate(ANSI_ORDER)}


def write_ans(scr, path, rows=None, title="", author="", group=""):
    rows = rows if rows is not None else range(scr.H)
    out = bytearray(b"\x1b[0m")
    for y in rows:
        cur = None
        for x in range(scr.W):
            f, b, bl = int(scr.fg[y, x]), int(scr.bg[y, x]), bool(scr.blink[y, x])
            if (f, b, bl) != cur:
                parts = ["0"]
                if f > 7:
                    parts.append("1")
                if bl:
                    parts.append("5")
                parts += [str(30 + PC_TO_ANSI[f & 7]), str(40 + PC_TO_ANSI[b])]
                out += ("\x1b[" + ";".join(parts) + "m").encode()
                cur = (f, b, bl)
            c = int(scr.ch[y, x])
            if c in (0x0A, 0x0D, 0x1A, 0x1B):                   # Steuerbytes im Datenstrom nicht erlaubt
                raise ValueError(f"Zeichen {c:#04x} bei ({x},{y}) lässt sich in .ans nicht speichern")
            out.append(c)
        # 80 Zeichen je Zeile: Zeilenumbruch kommt durch den automatischen Umbruch des Betrachters
    out += b"\x1b[0m\x1a"
    nrows = len(list(rows))
    sauce = bytearray(b"SAUCE00")
    sauce += title.encode("cp437")[:35].ljust(35)
    sauce += author.encode("cp437")[:20].ljust(20)
    sauce += group.encode("cp437")[:20].ljust(20)
    sauce += b"20261011"
    sauce += (len(out) - 1).to_bytes(4, "little")
    sauce += bytes([1, 1])                                       # DataType Character, FileType ANSi
    sauce += (80).to_bytes(2, "little") + nrows.to_bytes(2, "little") + bytes(4)
    sauce += bytes([0])                                          # Kommentare
    sauce += bytes([0b00000010])                                 # TFlags: Buchstabenabstand 8 px
    sauce += b"IBM VGA".ljust(22, b"\0")
    assert len(sauce) == 128, len(sauce)
    pathlib.Path(path).write_bytes(bytes(out + sauce))


def read_ans(path, height):
    """Liest eine .ans (SGR-Farben, 80 Spalten, automatischer Umbruch, CR/LF, Cursor vor/zurück)."""
    data = pathlib.Path(path).read_bytes()
    if b"\x1a" in data:
        data = data[:data.index(b"\x1a")]
    scr = Screen()
    x = y = 0
    f, b, bold, bl = LGRAY, BLACK, False, False
    i = 0
    while i < len(data):
        c = data[i]
        if c == 0x1B and i + 1 < len(data) and data[i + 1] == ord("["):
            j = i + 2
            while j < len(data) and not (0x40 <= data[j] <= 0x7E):
                j += 1
            params, cmd = data[i + 2:j].decode(), chr(data[j])
            nums = [int(p) if p else 0 for p in params.split(";")] if params else [0]
            if cmd == "m":
                for n in nums:
                    if n == 0:
                        f, b, bold, bl = 7, 0, False, False
                    elif n == 1:
                        bold = True
                    elif n == 5:
                        bl = True
                    elif 30 <= n <= 37:
                        f = ANSI_ORDER[n - 30]
                    elif 40 <= n <= 47:
                        b = ANSI_ORDER[n - 40]
            elif cmd == "C":
                x += nums[0] or 1
            elif cmd == "D":
                x = max(0, x - (nums[0] or 1))
            elif cmd == "A":
                y = max(0, y - (nums[0] or 1))
            elif cmd == "B":
                y += nums[0] or 1
            elif cmd == "H":
                y, x = (nums + [1, 1])[0] - 1, (nums + [1, 1])[1] - 1
            i = j + 1
            continue
        if c == 0x0D:
            x = 0
        elif c == 0x0A:
            y += 1
        else:
            if x >= 80:                                         # automatischer Umbruch
                x, y = 0, y + 1
            if y < height:
                scr.ch[y, x] = c
                scr.fg[y, x] = f + (8 if bold else 0)
                scr.bg[y, x] = b
                scr.blink[y, x] = bl
            x += 1
        i += 1
    return scr
