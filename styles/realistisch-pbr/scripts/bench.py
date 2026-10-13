#!/usr/bin/env python3
"""Leistung messen: Zeit je Bild mit einzelnen Effekten aus (Forward+) und in den Renderern Mobile
und Compatibility, auf diesem Rechner (feste Endeinstellung, Zeit ab 4,8 s).

    .venv/bin/python styles/realistisch-pbr/scripts/bench.py [--frames 300] [--json assets/bench.json]

Die Demo misst selbst (main.gd --bench=N): Wanduhrzeit je Bild (Median über N Bilder nach 90 Bildern
Anlauf) mit --fixed-fps (keine Echtzeit-Wartezeit) und --disable-vsync. GPU-Zeitstempel liefert
Godot unter Metal nicht (viewport_get_measured_render_time_gpu und --gpu-profile ergeben 0); die
Bildzeit ist hier GPU-begrenzt (CPU-Zeit des Renderings um 0,2 ms). Gemessen wird in 1920×1080, weil
bei 1280×720 die Vollversion knapp an der 120-Hz-Grenze des Bildschirms (8,33 ms) liegt.
Jede Einstellung läuft --runs Mal (Standard 5), reihum verschachtelt (Lauf 1 aller Fälle, dann Lauf 2 …),
damit Schwankungen des Rechners (andere Prozesse, Wärme) alle Fälle gleich treffen. Angegeben werden der
Median der Läufe und die Spanne (kleinster bis größter Lauf). Die Kosten eines Effekts sind die
Differenz „alles an“ minus „ohne Effekt“ je Lauf (gepaart, gleicher Durchgang); Median und Spanne dieser
Differenzen. Ist die Differenz nicht in allen Läufen positiv oder kleiner als die halbe Spanne, gilt sie
als „unter der Messgenauigkeit“.
"""
import argparse
import json
import pathlib
import statistics
import subprocess

ENTRY = pathlib.Path(__file__).resolve().parent.parent
DEMO = ENTRY / "demo"
CAM = "--cam=-0.95,1.2,5.0,-0.1,1.04,-0.4,52"
ALL_OFF = ["--no-sdfgi", "--no-ssr", "--no-ssao", "--no-ssil", "--no-volfog", "--no-glow", "--no-dof",
           "--no-pom", "--no-fur"]
R = "1920x1080"
CASES = [
    ("Forward+ alles an", "", [], R),
    ("ohne SDFGI", "", ["--no-sdfgi"], R),
    ("ohne SSR", "", ["--no-ssr"], R),
    ("ohne SSAO", "", ["--no-ssao"], R),
    ("ohne SSIL", "", ["--no-ssil"], R),
    ("ohne volumetrischen Nebel (samt Seenebel)", "", ["--no-volfog"], R),
    ("ohne Seenebel (FogVolume)", "", ["--no-mist"], R),
    ("ohne Dunst (FogVolumes am Kai)", "", ["--no-haze"], R),
    ("ohne Tiefenschärfe", "", ["--no-dof"], R),
    ("ohne Glühen", "", ["--no-glow"], R),
    ("ohne Parallaxe (Pflaster)", "", ["--no-pom"], R),
    ("ohne Fell", "", ["--no-fur"], R),
    ("ohne TAA", "", ["--no-taa"], R),
    ("Forward+ alle Effekte aus", "", ALL_OFF, R),
    ("Forward+ alle Effekte aus, ohne Texturen", "", ALL_OFF + ["--flat"], R),
    ("Forward+ alles an, 1280×720", "", [], "1280x720"),
    ("Forward+ alles an, 2560×1440", "", [], "2560x1440"),
    ("Mobile", "mobile", [], R),
    ("Compatibility (OpenGL)", "gl_compatibility", [], R),
    # Unter etwa 8,4 ms greift die 120-Hz-Grenze des Bildschirms trotz --disable-vsync; die leichten
    # Fälle deshalb zusätzlich in 2560×1440
    ("2560×1440: ohne SDFGI", "", ["--no-sdfgi"], "2560x1440"),
    ("2560×1440: alle Effekte aus", "", ALL_OFF, "2560x1440"),
    ("2560×1440: Mobile", "mobile", [], "2560x1440"),
    ("2560×1440: Compatibility", "gl_compatibility", [], "2560x1440"),
]


