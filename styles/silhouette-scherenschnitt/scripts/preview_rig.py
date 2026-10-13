#!/usr/bin/env python3
"""Setzt die Puppe aus assets/puppet/ in Python zusammen (Prüfbild vor dem Godot-Lauf).

Schreibt assets/check/rig_rest.png: links die KI-Gesamtfigur aus dem Blatt (gleicher Maßstab), rechts die
zusammengesetzte Puppe in Ruhe und in zwei Schrittstellungen; die Gelenke als rote Punkte.

    .venv/bin/python styles/silhouette-scherenschnitt/scripts/preview_rig.py
"""
import json, math, pathlib
import numpy as np
from PIL import Image, ImageDraw

SD = pathlib.Path(__file__).resolve().parents[1]
P = SD / "assets" / "puppet"
RIG = json.loads((P / "rig.json").read_text())
Z = 3


def piece(name):
    return Image.open(P / RIG["pieces"][name]["file"]).convert("RGBA")


def place(canvas, name, at, angle_deg, color=(20, 14, 26)):
    """Teil so setzen, dass sein Drehpunkt auf 'at' (Bildpixel) liegt, gedreht um angle (Grad, im Uhrzeigersinn)."""
    pc = RIG["pieces"][name]
    im = piece(name)
    a = np.asarray(im)[..., 3]
    col = np.zeros(a.shape + (4,), np.uint8)
    col[..., :3] = color
    col[..., 3] = a
    im = Image.fromarray(col).resize((im.width * Z, im.height * Z), Image.LANCZOS)
    px, py = pc["pivot"][0] * Z, pc["pivot"][1] * Z
    # um den Drehpunkt drehen: Bild groß genug machen
    R = int(math.hypot(im.width, im.height)) + 4
    big = Image.new("RGBA", (2 * R, 2 * R), (0, 0, 0, 0))
    big.paste(im, (int(R - px), int(R - py)))
    big = big.rotate(-angle_deg, resample=Image.BICUBIC, center=(R, R))
    canvas.alpha_composite(big, (int(at[0] * Z - R), int(at[1] * Z - R)))


def rot(v, deg):
    r = math.radians(deg)
    return (v[0] * math.cos(r) - v[1] * math.sin(r), v[0] * math.sin(r) + v[1] * math.cos(r))


def pose(canvas, hip, th_n=0.0, th_f=0.0, foot_n=0.0, foot_f=0.0, lift_n=0.0, lift_f=0.0, body=0.0,
         head=0.0, arm_n=0.0, arm_f=0.0, scarf=(-56.0, -70.0), dots=True):
    J = RIG["joints"]
    hx, hy = hip
    def at(rel, extra=(0, 0)):
        v = rot(rel, body)
        return (hx + v[0] + extra[0], hy + v[1] + extra[1])
    # Reihenfolge: Schalenden, ferner Arm, fernes Bein, nahes Bein, Kopf, Rumpf, naher Arm
    for nm, ang in (("scarf_b", scarf[1]), ("scarf_a", scarf[0])):
        place(canvas, nm, at(J["scarf_root"]), body + ang)
    place(canvas, "arm_f", at(J["shoulder_f"]), body + arm_f)
    for side, th, ft, lift in (("f", th_f, foot_f, lift_f), ("n", th_n, foot_n, lift_n)):
        leg = "leg_" + side
        hp = (hx, hy - lift)
        place(canvas, leg, hp, th)
        ank = rot(RIG["pieces"][leg]["ankle_rel"], th)
        place(canvas, "foot_" + side, (hp[0] + ank[0], hp[1] + ank[1]), ft)
    place(canvas, "head", at(J["neck"]), body + head)
    place(canvas, "torso", (hx, hy), body)
    place(canvas, "arm_n", at(J["shoulder_n"]), body + arm_n)
    if dots:
        d = ImageDraw.Draw(canvas)
        for p in (hip, at(J["neck"]), at(J["shoulder_n"]), at(J["scarf_root"])):
            d.ellipse([p[0] * Z - 3, p[1] * Z - 3, p[0] * Z + 3, p[1] * Z + 3], fill=(255, 0, 0, 255))


def main():
    W, H = 760, 240
    canvas = Image.new("RGBA", (W * Z, H * Z), (236, 200, 160, 255))
    # KI-Gesamtfigur zum Vergleich
    src = Image.open(SD / "assets" / "raw" / "puppet.png").convert("L").crop((30, 100, 480, 750))
    s = RIG["scale"] * Z
    src = src.resize((int(src.width * s), int(src.height * s)), Image.LANCZOS)
    a = 255 - np.asarray(src)
    col = np.zeros(a.shape + (4,), np.uint8); col[..., :3] = (20, 14, 26); col[..., 3] = a
    canvas.alpha_composite(Image.fromarray(col), (10 * Z, int((H - 10) * Z - src.height)))
    ground = H - 10
    hip_h = RIG["hip_to_sole"]
    pose(canvas, (230, ground - hip_h))
    L = RIG["hip_to_ankle"]
    a = 18.0
    hy = ground - (RIG["hip_to_sole"] - L) - L * math.cos(math.radians(a))
    pose(canvas, (400, hy), th_n=-a, th_f=a, arm_n=-30, arm_f=10, body=3, scarf=(-30, -40))
    pose(canvas, (570, ground - hip_h), th_n=0, th_f=0, lift_f=7, head=-11, arm_n=-56, scarf=(-56, -70))
    d = ImageDraw.Draw(canvas)
    d.line([(0, ground * Z), (W * Z, ground * Z)], fill=(255, 255, 255, 255), width=1)
    canvas.convert("RGB").save(SD / "assets" / "check" / "rig_rest.png")
    print("ok", RIG["hip_to_sole"], RIG["hip_to_ankle"])


if __name__ == "__main__":
    main()
