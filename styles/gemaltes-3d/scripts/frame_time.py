#!/usr/bin/env python3
"""Bildzeit grob messen, ohne sichtbares Fenster (macOS drosselt verdeckte Fenster, --bench geht dann nicht).

    .venv/bin/python styles/gemaltes-3d/scripts/frame_time.py

Nimmt mit --write-movie als AVI (schnelle MJPEG-Kodierung) 30 und 330 Bilder auf und teilt die
Differenz der Laufzeiten durch 300: Zeit je Bild einschließlich Rücklesen und Kodieren, aber ohne Start
und Shader-Übersetzung. Verglichen werden Varianten mit fester Kamera (Endeinstellung); die Differenz zu
--raw (Steuerkamera und Durchgänge abgeschaltet) ist der Preis der Nachbearbeitung.
"""
import pathlib, subprocess, tempfile, time

DEMO = pathlib.Path(__file__).resolve().parent.parent / "demo"


def run(n, args):
    with tempfile.TemporaryDirectory() as td:
        t0 = time.time()
        subprocess.run(["godot", "--path", str(DEMO), "--position", "20000,20000", "--resolution", "1280x720",
                        "--write-movie", str(pathlib.Path(td) / "f.avi"), "--fixed-fps", "30",
                        "--quit-after", str(n), "--", "--static-cam"] + args,
                       capture_output=True, text=True, timeout=900)
        return time.time() - t0


for label, args in [("ungemalt (--raw)", ["--raw"]), ("gemalt", []), ("gemalt ohne Kuwahara", ["--no-kuwahara"]),
                    ("gemalt ohne Striche", ["--no-lic"])]:
    ms = (run(330, args) - run(30, args)) / 300 * 1000
    print(f"{label:24s} {ms:5.1f} ms je Bild")