def run(renderer, extra, res, frames):
    cmd = ["godot", "--path", str(DEMO), "--disable-vsync", "--fixed-fps", "30", "--position", "20000,20000",
           "--resolution", res]
    if renderer:
        cmd += ["--rendering-method", renderer]
    cmd += ["--", CAM, "--t0=4.8", "--no-ui", f"--bench={frames}"] + extra
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    for line in (r.stdout + r.stderr).splitlines():
        if line.startswith("BENCH "):
            return json.loads(line[6:])
    print((r.stdout + r.stderr)[-1500:])
    return None


COSTS = [("SDFGI", "ohne SDFGI"), ("volumetrischer Nebel (samt Seenebel und Dunst)", "ohne volumetrischen Nebel (samt Seenebel)"),
         ("Seenebel (FogVolume)", "ohne Seenebel (FogVolume)"), ("Dunst an Laterne/Fenster", "ohne Dunst (FogVolumes am Kai)"),
         ("TAA", "ohne TAA"), ("SSIL", "ohne SSIL"), ("Tiefenschärfe", "ohne Tiefenschärfe"), ("SSR", "ohne SSR"),
         ("Parallaxe", "ohne Parallaxe (Pflaster)"), ("Fell", "ohne Fell"), ("SSAO", "ohne SSAO"), ("Glühen", "ohne Glühen")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=300)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--json", default=str(ENTRY / "assets" / "bench.json"))
    a = ap.parse_args()
    runs = {name: [] for name, *_ in CASES}
    info = {}
    for r in range(a.runs):
        for name, renderer, extra, res in CASES:
            m = run(renderer, extra, res, a.frames)
            if m is None:
                print(f"Lauf {r + 1} {name}: keine Messung")
                runs[name].append(None)
                continue
            runs[name].append(m["frame_ms_median"])
            info[name] = {"renderer": m["renderer"], "adapter": m["adapter"], "resolution": res,
                          "cpu_ms_median": m["cpu_ms_median"]}
            print(f"Lauf {r + 1} {name:48s} {m['frame_ms_median']:6.2f} ms", flush=True)
    out = {"runs": a.runs, "frames": a.frames, "cases": [], "costs": []}
    for name, *_ in CASES:
        v = [x for x in runs[name] if x is not None]
        if not v:
            continue
        med = statistics.median(v)
        out["cases"].append({"case": name, **info[name], "frame_ms_runs": [round(x, 2) for x in runs[name] if x],
                             "frame_ms_median": round(med, 2), "frame_ms_min": round(min(v), 2),
                             "frame_ms_max": round(max(v), 2), "fps_median": round(1000 / med, 1)})
        print(f"{name:48s} Median {med:6.2f} ms ({1000 / med:5.0f} fps), Spanne {min(v):6.2f}–{max(v):6.2f} ms")
    full = runs["Forward+ alles an"]
    for label, case in COSTS:
        d = [f - x for f, x in zip(full, runs.get(case, [])) if f is not None and x is not None]
        if not d:
            continue
        med = statistics.median(d)
        lo, hi = min(d), max(d)
        below = lo <= 0.0 or med < (hi - lo) / 2.0
        out["costs"].append({"effect": label, "ms_median": round(med, 2), "ms_min": round(lo, 2), "ms_max": round(hi, 2),
                             "below_precision": below})
        print(f"Kosten {label:44s} {med:5.2f} ms (Spanne {lo:5.2f}–{hi:5.2f}){'  unter der Messgenauigkeit' if below else ''}")
    pathlib.Path(a.json).write_text(json.dumps(out, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
