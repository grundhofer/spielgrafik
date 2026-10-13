#!/usr/bin/env python3
"""Testbilder für prep.py, solange die Bildaufträge nicht erledigt sind (kein KI-Bild, nur zum Prüfen der Kette).

Aufruf aus dem Projektordner (Zielordner außerhalb von assets/raw/, sonst hält imagequeue.py die Aufträge für
erledigt und überspringt sie):
    .venv/bin/python styles/anime-visual-novel/tools/make_testinputs.py --out <Temp>/anime-visual-novel/raw_test
    .venv/bin/python styles/anime-visual-novel/tools/prep.py --raw <Temp>/anime-visual-novel/raw_test --test

Ahmt nach, was die Aufträge liefern und was dabei schiefgehen kann:
  sheet.keyed-src.png / sheet.png   assets/ref_pair.png mit gemalter „freudiger“ Mimik rechts; die rechte Figur
                                    um +3/-2 px verschoben und 1 % größer (zwei Figuren eines Blatts sind nie
                                    deckungsgleich); auf 1264x848 verkleinert (agy-Größe) und als JPEG gespeichert.
  faces.keyed-src.png / faces.png   Bearbeitung davon: links Augen zu + Mund offen, rechts überrascht; das ganze
                                    Bild 1 px versetzt neu abgetastet und erneut JPEG (agy malt das Bild neu).
  bg.png                            Kopie von styles/ligne-claire/assets/raw/bg.png (nur gelesen; agy-Größe 1264x848).
Freigestellt wird wie in genimg.py mit tools/sprites.py key (Toleranz 70, weich 50).
"""
import argparse, io, pathlib, shutil, subprocess, sys

from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parent.parent
ROOT = SD.parent.parent
EYES = [(335, 218), (454, 220)]       # Augenmitten der linken Figur in assets/ref_pair.png (1536x1024)
MOUTH = (395, 302)
DX = 768                              # Abstand der rechten Figur
STRIPE = (66, 64, 72)
FUR = (238, 228, 208)
LINE = (52, 36, 32)


def jpeg(im, q):
    b = io.BytesIO()
    im.convert("RGB").save(b, "JPEG", quality=q)
    return Image.open(io.BytesIO(b.getvalue())).convert("RGB")


def closed_eye(d, x, y, up):
    d.ellipse([x - 19, y - 19, x + 19, y + 19], fill=STRIPE)
    box = [x - 17, y - 10, x + 17, y + 10]
    if up:   # freudig: Bogen nach oben
        d.arc(box, 190, 350, fill=(232, 222, 205), width=4)
    else:    # Blinzeln: Bogen nach unten
        d.arc(box, 10, 170, fill=(232, 222, 205), width=4)


def open_mouth(d, x, y, w, h):
    d.ellipse([x - w, y - h, x + w, y + h], fill=(70, 28, 30), outline=LINE, width=3)
    d.ellipse([x - w * 0.55, y + h * 0.1, x + w * 0.55, y + h * 0.85], fill=(222, 120, 130))


def round_eye(d, x, y):
    d.ellipse([x - 18, y - 18, x + 18, y + 18], fill=(250, 250, 250), outline=LINE, width=3)
    d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(60, 36, 24))
    d.ellipse([x - 2, y - 9, x + 4, y - 3], fill=(255, 255, 255))


def key(src, dst):
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "sprites.py"), "key", str(src), str(dst),
                        "--color", "ff00ff", "--tol", "70", "--soft", "50"], capture_output=True, text=True)
    print(" ", (r.stdout or r.stderr).strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = pathlib.Path(a.out).resolve()
    if (SD / "assets" / "raw").resolve() in [out, *out.parents]:
        sys.exit("Testbilder nicht nach assets/raw/ schreiben (Ziele der Bildaufträge)")
    out.mkdir(parents=True, exist_ok=True)
    base = Image.open(SD / "assets" / "ref_pair.png").convert("RGB")
    # Blatt: rechts freudig, rechte Hälfte leicht versetzt und vergrößert
    sheet = base.copy()
    d = ImageDraw.Draw(sheet)
    for x, y in EYES:
        closed_eye(d, x + DX, y, up=True)
    open_mouth(d, MOUTH[0] + DX, MOUTH[1] + 4, 24, 16)
    right = sheet.crop((768, 0, 1536, 1024))
    s = 1.01
    rr = right.resize((round(768 * s), round(1024 * s)), Image.LANCZOS)
    canvas = Image.new("RGB", (768, 1024), (255, 0, 255))
    canvas.paste(rr, (3 - (rr.width - 768) // 2, -2 - (rr.height - 1024) // 2))
    sheet.paste(canvas, (768, 0))
    # Bearbeitung: links Augen zu + Mund offen, rechts überrascht
    faces = sheet.copy()
    d = ImageDraw.Draw(faces)
    for x, y in EYES:
        closed_eye(d, x, y, up=False)
    open_mouth(d, MOUTH[0], MOUTH[1] - 2, 15, 11)
    for x, y in EYES:
        X = round(768 + 3 - (rr.width - 768) // 2 + (x + DX - 768) * s)
        Y = round(-2 - (rr.height - 1024) // 2 + y * s)
        d.ellipse([X - 20, Y - 20, X + 20, Y + 20], fill=STRIPE)
        round_eye(d, X, Y)
    MX = round(768 + 3 - (rr.width - 768) // 2 + (MOUTH[0] + DX - 768) * s)
    MY = round(-2 - (rr.height - 1024) // 2 + (MOUTH[1] + 4) * s)
    d.ellipse([MX - 28, MY - 20, MX + 28, MY + 20], fill=FUR)
    d.ellipse([MX - 9, MY - 9, MX + 9, MY + 9], fill=(70, 28, 30), outline=LINE, width=3)
    faces = faces.transform(faces.size, Image.AFFINE, (1, 0, -1, 0, 1, -1), resample=Image.BICUBIC,
                            fillcolor=(255, 0, 255))
    for name, im, q in (("sheet", sheet, 90), ("faces", faces, 88)):
        small = jpeg(im.resize((1264, 848), Image.LANCZOS), q)
        src = out / f"{name}.keyed-src.png"
        small.save(src)
        key(src, out / f"{name}.png")
    shutil.copy2(ROOT / "styles" / "ligne-claire" / "assets" / "raw" / "bg.png", out / "bg.png")
    print(f"Testbilder in {out}")


if __name__ == "__main__":
    main()
