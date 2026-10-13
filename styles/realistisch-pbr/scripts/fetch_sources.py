#!/usr/bin/env python3
"""Lädt die CC0-Quellen (Poly Haven, ambientCG) in einen Arbeitsordner außerhalb des Projekts.

    .venv/bin/python styles/realistisch-pbr/scripts/fetch_sources.py <arbeitsordner>

Die Downloads sind groß und werden nicht eingecheckt; build_textures.py macht daraus die
verkleinerten, gepackten Texturen in demo/textures/ und demo/sky/. Bereits vorhandene Dateien
werden übersprungen. Die Liste unten ist zugleich die Quellenangabe für style.json → licenses.
"""
import io
import json
import pathlib
import sys
import urllib.request
import zipfile

# Poly Haven: (Asset, Auflösung, Karten). Karten: Diffuse, nor_gl, arm (AO/Rauheit/Metall), Displacement
POLYHAVEN = [
    ("cobblestone_floor_03", "2k", ["Diffuse", "nor_gl", "arm", "Displacement"]),  # Kaipflaster
    ("stone_wall_04", "1k", ["Diffuse", "nor_gl", "arm"]),                           # Kaimauer
    ("castle_wall_slates", "1k", ["Diffuse", "nor_gl", "arm"]),                      # Häuschen
    ("rock_surface", "1k", ["Diffuse", "nor_gl", "arm"]),                            # Eckquader, Kantensteine
    ("roof_slates_03", "1k", ["Diffuse", "nor_gl", "arm"]),                          # Schieferdach
    ("weathered_planks", "1k", ["Diffuse", "nor_gl", "arm"]),                        # Fässer, Holz dunkel
    ("wood_planks_grey", "1k", ["Diffuse", "nor_gl", "arm"]),                        # Steg, Kisten
    ("white_planks_clean", "1k", ["Diffuse", "nor_gl", "arm"]),                      # Bootsrumpf, Läden
    ("painted_plaster_wall", "1k", ["Diffuse", "nor_gl", "arm"]),                    # Leuchtturm
    ("green_metal_rust", "1k", ["Diffuse", "nor_gl", "arm"]),                        # Poller, Laterne
    ("rust_coarse_01", "1k", ["Diffuse", "nor_gl", "arm"]),                          # Fassreifen
    ("mossy_rock", "1k", ["Diffuse", "nor_gl", "arm"]),                              # Fels an Land
    ("lichen_rock", "1k", ["Diffuse", "nor_gl", "arm"]),                             # Felsen im Wasser
    ("damp_beach_sand", "1k", ["Diffuse", "nor_gl", "arm"]),                         # Sand
    ("sparse_grass", "1k", ["Diffuse", "nor_gl", "arm"]),                            # Gras
    ("poly_wool_herringbone", "1k", ["Diffuse", "nor_gl", "arm"]),                   # Mütze, Weste
    ("rough_linen", "1k", ["Diffuse", "nor_gl", "arm"]),                             # Hemd
    ("fabric_leather_02", "1k", ["Diffuse", "nor_gl", "arm"]),                       # Tasche
]
# Himmel (HDRI): Abendhimmel ohne Boden ("pure sky")
POLYHAVEN_HDRI = [("belfast_sunset_puresky", "4k")]
# ambientCG: (Asset, Paket)
AMBIENTCG = [("Rope001", "1K-JPG"), ("Cardboard002", "1K-JPG")]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "spielgrafik-realistisch-pbr/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for asset, res, maps in POLYHAVEN:
        files = None
        for m in maps:
            dst = out / f"{asset}_{m}_{res}.jpg"
            if dst.exists():
                continue
            if files is None:
                files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
            url = files[m][res]["jpg"]["url"]
            dst.write_bytes(get(url))
            print("ok", dst.name, dst.stat().st_size)
    for asset, res in POLYHAVEN_HDRI:
        dst = out / f"{asset}_{res}.hdr"
        if not dst.exists():
            files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
            dst.write_bytes(get(files["hdri"][res]["hdr"]["url"]))
            print("ok", dst.name, dst.stat().st_size)
    for asset, pack in AMBIENTCG:
        if list(out.glob(f"{asset}_{pack}_*")):
            continue
        data = get(f"https://ambientcg.com/get?file={asset}_{pack}.zip")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for n in z.namelist():
                if n.lower().endswith((".jpg", ".png")):
                    (out / f"{asset}_{pack}_{pathlib.Path(n).name}").write_bytes(z.read(n))
                    print("ok", n)


if __name__ == "__main__":
    main()
