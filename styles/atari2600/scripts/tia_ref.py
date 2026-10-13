"""Gemeinsame Grundlagen für den Eintrag atari2600: NTSC-Palette und ein Referenz-Renderer des Videochips.

Der Renderer arbeitet mit derselben Zeilentabelle wie demo/shaders/tia.gdshader (eine Registerbelegung je
Bildzeile) und dient nur für Vorschaubilder beim Bauen; das Demo-Bild rechnet der Shader in Godot.

Farbwerte: NTSC-Palette in der verbreiteten Fassung des Emulators Stella. Ein Farbregister enthält
Farbton (Bit 7-4) und Helligkeit (Bit 3-1); Bit 0 wird ignoriert -> 16 x 8 = 128 Farben.
"""
import numpy as np
from PIL import Image

NTSC = [
    0x000000, 0x4a4a4a, 0x6f6f6f, 0x8e8e8e, 0xaaaaaa, 0xc0c0c0, 0xd6d6d6, 0xececec,
    0x484800, 0x69690f, 0x86861d, 0xa2a22a, 0xbbbb35, 0xd2d240, 0xe8e84a, 0xfcfc54,
    0x7c2c00, 0x904811, 0xa26221, 0xb47a30, 0xc3903d, 0xd2a44a, 0xdfb755, 0xecc860,
    0x901c00, 0xa33915, 0xb55328, 0xc66c3a, 0xd5824a, 0xe39759, 0xf0aa67, 0xfcbc74,
    0x940000, 0xa71a1a, 0xb83232, 0xc84848, 0xd65c5c, 0xe46f6f, 0xf08080, 0xfc9090,
    0x840064, 0x97197a, 0xa8308f, 0xb846a2, 0xc659b3, 0xd46cc3, 0xe07cd2, 0xec8ce0,
    0x500084, 0x68199a, 0x7d30ad, 0x9246c0, 0xa459d0, 0xb56ce0, 0xc57cee, 0xd48cfc,
    0x140090, 0x331aa3, 0x4e32b5, 0x6848c6, 0x7f5cd5, 0x956fe3, 0xa980f0, 0xbc90fc,
    0x000094, 0x181aa7, 0x2d32b8, 0x4248c8, 0x545cd6, 0x656fe4, 0x7580f0, 0x8490fc,
    0x001c88, 0x183b9d, 0x2d57b0, 0x4272c2, 0x548ad2, 0x65a0e1, 0x75b5ef, 0x84c8fc,
    0x003064, 0x185080, 0x2d6d98, 0x4288b0, 0x54a0c5, 0x65b7d9, 0x75cceb, 0x84e0fc,
    0x004030, 0x18624e, 0x2d8169, 0x429e82, 0x54b899, 0x65d1ae, 0x75e7c2, 0x84fcd4,
    0x004400, 0x1a661a, 0x328432, 0x48a048, 0x5cba5c, 0x6fd26f, 0x80e880, 0x90fc90,
    0x143c00, 0x355f18, 0x527e2d, 0x6e9c42, 0x87b754, 0x9ed065, 0xb4e775, 0xc8fc84,
    0x303800, 0x505916, 0x6d762b, 0x88923e, 0xa0ab4f, 0xb7c25f, 0xccd86e, 0xe0ec7c,
    0x482c00, 0x694d14, 0x866a26, 0xa28638, 0xbb9f47, 0xd2b656, 0xe8cc63, 0xfce070,
]
PAL = np.array([[(c >> 16) & 255, (c >> 8) & 255, c & 255] for c in NTSC], dtype=np.uint8)
PALETTE_HEX = ",".join(f"{c:06x}" for c in NTSC)   # für sprites.py --palette-hex


def rgb(reg):
    """Farbregister (0..255, Bit 0 egal) -> RGB-Tupel."""
    return tuple(int(v) for v in PAL[(reg & 0xFE) >> 1])


# NUSIZ: Kopien (Abstand in Pixeln vom Ursprung) und Breitenfaktor des Spielers
NUSIZ_COPIES = {0: [0], 1: [0, 16], 2: [0, 32], 3: [0, 16, 32], 4: [0, 64], 5: [0], 6: [0, 32, 64], 7: [0]}
NUSIZ_SCALE = {5: 2, 7: 4}


def render_lines(L, text_rows=None, sprites_only=False):
    """L: Liste von 192 Zeilen-Dicts mit den Registern (siehe build_rom.py). Rückgabe: 160x192 RGB-Array."""
    out = np.zeros((192, 160, 3), np.uint8)
    for y, r in enumerate(L):
        if r.get("text"):
            row = (text_rows or {}).get(y, [0] * 160)
            for x in range(160):
                out[y, x] = rgb(r["colupf"] if row[x] else r["colubk"])
            continue
        for x in range(160):
            if r.get("hmove", 0) and x < 8:
                continue
            blk = x // 4
            pf = (r["pf"] >> blk) & 1
            def player(px, grp, nus, ref):
                for off in NUSIZ_COPIES[nus & 7]:
                    sc = NUSIZ_SCALE.get(nus & 7, 1)
                    d = (x - px - off) % 160
                    if d < 8 * sc:
                        b = d // sc
                        bit = b if ref else 7 - b
                        if (grp >> bit) & 1:
                            return True
                return False
            def missile(mx, en, nus):
                if not en:
                    return False
                w = 1 << ((nus >> 4) & 3)
                offs = NUSIZ_COPIES[nus & 7] if (nus & 7) not in (5, 7) else [0]
                return any((x - mx - o) % 160 < w for o in offs)
            p0 = player(r["p0x"], r["grp0"], r["nusiz0"], r["refp0"]) or missile(r["m0x"], r["enam0"], r["nusiz0"])
            p1 = player(r["p1x"], r["grp1"], r["nusiz1"], r["refp1"]) or missile(r["m1x"], r["enam1"], r["nusiz1"])
            bw = 1 << ((r["ctrlpf"] >> 4) & 3)
            bl = r["enabl"] and (x - r["blx"]) % 160 < bw
            pfc = r["colupf"] if x < r.get("split", 160) else r.get("colupf_r", r["colupf"])
            if r["ctrlpf"] & 2:          # Score-Modus
                pfc = r["colup0"] if x < 80 else r["colup1"]
            if sprites_only:
                c = r["colup0"] if p0 else None
                out[y, x] = rgb(c) if c is not None else (255, 0, 255)
                continue
            if r["ctrlpf"] & 4:          # Playfield vor Spielern
                order = [(pf, pfc), (bl, pfc), (p0, r["colup0"]), (p1, r["colup1"])]
            else:
                order = [(p0, r["colup0"]), (p1, r["colup1"]), (pf, pfc), (bl, pfc)]
            c = r["colubk"]
            for hit, col in order:
                if hit:
                    c = col
                    break
            out[y, x] = rgb(c)
    return out


def to_display(arr, scale=3):
    """160 breite Pixel -> doppelt breit (wie im Demo-Viewport 320x192), dann ganzzahlig vergrößert."""
    im = Image.fromarray(arr)
    w, h = im.size
    return im.resize((w * 2 * scale, h * scale), Image.NEAREST)
