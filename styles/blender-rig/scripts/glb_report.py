#!/usr/bin/env python3
"""Was steckt im exportierten Dachs? Liest den JSON-Teil einer .glb ohne Zusatzpakete.

    .venv/bin/python styles/blender-rig/scripts/glb_report.py [styles/blender-rig/demo/models/badger.glb]

Ausgabe: Knochen (Skin-Gelenke), Meshes mit Dreiecken und Einflüssen je Punkt, Animationen mit Länge,
Kanälen und Schlüsselbildern je Kanal (gesampelt = jedes Bild ein Schlüssel), Interpolation, und ob
glTF ein Schleifen-Flag kennt (nein: Godot importiert LOOP_NONE).
"""
import json
import pathlib
import struct
import sys

path = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                    pathlib.Path(__file__).resolve().parents[1] / "demo" / "models" / "badger.glb")
data = path.read_bytes()
magic, version, length = struct.unpack_from("<4sII", data, 0)
assert magic == b"glTF", "keine GLB-Datei"
clen, ctype = struct.unpack_from("<I4s", data, 12)
g = json.loads(data[20:20 + clen])
acc = g["accessors"]
print(f"{path.name}: glTF {g['asset'].get('version')} von {g['asset'].get('generator', '?')}, {length / 1024:.0f} KiB")

for s in g.get("skins", []):
    names = [g["nodes"][j]["name"] for j in s["joints"]]
    print(f"Skin: {len(names)} Gelenke: {', '.join(names)}")

for m in g["meshes"]:
    tris = 0
    infl = set()
    for p in m["primitives"]:
        tris += acc[p["indices"]]["count"] // 3
        infl.update(k for k in p["attributes"] if k.startswith(("JOINTS_", "WEIGHTS_")))
    print(f"Mesh {m['name']}: {tris} Dreiecke in {len(m['primitives'])} Teilen (je Material), "
          f"Einflüsse: {sorted(infl)} (4 je Satz)")

print(f"Animationen: {len(g.get('animations', []))}")
for a in g.get("animations", []):
    keys = {}
    paths = {}
    interp = set()
    tmax = 0.0
    for ch in a["channels"]:
        smp = a["samplers"][ch["sampler"]]
        inp = acc[smp["input"]]
        keys[inp["count"]] = keys.get(inp["count"], 0) + 1
        paths[ch["target"]["path"]] = paths.get(ch["target"]["path"], 0) + 1
        interp.add(smp.get("interpolation", "LINEAR"))
        tmax = max(tmax, inp.get("max", [0])[0])
    print(f"  {a['name']:5s}: {tmax:.2f} s, {len(a['channels'])} Kanäle ({', '.join(f'{v}× {k}' for k, v in paths.items())}),"
          f" Schlüssel je Kanal: {', '.join(f'{k} ({v} Kanäle)' for k, v in sorted(keys.items()))}, "
          f"Interpolation {', '.join(sorted(interp))}")
ext = set(g.get("extensionsUsed", []))
print(f"Erweiterungen: {sorted(ext) or 'keine'}; Schleifen-Flag in glTF: keines (Godot setzt LOOP_NONE)")
