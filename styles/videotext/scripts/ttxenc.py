#!/usr/bin/env python3
"""Mosaik-Zeilen nach den Videotext-Regeln kodieren (dynamische Programmierung je Zeile).

Eingabe je Zeichenzeile: Zielfarben der 2×3 Sechstel je Zelle (80 × 3 Mosaikpunkte, Farbnummer 0–7 oder -1 =
egal), optional eine zweite Zielfarbe für die Aus-Phase des Blinkens, Gewichte je Mosaikpunkt und je Zelle der
Wunsch „getrennt“/„zusammenhängend“. Gesucht ist die Bytefolge (40 Bytes), deren dekodierte Anzeige die
gewichtete Farbabweichung minimiert. Der Zustand des Decoders je Spalte ist
(Modus, Vordergrund, Hintergrund, getrennt, Hold, Flash, gehaltenes Zeichen) = 32 768 Zustände.

Erlaubte Bytes: Mosaikzeichen und die Steuerzeichen Mosaik-Farbe 11–17, New Background 1D, Black Background 1C,
Contiguous 19, Separated 1A, Hold 1E, Release 1F, Flash 08, Steady 09. Schwarz als Vordergrund gibt es in
Level 1 nicht (0x10 ist dort kein Steuerzeichen); Schwarz entsteht nur als Hintergrund.
Die Kostenrechnung ist dieselbe wie im Decoder (ttxlib.decode_row); check_row() prüft das für jede Zeile.
"""
import numpy as np

import ttxlib as T

SHAPE = (2, 8, 8, 2, 2, 2, 64, 2)       # mode, fg, bg, sep, hold, flash, held, held_sep
NS = int(np.prod(SHAPE))
M_, FG_, BG_, SEP_, HOLD_, FL_, HELD_, HSEP_ = np.unravel_index(np.arange(NS), SHAPE)
SEP_PENALTY = 50.0   # gehaltenes Zeichen im falschen Trennmodus (z. B. getrennter Strahl als Lampe)


def sidx(mode, fg, bg, sep, hold, flash, held, hsep=0):
    return np.ravel_multi_index((mode, fg, bg, sep, hold, flash, held, hsep), SHAPE)


def _oklab(rgb):
    c = rgb / 255.0
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    l = 0.4122214708 * c[:, 0] + 0.5363325363 * c[:, 1] + 0.0514459929 * c[:, 2]
    m = 0.2119034982 * c[:, 0] + 0.6806995451 * c[:, 1] + 0.1073969566 * c[:, 2]
    s = 0.0883024619 * c[:, 0] + 0.2817188376 * c[:, 1] + 0.6299787005 * c[:, 2]
    l, m, s = np.cbrt(l), np.cbrt(m), np.cbrt(s)
    return np.stack([0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                     1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                     0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s], 1)


_LAB = _oklab(PAL := T.PALETTE.astype(np.float64))
# Abstand je Farbpaar (Zeile = Ziel, Spalte = Anzeige): Oklab-Abstand plus 0,25 für jede falsche Farbe, plus
# 0,4, wenn statt der Zielfarbe eine andere bunte Farbe erscheint. Eine Lücke in Hintergrundfarbe Schwarz ist im
# Videotext normal; fremdfarbige Splitter (rote Punkte im Pflaster) stören mehr, als der Oklab-Abstand sagt.
DIST = np.sqrt(((_LAB[:, None] - _LAB[None]) ** 2).sum(-1))
DIST = np.where(DIST > 0, 0.25 + DIST + 0.4 * (np.arange(8)[None, :] != 0), 0.0)

# Steuerzeichen: (Byte, Set-At?, Wirkung)
CONTROLS = [(0x10 + c, False, ("fg", c)) for c in range(1, 8)] + [
    (T.NEWBG, True, ("newbg",)), (T.BLACKBG, True, ("blackbg",)),
    (T.CONTIG, True, ("sep", 0)), (T.SEPAR, True, ("sep", 1)),
    (T.HOLD, True, ("hold", 1)), (T.RELEASE, False, ("hold", 0)),
    (T.FLASH, False, ("flash", 1)), (T.STEADY, True, ("flash", 0))]


