"""Hintergrundpaletten nach der Attributregel der 8-Bit-Konsole:
gemeinsame Grundfarbe (Schwarz) + 4 Paletten zu je 3 Systemfarben, jeder 16x16-Block wählt eine Palette.

Vorgehen: Abstand jedes Bildpixels (Oklab, aus dem Original-RGB) zu jeder Kandidatenfarbe; abwechselnd
(a) jeden Block der Palette mit dem kleinsten Fehler zuordnen, (b) je Palette das beste Farbtripel aus den
Kandidaten suchen (vollständige Suche). Feste Farben je Palette sind möglich (z. B. Weiß für das Textfenster),
wichtige Bildteile bekommen ein Gewicht."""
import itertools
import numpy as np
import neslib


def block_view(a, bs=16):
    H, W = a.shape[:2]
    rest = a.shape[2:]
    a = a.reshape(H // bs, bs, W // bs, bs, *rest)
    return np.moveaxis(a, 2, 1).reshape(H // bs, W // bs, bs * bs, *rest)


def optimize(lab, weight, cands, init, fixed=None, backdrop=neslib.BLACK, iters=12, forced=None, log=print):
    """lab: HxWx3 Oklab, weight: HxW. cands: Liste Systemfarben. init: 4 Tripel. fixed: {pal: [farben]}.
    forced: {(by,bx): pal} Blöcke mit fester Palette. Rückgabe: pals (4x3), assign (H/16 x W/16), fehler."""
    fixed = fixed or {}
    forced = forced or {}
    cands = list(cands)
    allc = sorted(set(cands) | {backdrop} | {c for t in init for c in t} | {c for v in fixed.values() for c in v})
    pos = {c: i for i, c in enumerate(allc)}
    d = ((lab[..., None, :] - neslib.SYS_LAB[allc][None, None]) ** 2).sum(-1)   # HxWxC
    db = block_view(d)                       # BYxBXx256xC
    wb = block_view(weight)                  # BYxBXx256
    BY, BX = db.shape[:2]
    bd = db[..., pos[backdrop]]

    def block_err(trip):
        m = np.minimum(bd, db[..., [pos[c] for c in trip]].min(-1))
        return (m * wb).sum(-1)              # BYxBX

    pals = [list(t) for t in init]
    for it in range(iters):
        errs = np.stack([block_err(p) for p in pals], -1)
        assign = errs.argmin(-1)
        for (by, bx), p in forced.items():
            assign[by, bx] = p
        total = errs[np.arange(BY)[:, None], np.arange(BX)[None], assign].sum()
        log(f"  Durchgang {it}: Fehler {total:.1f}, Paletten " +
            " | ".join(" ".join(f"{c:02X}" for c in p) for p in pals) +
            "  Blöcke je Palette " + str(np.bincount(assign.ravel(), minlength=4).tolist()))
        changed = False
        for k in range(4):
            sel = assign == k
            if not sel.any():
                continue
            dk = db[sel]                     # Nx256xC
            wk = wb[sel]
            bk = bd[sel]
            fx = list(fixed.get(k, []))
            free = 3 - len(fx)
            pool = [c for c in cands if c not in fx and c != backdrop]
            best = None
            for combo in itertools.combinations(pool, free):
                trip = fx + list(combo)
                m = np.minimum(bk, dk[..., [pos[c] for c in trip]].min(-1))
                e = (m * wk).sum()
                if best is None or e < best[0]:
                    best = (e, trip)
            if sorted(best[1]) != sorted(pals[k]):
                pals[k] = sorted(best[1], key=lambda c: neslib.SYS_LAB[c][0])
                changed = True
        if not changed:
            break
    errs = np.stack([block_err(p) for p in pals], -1)
    assign = errs.argmin(-1)
    for (by, bx), p in forced.items():
        assign[by, bx] = p
    return [list(p) for p in pals], assign


def render(lab, pals, assign, backdrop=neslib.BLACK):
    """Je Pixel die nächste Farbe aus Grundfarbe + Blockpalette: Farbnummer 0..3 und Systemfarbe."""
    H, W = lab.shape[:2]
    ci = np.zeros((H, W), np.uint8)
    sysc = np.zeros((H, W), np.int32)
    for by in range(H // 16):
        for bx in range(W // 16):
            opts = [backdrop] + list(pals[assign[by, bx]])
            blk = lab[by * 16:(by + 1) * 16, bx * 16:(bx + 1) * 16]
            dd = ((blk[..., None, :] - neslib.SYS_LAB[opts][None, None]) ** 2).sum(-1)
            k = dd.argmin(-1)
            ci[by * 16:(by + 1) * 16, bx * 16:(bx + 1) * 16] = k
            sysc[by * 16:(by + 1) * 16, bx * 16:(bx + 1) * 16] = np.array(opts)[k]
    return ci, sysc
