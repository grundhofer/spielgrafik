#!/usr/bin/env python3
"""Misst den laufenden Dachs in der Godot-Aufnahme (Prüfmodus: nur die Figur vor Magenta).

    .venv/bin/python styles/painterly-digital/scripts/measure_badger.py OUTDIR

Drei Läufe mit Movie Maker (30 fps, 6 s):
  --badger-only --only-near   nur nahes Bein      -> Bodenkontakt des nahen Fußes je Bild
  --badger-only --only-far    nur fernes Bein     -> Bodenkontakt des fernen Fußes je Bild
  --badger-only               ganze Figur         -> Kopf (oberstes Viertel) und Fußzeile je Bild
Prüfungen:
  (1) Standfuß: Solange ein Fuß in zwei aufeinanderfolgenden Bildern den Boden berührt, bleibt mindestens eine
      seiner Kanten (Ferse beim Aufsetzen, Zehe beim Abrollen) auf ±1 px an derselben Stelle. Wächst die
      Kontaktkante nach beiden Seiten bei fester Mitte (±1 px), ist das ein flach aufsetzender Fuß, kein Rutschen;
      das wird getrennt gezählt.
  (2) Fußzeile (unterste Pixelzeile der Figur) in allen Stehbildern gleich, beim Gehen höchstens ±1 px.
  (3) Kopf: kein Sprung zwischen zwei Bildern, der größer ist als der Vorschub des Körpers + 2 px.
Sohlenlinie (GROUND) und Stehbeginn (T_WALK + T_DEC) werden aus demo/main.gd gelesen. Temporäre Bilder liegen in
<TMPDIR>/painterly-digital/. Schreibt OUTDIR/feet.txt (alle Werte) und gibt eine Zusammenfassung aus.
"""
import pathlib, re, shutil, subprocess, sys, tempfile
import numpy as np
from PIL import Image

S = pathlib.Path(__file__).resolve().parent.parent
_GD = (S / "demo" / "main.gd").read_text()


def _const(name):
    return float(re.search(rf"const {name} := ([0-9.]+)", _GD).group(1))


GROUND = int(round(_const("GROUND")))                                  # Sohlenlinie aus main.gd
STOP_FRAME = int(round((_const("T_WALK") + _const("T_DEC")) * 30))     # ab hier steht er
# Temporäre Bilder nur in einem eigenen Unterordner (mehrere Agenten arbeiten gleichzeitig)
TMP = pathlib.Path(tempfile.gettempdir()) / "painterly-digital"


def run(extra):
    TMP.mkdir(parents=True, exist_ok=True)
    td = tempfile.mkdtemp(dir=TMP)
    subprocess.run(["godot", "--path", str(S / "demo"), "--position", "20000,20000", "--resolution", "1280x720",
                    "--write-movie", f"{td}/f.png", "--fixed-fps", "30", "--quit-after", "180", "--",
                    "--badger-only", *extra], capture_output=True, text=True)
    out = []
    for p in sorted(pathlib.Path(td).glob("f*.png")):
        a = np.asarray(Image.open(p).convert("RGB")).astype(int)
        mag = (a[..., 0] > 200) & (a[..., 1] < 60) & (a[..., 2] > 200)
        out.append(~mag)
        p.unlink()
    shutil.rmtree(td, ignore_errors=True)        # Movie Maker schreibt zusätzlich f.wav
    return out


def segs(row):
    xs = np.flatnonzero(row)
    if not len(xs):
        return []
    res, st, last = [], xs[0], xs[0]
    for x in xs[1:]:
        if x != last + 1:
            res.append((int(st), int(last))); st = x
        last = x
    res.append((int(st), int(last)))
    return res


def contacts(fig):
    # Bodenkontakt: deckende Pixel in den beiden untersten Zeilen über dem Boden
    return segs(fig[GROUND - 2:GROUND].any(0))


def main():
    out = pathlib.Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    near, far, full = run(["--only-near"]), run(["--only-far"]), run([])
    lines, worst, slips, flat = [], 0, [], []
    for name, frames in (("nah", near), ("fern", far)):
        prev = []
        for i, fig in enumerate(frames):
            c = [s for s in contacts(fig) if s[1] - s[0] >= 2]
            if prev and c:
                for a0, a1 in c:
                    for b0, b1 in prev:
                        if min(a1, b1) - max(a0, b0) >= 0:
                            move = min(abs(a0 - b0), abs(a1 - b1))
                            # Aufsetzen eines flachen Fußes: die Kontaktkante wächst nach beiden Seiten, die Mitte
                            # bleibt stehen. Rutschen = beide Kanten UND die Mitte wandern.
                            centre = abs((a0 + a1) - (b0 + b1)) / 2
                            if centre <= 1 and move > 1:
                                flat.append(f"{name} Bild {i}: {b0}-{b1} -> {a0}-{a1} (Mitte {centre:.1f} px)")
                                continue
                            worst = max(worst, move)
                            if move > 1:
                                slips.append(f"{name} Bild {i}: {b0}-{b1} -> {a0}-{a1} ({move} px)")
            lines.append(f"{name} {i:3d} {i / 30:5.2f} kontakt={c}")
            prev = c
    bottoms, heads, jumps = [], [], []
    for i, fig in enumerate(full):
        if fig[:, 0].any():                       # Figur noch am Bildrand angeschnitten: nicht werten
            continue
        ys, xs = np.nonzero(fig)
        top, bot = ys.min(), ys.max()
        hq = fig[top:top + (bot - top) // 4]
        hx = np.nonzero(hq)[1].mean()
        bottoms.append(bot); heads.append((top, hx)); first = first if "first" in dir() else i
        lines.append(f"figur {i:3d} {i / 30:5.2f} oben={top} unten={bot} kopf_x={hx:7.1f}")
    for i in range(1, len(heads)):
        dy = heads[i][0] - heads[i - 1][0]
        if abs(dy) > 2:
            jumps.append(f"Bild {i}: Kopf springt {dy} px senkrecht")
    skipped = len(full) - len(bottoms)
    stand = set(bottoms[STOP_FRAME + 8 - skipped:])
    walk_b = bottoms[:STOP_FRAME - skipped]
    summary = [f"Standfuß: max. Abweichung der festen Kante {worst} px ({len(slips)} Meldungen > 1 px)",
               f"Aufsetzen mit wachsender Kontaktkante, Mitte fest: {len(flat)}",
               f"Fußzeile beim Gehen: {min(walk_b)}..{max(walk_b)} (Boden {GROUND - 1}), im Stand: {sorted(stand)}",
               f"Kopfsprünge > 2 px: {len(jumps)}"]
    (out / "feet.txt").write_text("\n".join(summary + slips + flat + jumps + [""] + lines) + "\n")
    print("\n".join(summary))
    for s_ in (slips + flat + jumps)[:15]:
        print("  ", s_)


if __name__ == "__main__":
    main()
