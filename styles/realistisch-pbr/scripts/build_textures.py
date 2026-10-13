#!/usr/bin/env python3
"""Baut aus den CC0-Downloads (fetch_sources.py) die Texturen der Demo.

    .venv/bin/python styles/realistisch-pbr/scripts/build_textures.py <arbeitsordner>

Je Material entstehen in demo/textures/:
  <name>_a.jpg    Grundfarbe (sRGB). "color": Farben der Vorlage; "detail": Graustufen, linear auf
                  Mittelwert 0,5 gebracht; der Shader multipliziert mit 2 × Materialfarbe aus dem glTF.
  <name>_n.jpg    Normalenkarte (OpenGL, +Y), unverändert übernommen, wenn nichts gedreht wird
  <name>_orm.jpg  R = Umgebungsverdeckung, G = Rauheit, B = Metall (Poly Haven "arm" ist genau das)
  <name>_h.jpg    Höhe (nur Pflaster, für Parallax Occlusion Mapping)
dazu passende .import-Dateien (VRAM-komprimiert mit Mipmaps; Normalen als Normalenkarte).

Außerdem demo/sky/: sky_full.hdr (ganzes Panorama 1024×512 für Umgebungslicht und Spiegelungen)
und sky_band.hdr (scharfer Ausschnitt um den Horizont aus dem 4k-HDRI für den sichtbaren Himmel).
Schreibt assets/texture_table.json (Quelle, Maße, Modus) für die Dokumentation.
"""
import json
import pathlib
import shutil
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rgbe_io import read_hdr, write_hdr  # noqa: E402

ENTRY = pathlib.Path(__file__).resolve().parent.parent
TEX = ENTRY / "demo" / "textures"
SKY = ENTRY / "demo" / "sky"

# name: (Quelle, Präfix der Dateien, Auflösung im Download, Zielgröße, Modus, Drehung, physische Kachel in m)
PH = "polyhaven"
SUN_AZ_DEG = -20.0        # Sonne 20° links der Blickrichtung
BAND_LO, BAND_HI = -8.0, 40.0
BAND_HALF = 80.0
MATS = {
    "cobble":   (PH, "cobblestone_floor_03", "2k", 2048, "color", 0, 2.0),
    "quaywall": (PH, "stone_wall_04", "1k", 1024, "color", 0, 1.7),
    "slatewall": (PH, "castle_wall_slates", "1k", 1024, "color", 0, 2.5),
    "granite":  (PH, "rock_surface", "1k", 1024, "color", 0, 2.0),
    "roof":     (PH, "roof_slates_03", "1k", 1024, "color", 0, 3.0),
    "planks":   (PH, "weathered_planks", "1k", 1024, "color", 0, 2.0),
    "greywood": (PH, "wood_planks_grey", "1k", 1024, "color", 0, 1.5),
    "paintwood": (PH, "white_planks_clean", "1k", 1024, "detail", 0, 1.8),
    "plaster":  (PH, "painted_plaster_wall", "1k", 1024, "detail", 0, 2.0),
    "ironpaint": (PH, "green_metal_rust", "1k", 1024, "color", 0, 1.0),
    "rust":     (PH, "rust_coarse_01", "1k", 512, "color", 0, 2.2),
    "rock":     (PH, "mossy_rock", "1k", 1024, "color", 0, 3.0),
    "searock":  (PH, "lichen_rock", "1k", 1024, "color", 0, 2.0),
    "sand":     (PH, "damp_beach_sand", "1k", 1024, "color", 0, 2.0),
    "grass":    (PH, "sparse_grass", "1k", 1024, "color", 0, 2.0),
    "tweed":    (PH, "poly_wool_herringbone", "1k", 512, "detail", 0, 0.27),
    "linen":    (PH, "rough_linen", "1k", 512, "detail", 0, 0.27),
    "leather":  (PH, "fabric_leather_02", "1k", 512, "detail", 0, 0.5),
    "rope":     ("ambientcg", "Rope001", "1K-JPG", 512, "detail", 0, 0.0),
    "cardboard": ("ambientcg", "Cardboard002", "1K-JPG", 512, "detail", 0, 0.0),
}

IMPORT_TMPL = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://{res}"

[params]

