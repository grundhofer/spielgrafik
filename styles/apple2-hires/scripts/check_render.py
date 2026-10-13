"""Renderer- und Dauerlaufprüfung der Demo und Vergleichsbild der drei Farbmodelle.

    .venv/bin/python styles/apple2-hires/scripts/check_render.py <tmpdir>

1. Forward+, Mobile und Compatibility je 180 Bilder rendern, ausgewählte Bilder pixelweise vergleichen.
2. Dauerlauf ab t = 30 s (60 Bilder): media/probe_t30.png (×3).
3. Dasselbe Bild (t = 5,4 s) mit --model=fringe, crisp, ideal: assets/model_compare.png (Ausschnitt ×3).
4. Textzeilen wie in der Demo (Farbmodell) und mit --text=mono (einfarbig, bewusste Abweichung):
   assets/text_compare.png (unterer Bildteil ×3).
Beschriftungen mit dem eigenen Zeichensatz font57 (enthält Ä, Ö, Ü), einbittig ×2.
Ergebnis: media/check_render.json
"""
import json, pathlib, subprocess, sys
import numpy as np
from PIL import Image

ENTRY = pathlib.Path(__file__).resolve().parent.parent
DEMO = ENTRY / "demo"
sys.path.insert(0, str(ENTRY / "scripts"))
from font57 import glyph_bytes  # noqa: E402


def label(text, width, scale=2, pad=3):
    """Beschriftung im Zeichensatz font57 (weiß auf Dunkelgrau), Breite in Pixeln."""
    h = 8 * scale + 2 * pad
    out = np.full((h, width, 3), 40, np.uint8)
    for ci, ch in enumerate(text):
        for r, v in enumerate(glyph_bytes(ch)):
            for k in range(7):
                if (v >> k) & 1:
                    x, y = pad + (7 * ci + k) * scale, pad + r * scale
                    if x + scale <= width:
                        out[y:y + scale, x:x + scale] = 255
    return Image.fromarray(out)


def run(out, n, *extra, user=()):
    out.mkdir(parents=True, exist_ok=True)
    for p in out.glob("f*.png"):
        p.unlink()
    cmd = ["godot", "--path", str(DEMO), "--position", "20000,20000", *extra, "--write-movie",
           str(out / "f.png"), "--fixed-fps", "30", "--quit-after", str(n)]
    if user:
        cmd += ["--", *user]
    r = subprocess.run(cmd, capture_output=True, text=True)
    errs = [l for l in (r.stdout + r.stderr).splitlines() if "ERROR" in l]
    return sorted(out.glob("f*.png")), errs


def main():
    tmp = pathlib.Path(sys.argv[1])
    subprocess.run(["godot", "--headless", "--path", str(DEMO), "--import"], capture_output=True)
    res = {}
    base, e0 = run(tmp / "fwd", 180)
    picks = [0, 20, 50, 80, 120, 162]
    for name, flag in (("mobile", "mobile"), ("gl_compatibility", "gl_compatibility")):
        fr, errs = run(tmp / name, 180, "--rendering-method", flag)
        diffs = []
        for i in picks:
            a = np.asarray(Image.open(base[i]).convert("RGB"), int)
            b = np.asarray(Image.open(fr[i]).convert("RGB"), int)
            diffs.append(int((np.abs(a - b).sum(2) > 0).sum()))
        res[name] = {"frames": len(fr), "changed_pixels_at": dict(zip(map(str, picks), diffs)), "errors": errs[:3]}
    t30, e30 = run(tmp / "t30", 60, user=("--t0=30",))
    im = Image.open(t30[-1]).convert("RGB")
    im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(ENTRY / "media" / "probe_t30.png")
    res["t30"] = {"frames": len(t30), "errors": e30[:3]}
    crops = []
    for m in ("fringe", "crisp", "ideal"):
        fr, errs = run(tmp / f"m_{m}", 2, user=("--t0=5.4", f"--model={m}"))
        im = Image.open(fr[-1]).convert("RGB").crop((0, 80, 140, 192))
        crops.append((m, im.resize((im.width * 3, im.height * 3), Image.NEAREST)))
    w, h = crops[0][1].size
    names = {"fringe": "FRINGE: ALLE SÄUME", "crisp": "CRISP: DEMO, HELLE SÄUME", "ideal": "IDEAL: OHNE SÄUME"}
    lh = label("X", w).height
    sheet = Image.new("RGB", (w * 3 + 16, h + lh), (40, 40, 40))
    for k, (m, im) in enumerate(crops):
        sheet.paste(label(names[m], w), (k * (w + 8), 0))
        sheet.paste(im, (k * (w + 8), lh))
    sheet.save(ENTRY / "assets" / "model_compare.png")
    # 4. Textzeilen: Farbmodell der Demo gegen einfarbig (Prüfschalter --text=mono)
    parts = []
    for name, user in (("DEMO: FARBMODELL AUCH IM TEXT, WIE AM FARBFERNSEHER", ("--t0=5.4",)),
                       ("ABWEICHUNG: TEXTZEILEN EINFARBIG", ("--t0=5.4", "--text=mono"))):
        fr, errs = run(tmp / f"txt_{len(parts)}", 2, user=user)
        im = Image.open(fr[-1]).convert("RGB").crop((0, 136, 280, 192))
        im = im.resize((im.width * 3, im.height * 3), Image.NEAREST)
        parts += [label(name, im.width), im]
        res[f"text_{'mono' if '--text=mono' in user else 'demo'}_errors"] = errs[:3]
    sheet = Image.new("RGB", (parts[0].width, sum(p.height for p in parts)), (40, 40, 40))
    y = 0
    for p in parts:
        sheet.paste(p, (0, y))
        y += p.height
    sheet.save(ENTRY / "assets" / "text_compare.png")
    res["forward_errors"] = e0[:3]
    (ENTRY / "media" / "check_render.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