def _apply(eff, mode, fg, bg, sep, hold, flash, held, hsep):
    mode, fg, bg, sep, hold, flash, held, hsep = [np.array(v) for v in (mode, fg, bg, sep, hold, flash, held, hsep)]
    if eff[0] == "fg":
        held = np.where(mode == 0, 0, held)
        hsep = np.where(mode == 0, 0, hsep)
        fg = np.full_like(fg, eff[1]); mode = np.ones_like(mode)
    elif eff[0] == "newbg":
        bg = fg.copy()
    elif eff[0] == "blackbg":
        bg = np.zeros_like(bg)
    elif eff[0] == "sep":
        sep = np.full_like(sep, eff[1])
    elif eff[0] == "hold":
        hold = np.full_like(hold, eff[1])
    elif eff[0] == "flash":
        flash = np.full_like(flash, eff[1])
    return mode, fg, bg, sep, hold, flash, held, hsep


def _precompute():
    acts = []
    st = (M_, FG_, BG_, SEP_, HOLD_, FL_, HELD_, HSEP_)
    for byte, set_at, eff in CONTROLS:
        new = _apply(eff, *st)
        disp = new if set_at else st
        dm, dfg, dbg, _, dhold, dfl, dheld, dhsep = disp
        pat = np.where((dm == 1) & (dhold == 1), dheld, 0)
        di = np.ravel_multi_index((pat, dfg, dbg, dfl), (64, 8, 8, 2))
        dsep = np.where(pat > 0, dhsep, -1)         # Trennmodus des angezeigten gehaltenen Zeichens
        ns = np.ravel_multi_index(new, SHAPE)
        acts.append((byte, ns.astype(np.int64), di.astype(np.int64), dsep.astype(np.int8)))
    return acts


ACTS = _precompute()
ROW_START = int(sidx(0, 7, 0, 0, 0, 0, 0))


def cell_table(t_on, t_off, w):
    """Kosten aller Anzeigen (Muster, fg, bg, flash) einer Zelle; t_on/t_off/w: je 6 Sechstel."""
    D = np.vstack([DIST, np.zeros((1, 8))])          # D[Ziel, Anzeige], Zeile 8 = egal (-1)
    on = np.where(t_on < 0, 8, t_on)
    off = np.where(t_off < 0, 8, t_off)
    # c[s, Anzeige an, Anzeige aus]
    c = (D[on][:, :, None] + D[off][:, None, :]) * w[:, None, None]   # (6, 8, 8)
    tab = np.zeros((64, 8, 8, 2))
    fg = np.arange(8)[:, None]
    bg = np.arange(8)[None, :]
    for s in range(6):
        bit = (np.arange(64) >> s) & 1
        steady_on = c[s][fg, fg]          # Sechstel an, kein Flash: fg in beiden Phasen
        flash_on = c[s][fg, bg]           # Sechstel an, Flash: fg / bg
        off_ = c[s][bg, bg]               # Sechstel aus: bg
        tab[:, :, :, 0] += np.where(bit[:, None, None] == 1, steady_on[None], off_[None])
        tab[:, :, :, 1] += np.where(bit[:, None, None] == 1, flash_on[None], off_[None])
    return tab.ravel()


EPS = 1e-3      # Steuerzeichen kosten minimal mehr: bei Gleichstand gewinnt das Mosaikzeichen


