#!/usr/bin/env python3
"""TripoSR lokal auf dem Mac: freigestelltes Bild -> Mesh mit Eckpunktfarben (PLY) + Messwerte.

Aufruf (aus dem Projektordner, mit dem eigenen venv des Eintrags):
    E=styles/ki-3d-modell
    HF_HOME=$E/tsr/hf HF_HUB_OFFLINE=1 $E/tsr/venv/bin/python -I $E/scripts/tsr_run.py \
        --image $E/assets/raw/barrel.png --out $E/work/tsr/barrel [--device mps|cpu] [--mc 256] [--views 8]

Abweichungen vom Original-run.py (TripoSR, MIT):
  - torchmcubes (C++/CUDA-Erweiterung, baut nicht ohne Weiteres auf macOS) wird durch Marching Cubes aus
    scikit-image ersetzt (kleines Ersatzmodul, siehe _install_shims).
  - rembg wird nicht installiert: Die Bilder sind schon freigestellt (Alphakanal aus genimg.py).
    utils.py importiert rembg trotzdem beim Laden, deshalb ein leeres Ersatzmodul.
  - Gewichte mit fester Revision aus dem HF-Cache im Eintragsordner (HF_HOME), torch.load mit weights_only.
"""
import argparse, json, os, sys, time, types, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ENTRY = HERE.parent
TSR_SRC = ENTRY / "tsr" / "TripoSR"
REVISION = "5b521936b01fbe1890f6f9baed0254ab6351c04a"   # stabilityai/TripoSR, Lizenz MIT (Model Card)


def _install_shims():
    import numpy as np
    import torch
    from skimage import measure

    def marching_cubes(vol: "torch.Tensor", thresh: float):
        """Ersatz für torchmcubes.marching_cubes: gleiche Rückgabe (Ecken als x=letzte Achse zuerst, Dreiecke)."""
        v = vol.detach().cpu().numpy().astype(np.float32)
        # torchmcubes: innen = Werte > thresh; skimage erzeugt die Fläche bei level, Orientierung prüfen wir in Blender
        verts, faces, _n, _vals = measure.marching_cubes(v, level=thresh, allow_degenerate=False)
        verts = verts[:, ::-1].copy()          # skimage liefert (Achse0, Achse1, Achse2); torchmcubes (x=Achse2, y, z=Achse0)
        # Umlaufsinn umdrehen: sonst zeigen die Normalen nach innen (gemessen: Volumen des Fasses -0,42 statt +0,42)
        faces = faces[:, ::-1].copy()
        return torch.from_numpy(verts), torch.from_numpy(faces.astype(np.int64))

    mc = types.ModuleType("torchmcubes")
    mc.marching_cubes = marching_cubes
    sys.modules["torchmcubes"] = mc
    rb = types.ModuleType("rembg")      # nur damit tsr.utils importiert; remove_background wird nicht genutzt
    sys.modules["rembg"] = rb


def prepare(img_path: pathlib.Path, ratio: float):
    """Wie run.py: Vordergrund auf Anteil `ratio` eines Quadrats bringen, auf Grau 0,5 setzen."""
    import numpy as np
    from PIL import Image
    im = Image.open(img_path).convert("RGBA")
    a = np.array(im)
    # 1-Bit-ähnliche Kante: halbtransparente Säume (Freistellen) nicht als Vordergrund zählen
    ys, xs = np.where(a[..., 3] > 127)
    y1, y2, x1, x2 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    fg = a[y1:y2, x1:x2]
    size = max(fg.shape[0], fg.shape[1])
    new = int(round(size / ratio))
    canvas = np.zeros((new, new, 4), np.uint8)
    oy, ox = (new - fg.shape[0]) // 2, (new - fg.shape[1]) // 2
    canvas[oy:oy + fg.shape[0], ox:ox + fg.shape[1]] = fg
    f = canvas.astype(np.float32) / 255.0
    rgb = f[..., :3] * f[..., 3:4] + (1 - f[..., 3:4]) * 0.5
    crop = {"src_bbox": [int(x1), int(y1), int(x2), int(y2)], "square": new, "offset": [int(ox), int(oy)],
            "ratio": ratio}
    return Image.fromarray((rgb * 255).round().astype(np.uint8)), Image.fromarray(canvas), crop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="mps")
    ap.add_argument("--mc", type=int, default=256, help="Marching-Cubes-Auflösung")
    ap.add_argument("--threshold", type=float, default=25.0)
    ap.add_argument("--ratio", type=float, default=0.85)
    ap.add_argument("--views", type=int, default=8, help="NeRF-Ansichten zur Kontrolle (0 = keine)")
    ap.add_argument("--chunk", type=int, default=8192)
    a = ap.parse_args()

    _install_shims()
    sys.path.insert(0, str(TSR_SRC))
    import numpy as np
    import torch
    from huggingface_hub import hf_hub_download
    from omegaconf import OmegaConf
    from tsr.system import TSR

    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    dev = a.device
    if dev == "mps" and not torch.backends.mps.is_available():
        dev = "cpu"
    rec = {"image": a.image, "device": dev, "mc_resolution": a.mc, "threshold": a.threshold, "ratio": a.ratio,
           "torch": torch.__version__, "revision": REVISION}
    t0 = time.time()
    cfg_path = hf_hub_download("stabilityai/TripoSR", "config.yaml", revision=REVISION)
    w_path = hf_hub_download("stabilityai/TripoSR", "model.ckpt", revision=REVISION)
    cfg = OmegaConf.load(cfg_path); OmegaConf.resolve(cfg)
    model = TSR(cfg)
    model.load_state_dict(torch.load(w_path, map_location="cpu", weights_only=True))
    model.renderer.set_chunk_size(a.chunk)
    model.to(dev).eval()
    rec["t_load"] = round(time.time() - t0, 2)

    img, rgba, crop = prepare(pathlib.Path(a.image), a.ratio)
    img.save(out / "input.png"); rgba.save(out / "input_rgba.png")
    rec["crop"] = crop
    t1 = time.time()
    with torch.no_grad():
        codes = model([img], device=dev)
    if dev == "mps":
        torch.mps.synchronize()
    rec["t_model"] = round(time.time() - t1, 2)

    if a.views:
        t2 = time.time()
        views = model.render(codes, n_views=a.views, return_type="pil", height=256, width=256)[0]
        from PIL import Image
        sheet = Image.new("RGB", (256 * len(views), 256))
        for i, v in enumerate(views):
            sheet.paste(v, (256 * i, 0))
        sheet.save(out / "nerf_views.png")
        rec["t_render"] = round(time.time() - t2, 2)

    t3 = time.time()
    mesh = model.extract_mesh(codes, True, resolution=a.mc, threshold=a.threshold)[0]
    rec["t_mesh"] = round(time.time() - t3, 2)
    mesh.export(out / "mesh.ply")
    rec.update({"vertices": int(len(mesh.vertices)), "faces": int(len(mesh.faces)),
                "bounds": np.asarray(mesh.bounds).round(4).tolist(),
                "watertight": bool(mesh.is_watertight),
                "signed_volume": float(mesh.volume) if mesh.is_watertight else None,
                "components": int(len(mesh.split(only_watertight=False))) if len(mesh.faces) < 400000 else None,
                "t_total": round(time.time() - t0, 2)})
    (out / "tsr.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