compress/mode=2
compress/high_quality={hq}
compress/lossy_quality=0.7
compress/hdr_compression=1
compress/normal_map={nm}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/size_limit=0
detect_3d/compress_to=0
"""

HDR_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://{res}"

[params]

compress/mode=0
compress/high_quality=false
compress/hdr_compression=1
compress/normal_map=0
mipmaps/generate={mip}
mipmaps/limit=-1
process/fix_alpha_border=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def srgb_to_lin(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(x):
    x = np.clip(x, 0, 1)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def write_import(path, normal=False, hq=False):
    res = path.relative_to(ENTRY / "demo").as_posix()
    path.with_name(path.name + ".import").write_text(
        IMPORT_TMPL.format(res=res, nm=1 if normal else 0, hq="true" if hq else "false"))


def src_files(src, kind, prefix, res):
    if kind == PH:
        return {"a": src / f"{prefix}_Diffuse_{res}.jpg", "n": src / f"{prefix}_nor_gl_{res}.jpg",
                "arm": src / f"{prefix}_arm_{res}.jpg", "h": src / f"{prefix}_Displacement_{res}.jpg"}
    base = src / f"{prefix}_{res}_{prefix}_{res}"
    return {"a": pathlib.Path(f"{base}_Color.jpg"), "n": pathlib.Path(f"{base}_NormalGL.jpg"),
            "rough": pathlib.Path(f"{base}_Roughness.jpg"), "metal": pathlib.Path(f"{base}_Metalness.jpg"),
            "h": pathlib.Path(f"{base}_Displacement.jpg")}


def fit(im, size, rot):
    """Dreht und bringt auf size×size (leicht nicht-quadratische Stoffvorlagen wie 1024×1040 werden
    gestaucht; VRAM-Kompression braucht Kantenlängen in Vielfachen von 4). Seitenverhältnis 2:1
    (Seil) bleibt erhalten."""
    if rot:
        im = im.rotate(rot, expand=True)
    if abs(im.width - 2 * im.height) <= 2:
        target = (size, size // 2)
    else:
        target = (size, size)
    if im.size != target:
        im = im.resize(target, Image.LANCZOS)
    return im


def main():
    src = pathlib.Path(sys.argv[1])
    TEX.mkdir(parents=True, exist_ok=True)
    SKY.mkdir(parents=True, exist_ok=True)
    table = {}
    for name, (kind, prefix, res, size, mode, rot, tile_m) in MATS.items():
        f = src_files(src, kind, prefix, res)
        a = fit(Image.open(f["a"]).convert("RGB"), size, rot)
        info = {"source": kind, "asset": prefix, "download": res, "size": list(a.size), "mode": mode,
                "tile_m": tile_m}
        if mode == "detail":
            lin = srgb_to_lin(np.asarray(a, dtype=np.float32) / 255.0)
            lum = lin @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
            info["mean_lin"] = round(float(lum.mean()), 4)
            lum = np.clip(lum * (0.5 / lum.mean()), 0, 1)
            a = Image.fromarray((lin_to_srgb(lum) * 255 + 0.5).astype(np.uint8), "L").convert("RGB")
        else:
            lin = srgb_to_lin(np.asarray(a, dtype=np.float32) / 255.0)
            info["mean_rgb_lin"] = [round(float(v), 4) for v in lin.reshape(-1, 3).mean(0)]
        out = TEX / f"{name}_a.jpg"
        a.save(out, quality=90)
        write_import(out)
        # Normalenkarte: Original übernehmen, wenn Größe stimmt und nichts gedreht wird
        n_im = Image.open(f["n"])
        out = TEX / f"{name}_n.jpg"
        if rot == 0 and n_im.size == fit(n_im, size, 0).size and n_im.size[0] == size:
            shutil.copyfile(f["n"], out)
        else:
            n_im = fit(n_im.convert("RGB"), size, 0)
            if rot:
                # Drehen dreht auch die Richtungen in der Karte: (x, y) -> (-y, x) bei +90°
                arr = np.asarray(n_im.rotate(rot, expand=True), dtype=np.float32) / 127.5 - 1
                k = (rot // 90) % 4
                for _ in range(k):
                    arr = np.stack([-arr[..., 1], arr[..., 0], arr[..., 2]], -1)
                n_im = Image.fromarray(((arr + 1) * 127.5 + 0.5).clip(0, 255).astype(np.uint8))
            n_im.save(out, quality=92)
        write_import(out, normal=True)
        # ORM
        out = TEX / f"{name}_orm.jpg"
        if kind == PH:
            o = Image.open(f["arm"])
            if rot == 0 and o.size[0] == size and o.size == fit(o, size, 0).size:
                shutil.copyfile(f["arm"], out)
            else:
                fit(o.convert("RGB"), size, rot).save(out, quality=92)
        else:
            r = fit(Image.open(f["rough"]).convert("L"), size, rot)
            m = fit(Image.open(f["metal"]).convert("L"), size, rot) if f["metal"].exists() \
                else Image.new("L", r.size, 0)
            ao = Image.new("L", r.size, 255)
            Image.merge("RGB", (ao, r, m)).save(out, quality=92)
        write_import(out)
        if name == "cobble":
            out = TEX / f"{name}_h.jpg"
            shutil.copyfile(f["h"], out)
            write_import(out)
        table[name] = info
        print(name, info)

    # Himmel
    hdr = read_hdr(src / "belfast_sunset_puresky_4k.hdr")
    h, w, _ = hdr.shape
    lum = hdr @ np.array([0.2126, 0.7152, 0.0722])
    y, x = np.unravel_index(np.argmax(lum), lum.shape)
    sun_u = (x + 0.5) / w
    # Drehung: die Sonne soll SUN_AZ_DEG rechts von der Blickrichtung -Z stehen (negativ = links).
    # Der Sky-Shader rechnet u = fract(atan(d.x, -d.z) / TAU + U_OFFSET).
    u_offset = (sun_u - SUN_AZ_DEG / 360.0) % 1.0
    # ganzes Panorama auf 1024×512 (Mittelwert über 4×4 Blöcke) für Umgebungslicht und Spiegelungen
    full = hdr.reshape(512, h // 512, 1024, w // 1024, 3).mean(axis=(1, 3))
    write_hdr(SKY / "sky_full.hdr", full)
    (SKY / "sky_full.hdr.import").write_text(HDR_IMPORT.format(res="sky/sky_full.hdr", mip="false"))
    # scharfes Band um den Horizont für den sichtbaren Himmel: BAND_LO..BAND_HI Grad Höhe,
    # BAND_HALF Grad links und rechts der Blickrichtung -Z
    y0 = int(round((90 - BAND_HI) / 180 * h))
    y1 = int(round((90 - BAND_LO) / 180 * h))
    xc = u_offset * w
    x0 = int(round(xc - BAND_HALF / 360 * w))
    x1 = int(round(xc + BAND_HALF / 360 * w))
    cols = np.arange(x0, x1) % w
    band = hdr[y0:y1][:, cols]
    write_hdr(SKY / "sky_band.hdr", band)
    (SKY / "sky_band.hdr.import").write_text(HDR_IMPORT.format(res="sky/sky_band.hdr", mip="true"))
    inc = (f"// erzeugt von scripts/build_textures.py, nicht von Hand ändern\n"
           f"const float SKY_U_OFFSET = {u_offset:.6f};\n"
           f"const vec2 BAND_U = vec2({x0 / w:.6f}, {x1 / w:.6f});  // u-Bereich des Bandes (kann über 1 hinausgehen)\n"
           f"const vec2 BAND_V = vec2({y0 / h:.6f}, {y1 / h:.6f});  // v-Bereich (0 = Zenit)\n"
           f"const vec3 SUN_DIR = vec3({np.sin(np.radians(SUN_AZ_DEG)) * np.cos(np.radians(90 - (y + 0.5) / h * 180)):.5f}, "
           f"{np.sin(np.radians(90 - (y + 0.5) / h * 180)):.5f}, "
           f"{-np.cos(np.radians(SUN_AZ_DEG)) * np.cos(np.radians(90 - (y + 0.5) / h * 180)):.5f});  // zur Sonne\n")
    (SKY / "sky_params.gdshaderinc").write_text(inc)
    table["_sky"] = {"asset": "belfast_sunset_puresky", "download": "4k", "full": [1024, 512],
                     "band": [int(x1 - x0), int(y1 - y0)], "band_deg": [BAND_LO, BAND_HI], "band_half_deg": BAND_HALF,
                     "sun_u": round(float(sun_u), 4), "sun_elev_deg": round(float(90 - (y + 0.5) / h * 180), 2),
                     "sun_az_deg": SUN_AZ_DEG, "u_offset": round(float(u_offset), 5),
                     "max_lum": round(float(lum.max()), 2), "mean_upper_lum": round(float(lum[: h // 2].mean()), 4)}
    print("_sky", table["_sky"])
    print(inc)
    (ENTRY / "assets" / "texture_table.json").write_text(json.dumps(table, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