def encode_row(t_on, t_off=None, w=None, sepwish=None, c0=0, c1=T.COLS, start=ROW_START, end_ok=None,
               allowed_fg=range(1, 8), fixed=None):
    """t_on: (3, 80) Zielfarben; liefert (Bytes für Spalten c0..c1-1, Kosten, Endzustand).
    sepwish je Zelle: 1 = Mosaik getrennt, 0 = zusammenhängend, -1 = egal (leere Mosaike sind immer erlaubt).
    end_ok: optional bool-Feld über alle Zustände, welche Endzustände erlaubt sind.
    fixed: {Spalte: Byte} erzwingt dort ein Steuer- oder Mosaikzeichen."""
    t_on = np.asarray(t_on)
    t_off = t_on if t_off is None else np.asarray(t_off)
    w = np.ones(t_on.shape) if w is None else np.asarray(w, dtype=np.float64)
    sepwish = np.full(T.COLS, -1) if sepwish is None else np.asarray(sepwish)
    fixed = fixed or {}
    bad_fg = np.array([f not in allowed_fg for f in range(8)])
    cost = np.full(NS, np.inf)
    cost[start] = 0.0
    bps, bpb = [], []
    for col in range(c0, c1):
        sl = slice(2 * col, 2 * col + 2)
        on6 = t_on[:, sl].reshape(-1)       # Reihenfolge: Zeile, dann Spalte = Sechstel 0..5
        off6 = t_off[:, sl].reshape(-1)
        w6 = w[:, sl].reshape(-1)
        tab = cell_table(on6, off6, w6)
        live = np.nonzero(np.isfinite(cost))[0]
        new = np.full(NS, np.inf)
        bp_s = np.full(NS, -1, dtype=np.int64)
        bp_b = np.zeros(NS, dtype=np.int16)
        fx = fixed.get(col)
        cand = []
        for byte, ns, di, dsep in ACTS:
            if 0x11 <= byte <= 0x17 and bad_fg[byte - 0x10] and fx != byte:
                continue
            if fx is not None and fx != byte:
                continue
            cc = cost[live] + tab[di[live]] + EPS
            if sepwish[col] >= 0:
                ds = dsep[live]
                cc = cc + SEP_PENALTY * ((ds >= 0) & (ds != sepwish[col]))
            cand.append((byte, live, ns[live], cc))
        t3 = tab.reshape(64, 8, 8, 2)
        m = live[M_[live] == 1]
        if fx is not None and fx >= 0x20:
            # erzwungenes Mosaikzeichen
            p = np.full(len(m), T.mosaic_pattern(fx))
            if len(m):
                ns = np.ravel_multi_index((M_[m], FG_[m], BG_[m], SEP_[m], HOLD_[m], FL_[m], p, SEP_[m]), SHAPE)
                cc = cost[m] + t3[p, FG_[m], BG_[m], FL_[m]]
                if sepwish[col] >= 0 and T.mosaic_pattern(fx):
                    cc = cc + SEP_PENALTY * (SEP_[m] != sepwish[col])
                cand.append((-1, m, ns, cc))
        elif fx is None and len(m):
            # Mosaikzeichen: bestes Muster je (fg, bg, flash); bei falschem Trennmodus nur das leere Zeichen
            bestp = t3.argmin(0)                 # (8, 8, 2)
            bestc = t3.min(0)
            ok = np.ones(len(m), dtype=bool) if sepwish[col] < 0 else SEP_[m] == sepwish[col]
            p = np.where(ok, bestp[FG_[m], BG_[m], FL_[m]], 0)
            cc = np.where(ok, bestc[FG_[m], BG_[m], FL_[m]], t3[0, FG_[m], BG_[m], FL_[m]])
            ns = np.ravel_multi_index((M_[m], FG_[m], BG_[m], SEP_[m], HOLD_[m], FL_[m], p, SEP_[m]), SHAPE)
            cand.append((-1, m, ns, cost[m] + cc))
        for byte, src, ns, cc in cand:
            np.minimum.at(new, ns, cc)
        for byte, src, ns, cc in cand:
            hit = (cc == new[ns]) & (bp_s[ns] < 0)
            # bei mehrfachen Treffern auf dieselbe Zielzelle gewinnt der erste
            hs, hn = src[hit], ns[hit]
            uniq, first = np.unique(hn, return_index=True)
            bp_s[uniq] = hs[first]
            bp_b[uniq] = byte
        bps.append(bp_s); bpb.append(bp_b)
        cost = new
    final = cost if end_ok is None else np.where(end_ok, cost, np.inf)
    s = int(np.argmin(final))
    total = float(final[s])
    if not np.isfinite(total):
        raise RuntimeError("keine gültige Kodierung")
    end_state = s
    out = []
    for k in range(len(bps) - 1, -1, -1):
        b = int(bpb[k][s])
        prev = int(bps[k][s])
        out.append(T.mosaic_byte(int(HELD_[s])) if b == -1 else b)
        s = prev
    return out[::-1], total, end_state


def decoder_state(row, upto):
    """Zustand des Decoders vor Spalte `upto` (als Zustandsindex)."""
    fg, bg, mosaic, sep, hold, flash = 7, 0, False, False, False, False
    held, hsep = 0, 0
    for b in row[:upto]:
        b &= 0x7F
        if b < 0x20:
            if b == T.STEADY: flash = False
            elif b == T.CONTIG: sep = False
            elif b == T.SEPAR: sep = True
            elif b == T.BLACKBG: bg = 0
            elif b == T.NEWBG: bg = fg
            elif b == T.HOLD: hold = True
            if 0x01 <= b <= 0x07:
                if mosaic: held, hsep = 0, 0
                fg, mosaic = b, False
            elif b == T.FLASH: flash = True
            elif 0x11 <= b <= 0x17:
                if not mosaic: held, hsep = 0, 0
                fg, mosaic = b - 0x10, True
            elif b == T.RELEASE: hold = False
        elif mosaic and (b & 0x20):
            held, hsep = T.mosaic_pattern(b), int(sep)
    return int(sidx(int(mosaic), fg, bg, int(sep), int(hold), int(flash), held, hsep))


def end_mask_for(row, c1):
    """Erlaubte Endzustände eines Fensters: gleich wie im Grundbild an Spalte c1; das gehaltene Zeichen nur, wenn
    es im Rest der Zeile vor dem nächsten Mosaikzeichen angezeigt würde."""
    s = decoder_state(row, c1)
    vals = np.unravel_index(s, SHAPE)
    mask = np.ones(NS, dtype=bool)
    for ax, v in enumerate(vals[:6]):
        mask &= np.unravel_index(np.arange(NS), SHAPE)[ax] == v
    # Braucht der Rest das gehaltene Zeichen?
    mode, hold = vals[0], vals[4]
    need = False
    for b in row[c1:]:
        b &= 0x7F
        if b >= 0x20:
            if mode and (b & 0x20):
                break
            continue
        if b == T.HOLD: hold = 1
        if hold and mode:
            need = True
            break
        if 0x01 <= b <= 0x07: break            # Moduswechsel löscht das Zeichen
        if 0x11 <= b <= 0x17: mode = 1
        if b == T.RELEASE: hold = 0
    if need:
        mask &= (HELD_ == vals[6]) & (HSEP_ == vals[7])
    return mask


def shown(row_bytes, r0=0):
    """Angezeigte Sechstelfarben (3, 80) beider Blinkphasen für eine Zeile."""
    cells, _ = T.decode_row(row_bytes)
    on = np.zeros((3, 80), dtype=int); off = np.zeros((3, 80), dtype=int)
    for c, (k, code, sep, fg, bg, fl, dh) in enumerate(cells):
        for i in range(6):
            bit = k == T.MOSAIC and (code >> i & 1)
            on[i // 2, 2 * c + i % 2] = fg if bit else bg
            off[i // 2, 2 * c + i % 2] = fg if (bit and not fl) else bg
    return on, off


def row_cost(row_bytes, t_on, t_off=None, w=None):
    t_on = np.asarray(t_on)
    t_off = t_on if t_off is None else np.asarray(t_off)
    w = np.ones(t_on.shape) if w is None else np.asarray(w)
    on, off = shown(row_bytes)
    D = np.vstack([DIST, np.zeros((1, 8))])
    ton = np.where(t_on < 0, 8, t_on); toff = np.where(t_off < 0, 8, t_off)
    return float((w * (D[ton, on] + D[toff, off])).sum())
