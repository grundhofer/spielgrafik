#!/usr/bin/env python3
"""Voxelisiert den gemeinsamen Hafen (shared/3d/harbor.glb) zu demo/models/harbor_voxel.glb.

    .venv/bin/python styles/voxel/scripts/voxelize_harbor.py

- Gitter 0,1 m (10 Voxel je Meter), achsenparallel in Weltkoordinaten; ferne Inseln 1,0 m.
- Kai und Gelände als Höhenfeld (oberste Fläche je Spalte, darunter aufgefüllt), alle anderen Objekte als
  Körper: Mitte der Zelle innen nach Parität entlang aller drei Achsen (Mehrheit), dünne Teile (Geländer,
  Mast, Laternenarm) als Hülle ergänzt. Material je Zelle nach Mehrheit der Oberflächenpunkte.
- Je Zelle eine flache Farbe (Palette + Abwandlung je Voxel), je Flächenecke Voxel-AO (0..3) im Alphakanal
  der Vertexfarbe. Verdeckte Flächen und Flächen nach -Z (nie zur Kamera) entfallen, ebenso Flächen unter
  Wasser (unter y = -1,25).
- Knoten, Namen, Eltern, Empties und Materialnamen bleiben wie im Original; jedes Objekt behält seine
  Transformation, die Voxel stehen in seinem lokalen Raum. Das Meer (Sea) bleibt unverändert, die Demo
  ersetzt es durch Voxelwasser (MultiMesh) und liest dafür demo/textures/water_mask.png.
"""
import json, pathlib, sys, time
import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from glb import read_glb, write_glb, world_matrices
from voxcore import voxelize_solid, build_faces, faces_to_arrays, face_materials, voxel_materials_from_faces

HERE = pathlib.Path(__file__).resolve().parent
STYLE = HERE.parent
ROOT = STYLE.parent.parent
SRC = ROOT / "shared/3d/harbor.glb"
OUT = STYLE / "demo/models/harbor_voxel.glb"
MASK = STYLE / "demo/textures/water_mask.png"
NOTES = STYLE / "assets/harbor_voxel.json"

S = 0.1
G0 = np.array([-35.0, -1.5, -35.0])
G1 = np.array([21.0, 14.6, 13.5])
Y_CUT = -1.25                       # Flächen darunter liegen unter dem (deckenden) Voxelwasser
S_FAR = 1.0
G0_FAR = np.array([-150.0, -1.5, -340.0])

HEIGHTFIELD = {"Quay", "WestHill", "Headland"}
TERRAIN = {"WestHill", "Headland", "IslandsFar"}
MOVING = {"BoatA", "BoatB"}
SKIP = {"Sea"}

# Farbpalette (sRGB). Wärmer und etwas kräftiger als die neutralen glTF-Farben, wie typische Voxel-Paletten.
PALETTE = {
    "Stone": "a8998a", "StoneDark": "6c625c", "Wood": "a8723f", "WoodDark": "5e3d29",
    "WhitePaint": "eee6d6", "RedPaint": "c7372c", "Roof": "4b5b7e", "Glass": "ffd27a",
    "Rope": "cfb07a", "Metal": "3e4048", "Rock": "857b74", "Sand": "dcc28e", "Grass": "6d9c45",
    "Water": "2b6a80", "Earth": "6e4b33",
}
# Gewichte bei der Materialabstimmung: kleine, wichtige Teile setzen sich gegen große Flächen durch
WEIGHT = {"Glass": 8.0, "RedPaint": 3.0, "WhitePaint": 2.0, "Metal": 2.0, "Rope": 2.0, "WoodDark": 1.3}


def hash3(c, seed=0):
    x = c[:, 0] * 12.9898 + c[:, 1] * 78.233 + c[:, 2] * 37.719 + seed * 4.1414
    return np.modf(np.abs(np.sin(x) * 43758.5453))[0]


def hex2rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def smooth_noise(c, scale, seed):
    """grobes Rauschen aus Sinuswellen (gleichmäßig, ohne Bibliothek), Werte etwa -1..1"""
    p = c * S / scale
    return (np.sin(p[:, 0] * 1.7 + seed) * np.sin(p[:, 2] * 1.3 + 2 * seed)
            + 0.5 * np.sin(p[:, 0] * 3.1 - p[:, 2] * 2.3 + p[:, 1] * 1.9 + seed)) / 1.5


def colors_for(cells, matnames, objname, top=None, tone=None):
    """Farbe je Zelle (n,3) uint8. cells: globale Indizes, matnames: Name je Zelle."""
    n = len(cells)
    base = np.stack([hex2rgb(PALETTE[m]) for m in matnames]) if n else np.zeros((0, 3))
    h = hash3(cells)
    h2 = hash3(cells, 1)
    f = 1.0 + (h - 0.5) * 0.12                       # +-6 % je Voxel
    mn = np.array(matnames)
    col = base * f[:, None]
    # Muster je Material
    m = mn == "Grass"
    if m.any():
        tones = np.array([hex2rgb("6d9c45"), hex2rgb("5f8d3c"), hex2rgb("7eaa4f"), hex2rgb("88b259")])
        pick = (h2[m] * 4).astype(int).clip(0, 3)
        nz = smooth_noise(cells[m], 2.5, 1.0)
        col[m] = tones[pick] * (1.0 + 0.07 * nz)[:, None]
        if top is not None:
            fl = m & top & (hash3(cells, 7) > 0.985)
            col[fl] = np.where((hash3(cells[fl], 9) > 0.5)[:, None], hex2rgb("f2e6b0"), hex2rgb("e8c84a"))
    m = mn == "Rock"
    if m.any():
        # Fels in Flecken (grobes Rauschen in drei Stufen), je Voxel nur leicht abgewandelt
        nz = smooth_noise(cells[m], 1.2, 3.0) + 0.35 * smooth_noise(cells[m], 0.45, 5.0)
        tones = np.array([hex2rgb("776e69"), hex2rgb("857b74"), hex2rgb("958a80")])
        pick = np.digitize(nz, [-0.3, 0.35])
        col[m] = tones[pick] * (1.0 + (h2[m] - 0.5) * 0.06)[:, None]
    m = mn == "Sand"
    if m.any():
        col[m] *= (1.0 + (h2[m] - 0.5) * 0.10)[:, None]
    m = mn == "Earth"
    if m.any():
        col[m] *= (1.0 + (h2[m] - 0.5) * 0.12)[:, None]
    m = mn == "Roof"
    if m.any():
        row = (cells[m, 1] % 2 == 0)
        col[m] *= np.where(row, 0.93, 1.03)[:, None]
    if tone is not None:
        col *= tone[:, None]
    m = (mn == "Wood") | (mn == "WoodDark")
    if m.any():
        # Bretter: Ton je Streifen (entlang der längeren Achse wäre besser; hier je 2 Voxel in x und z)
        stripe = np.stack([cells[m, 0] // 2 + cells[m, 2] // 2 * 7, cells[m, 1] // 3, np.zeros(m.sum(), int)], 1)
        col[m] *= (0.93 + 0.12 * hash3(stripe, 5))[:, None]
    return np.clip(col, 0, 255).astype(np.uint8)


def despeckle(cells, m, rounds=2):
    """Bootsrümpfe: einzelne Voxel, deren Material unter den 26 Nachbarn höchstens einmal vorkommt, nehmen
    das häufigste Nachbarmaterial an (die dünnen Wände ergeben sonst Holzsprenkel im Lack)."""
    lo = cells.min(0) - 1
    dims = cells.max(0) - lo + 2
    for _ in range(rounds):
        g = np.full(dims, -1, int)
        g[tuple((cells - lo).T)] = m
        cnt = {}
        nb = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    if dx or dy or dz:
                        q = cells - lo + [dx, dy, dz]
                        nb.append(g[tuple(q.T)])
        nb = np.stack(nb, 1)
        same = (nb == m[:, None]).sum(1)
        out = m.copy()
        for i in np.nonzero(same <= 1)[0]:
            v = nb[i][nb[i] >= 0]
            if len(v):
                vals, c = np.unique(v, return_counts=True)
                out[i] = vals[c.argmax()]
        m = out
    return m


def main():
    t0 = time.time()
    j, A = read_glb(SRC)
    W, parent = world_matrices(j)
    matnames = [m["name"] for m in j["materials"]]
    if "Earth" not in matnames:
        j["materials"].append({"name": "Earth", "pbrMetallicRoughness": {
            "baseColorFactor": [0.16, 0.07, 0.035, 1.0], "metallicFactor": 0.0, "roughnessFactor": 1.0}})
        matnames.append("Earth")
    EARTH = matnames.index("Earth")
    weights = {matnames.index(k): v for k, v in WEIGHT.items()}

    dim = np.ceil((G1 - G0) / S).astype(int)
    owner = np.full(dim, -1, np.int16)
    gmat = np.full(dim, -1, np.int16)
    istop = np.zeros(dim, bool)
    objs = {}
    for ni, n in enumerate(j["nodes"]):
        if "mesh" not in n or n["name"] in SKIP:
            continue
        T, M = [], []
        for p in j["meshes"][n["mesh"]]["primitives"]:
            v = A[p["attributes"]["POSITION"]]
            v = (W[ni][:3, :3] @ v.T).T + W[ni][:3, 3]
            T.append(v[A[p["indices"]].reshape(-1, 3)])
            M += [p["material"]] * (len(A[p["indices"]]) // 3)
        objs[n["name"]] = (ni, np.concatenate(T), np.array(M))

    vox = {}
    for name, (ni, T, M) in objs.items():
        if name == "IslandsFar":
            continue
        t1 = time.time()
        hf = name in HEIGHTFIELD
        lo, solid, mat = voxelize_solid(T, M, G0, S, weights, heightfield=hf,
                                        bottom=G0[1] if hf else None, close_gaps=(name == "Quay"))
        idx = np.argwhere(solid) + lo
        m = mat[solid]
        ok = np.all((idx >= 0) & (idx < dim), axis=1)
        vox[name] = (idx[ok], m[ok])
        print(f"{name:15s} {ok.sum():8d} Voxel  {time.time() - t1:5.1f} s", flush=True)

    # statische Objekte ins Weltgitter; kleinere Objekte gewinnen bei Überlappung (Fenster vor Wand)
    ids = {name: k for k, name in enumerate(sorted(objs))}
    for name in sorted(vox, key=lambda k: -len(vox[k][0])):
        if name in MOVING:
            continue
        idx, m = vox[name]
        owner[idx[:, 0], idx[:, 1], idx[:, 2]] = ids[name]
        gmat[idx[:, 0], idx[:, 1], idx[:, 2]] = m

    # Laterne: Metallzellen im Bereich des Glases werden Glas (leuchtender Würfel), die vier Eckpfosten
    # und Deckel bleiben Metall; sonst verschwände das kleine Glas ganz im Gehäuse
    gl_lo = np.floor((objs["LanternGlass"][1].reshape(-1, 3).min(0) - G0) / S).astype(int)
    gl_hi = np.floor((objs["LanternGlass"][1].reshape(-1, 3).max(0) - G0) / S).astype(int)
    lp, lg = ids["LanternPost"], ids["LanternGlass"]
    box = owner[gl_lo[0] - 1:gl_hi[0] + 2, gl_lo[1]:gl_hi[1] + 1, gl_lo[2] - 1:gl_hi[2] + 2]
    corner = np.zeros(box.shape, bool)
    corner[[0, 0, -1, -1], :, [0, -1, 0, -1]] = True
    conv = (box == lp) & ~corner
    box[conv] = lg
    gmat[gl_lo[0] - 1:gl_hi[0] + 2, gl_lo[1]:gl_hi[1] + 1, gl_lo[2] - 1:gl_hi[2] + 2][conv] = matnames.index("Glass")
    print("Laterne: Glaszellen", int((box == lg).sum()))

    # Material je Voxel nach dem, was man von außen sieht (Gerade entlang der Flächennormale zum
    # Originalmodell), für alle Objekte außer Kai und Gelände: verhindert Sprenkel an dünnen Wänden
    occ = owner >= 0
    for name in vox:
        if name in HEIGHTFIELD or name in ("LanternGlass", "LanternPost", "RocksSea"):
            continue
        ni, T, M = objs[name]
        if name in MOVING:
            cells, m = vox[name]
            o_lo = cells.min(0) - 1
            o = np.zeros(cells.max(0) - o_lo + 2, bool)
            o[tuple((cells - o_lo).T)] = True
            fc = build_faces(cells, o, o_lo, G0, S)
        else:
            cells = np.argwhere(owner == ids[name])
            m = gmat[owner == ids[name]]
            fc = build_faces(cells, occ, np.zeros(3, int), G0, S)
        if fc is None:
            continue
        fm = face_materials(fc[0], fc[1], G0, S, T, M)
        m2 = voxel_materials_from_faces(cells, m.astype(int), fc[0], fm, weights, len(matnames))
        if name in MOVING:
            m2 = despeckle(cells, m2)
            vox[name] = (cells, m2)
        else:
            gmat[tuple(cells.T)] = m2
        print(f"{name:15s} Strahl-Material: {(fm >= 0).mean():.2f} getroffen, {(m2 != m).sum()} geändert", flush=True)

    # Gelände: Gras oben, darunter zwei Lagen Erde, dann Fels; Sand bleibt Sand
    above = np.zeros(dim, bool)
    above[:, :-1, :] = occ[:, 1:, :]
    istop = occ & ~above
    for name in TERRAIN & set(vox):
        tid = ids[name]
        sel = owner == tid
        # Material der obersten Zelle je Spalte nach unten fortsetzen
        colmat = np.full(dim[[0, 2]], -1, np.int16)
        depth = np.zeros(dim, np.int16)
        run = np.zeros(dim[[0, 2]], np.int16)
        for y in range(dim[1] - 1, -1, -1):
            s_ = sel[:, y, :]
            newtop = s_ & istop[:, y, :]
            colmat = np.where(newtop, gmat[:, y, :], colmat)
            run = np.where(newtop, 0, np.where(s_, run + 1, 0))
            depth[:, y, :] = run
            gm = gmat[:, y, :]
            grass = matnames.index("Grass")
            rock = matnames.index("Rock")
            new = np.where((colmat == grass) & (run >= 1) & (run <= 2), EARTH,
                           np.where((colmat == grass) & (run > 2), rock,
                                    np.where(run >= 1, colmat, gm)))
            gmat[:, y, :] = np.where(s_ & (new >= 0), new, gm)

    # Pflaster: je Originalplatte ein Ton (zusammenhängende Stone-Oberzellen des Kais, 4er-Nachbarschaft)
    quay_tone = {}
    qid = ids["Quay"]
    stone = matnames.index("Stone")
    topy = np.where(istop.any(1), istop.argmax(1), -1)            # oberste Zelle je Spalte (x, z)
    tm = np.full(topy.shape, -1, int)
    ok = topy >= 0
    xs, zs = np.nonzero(ok)
    tm[xs, zs] = np.where(owner[xs, topy[xs, zs], zs] == qid, gmat[xs, topy[xs, zs], zs], -1)
    slab = tm == stone
    lab = np.where(slab, np.arange(slab.size).reshape(slab.shape), -1)
    for _ in range(60):
        prev = lab
        for ax in (0, 1):
            for sh in (1, -1):
                nb = np.roll(lab, sh, axis=ax)
                lab = np.where(slab & (nb >= 0), np.minimum(lab, np.where(nb >= 0, nb, lab)), lab)
        if np.array_equal(prev, lab):
            break
    xs, zs = np.nonzero(slab)
    lid = lab[xs, zs]
    tval = 0.88 + 0.18 * hash3(np.stack([lid % 9973, lid // 9973, np.zeros_like(lid)], 1), 3)
    for x_, z_, tv in zip(xs, zs, tval):
        quay_tone[(x_, z_)] = tv
    print("Platten:", len(np.unique(lid)))

    notes = {"voxel_m": S, "objects": {}}
    newmesh = {}
    for name, (ni, T, M) in objs.items():
        if name == "IslandsFar":
            lo, solid, mat = voxelize_solid(T, M, G0_FAR, S_FAR, weights, heightfield=True, bottom=-1.5)
            cells = np.argwhere(solid) + lo
            m = mat[solid]
            occ_far = np.zeros(solid.shape, bool); occ_far |= solid
            fc = build_faces(cells, occ_far, lo, G0_FAR, S_FAR, skip_dirs=(5,),
                             keep=lambda c, d: (G0_FAR[1] + (c[:, 1] + 1) * S_FAR) > Y_CUT)
            gs, g0 = S_FAR, G0_FAR
            mnames = np.array(matnames)[m]
            top_far = np.ones(len(cells), bool)
            cell_cols = colors_for(cells * 10, mnames, name, top_far)
            cellmap = {tuple(c): q for q, c in enumerate(cells)}
        else:
            if name in MOVING:
                cells, m = vox[name]
                o_lo = cells.min(0) - 1
                o = np.zeros(cells.max(0) - o_lo + 2, bool)
                o[tuple((cells - o_lo).T)] = True
                occ_use, occ_lo = o, o_lo
            else:
                tid = ids[name]
                cells = np.argwhere(owner == tid)
                m = gmat[owner == tid]
                occ_use, occ_lo = occ, np.zeros(3, int)
            fc = build_faces(cells, occ_use, occ_lo, G0, S, skip_dirs=(5,),
                             keep=lambda c, d: (G0[1] + (c[:, 1] + 1) * S) > Y_CUT)
            gs, g0 = S, G0
            mnames = np.array(matnames)[m]
            top = istop[tuple(cells.T)] if name not in MOVING else np.ones(len(cells), bool)
            tone = None
            if name == "Quay":
                tone = np.array([quay_tone.get((c[0], c[2]), 1.0) for c in cells])
            cell_cols = colors_for(cells, mnames, name, top, tone)
        if fc is None:
            print("keine Flächen:", name)
            continue
        fcell, fdir, corners, ao = fc
        # Zelle -> Zeilenindex in cells
        key_cells = np.ravel_multi_index((cells - cells.min(0)).T, cells.max(0) - cells.min(0) + 1)
        key_f = np.ravel_multi_index((fcell - cells.min(0)).T, cells.max(0) - cells.min(0) + 1)
        order = np.argsort(key_cells)
        row = order[np.searchsorted(key_cells[order], key_f)]
        fmat = m[row]
        fcol = cell_cols[row]
        inv = np.linalg.inv(W[ni])
        loc = corners.reshape(-1, 3) @ inv[:3, :3].T + inv[:3, 3]
        corners_l = loc.reshape(-1, 4, 3)
        prims = []
        for mi in np.unique(fmat):
            sel = fmat == mi
            pos, nrm, col, uv, idx = faces_to_arrays(fdir[sel], corners_l[sel], ao[sel], fcol[sel])
            # Normalen ins lokale System drehen (Objekte können um y gedreht sein)
            nrm = (nrm @ inv[:3, :3].T)
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
            prims.append((int(mi), pos, nrm.astype(np.float32), col, uv, idx))
        newmesh[name] = prims
        notes["objects"][name] = {"voxels": int(len(cells)), "faces": int(len(fdir)),
                                  "voxel_m": gs}
        print(f"{name:15s} Flächen {len(fdir):8d}", flush=True)

    # glTF neu zusammensetzen: Meshes der Objekte ersetzen, alles andere (Knoten, Empties, Sea) behalten
    arrays = list(A)
    for n in j["nodes"]:
        if n.get("name") in newmesh:
            prims = []
            for (mi, pos, nrm, col, uv, idx) in newmesh[n["name"]]:
                # ohne NORMAL: glTF verlangt dann flache Normalen, Godot erzeugt sie beim Import (jede
                # Würfelfläche hat eigene Punkte, also genau die Flächennormale); spart ein Drittel der Datei
                base = len(arrays)
                arrays += [pos, col, uv, idx]
                j["accessors"] += [{"type": "VEC3"}, {"type": "VEC4", "normalized": True},
                                   {"type": "VEC2", "normalized": True}, {"type": "SCALAR"}]
                prims.append({"attributes": {"POSITION": base, "COLOR_0": base + 1, "TEXCOORD_0": base + 2},
                              "indices": base + 3, "material": mi})
            j["meshes"][n["mesh"]]["primitives"] = prims
    from glb import compact
    j, arrays = compact(j, arrays)
    j["asset"]["generator"] = "spielgrafik/styles/voxel/scripts/voxelize_harbor.py"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_glb(OUT, j, arrays)

    # Wassermaske: Land/Objekte auf Wasserhöhe, Abstand zum Ufer (für Schaum), Bootsrumpf
    wx0, wx1, wz0, wz1 = -20.0, 21.0, -35.0, 9.0
    nx, nz = int(round((wx1 - wx0) / S)), int(round((wz1 - wz0) / S))
    yl = slice(int((-1.0 - G0[1]) / S), int((-0.55 - G0[1]) / S))
    ix0, iz0 = int(round((wx0 - G0[0]) / S)), int(round((wz0 - G0[2]) / S))
    land = np.zeros((nx, nz), bool)
    gx = slice(max(ix0, 0), min(ix0 + nx, dim[0]))
    gz = slice(max(iz0, 0), min(iz0 + nz, dim[2]))
    land[gx.start - ix0:gx.stop - ix0, gz.start - iz0:gz.stop - iz0] = occ[gx, yl, gz].any(1)
    boat = np.zeros((nx, nz), bool)
    for b in MOVING:
        c, _ = vox[b]
        c = c[(c[:, 1] >= yl.start - 4)]
        bx, bz = c[:, 0] - ix0, c[:, 2] - iz0
        ok = (bx >= 0) & (bx < nx) & (bz >= 0) & (bz < nz)
        boat[bx[ok], bz[ok]] = True
    # Abstand zum Ufer in Zellen (Wellenfront, höchstens 12)
    dist = np.full((nx, nz), 12, np.int16)
    front = land | boat
    dist[front] = 0
    cur = front.copy()
    for d in range(1, 12):
        nb = cur.copy()
        nb[1:] |= cur[:-1]; nb[:-1] |= cur[1:]; nb[:, 1:] |= cur[:, :-1]; nb[:, :-1] |= cur[:, 1:]
        dist[nb & ~cur] = d
        cur = nb
    img = np.zeros((nz, nx, 3), np.uint8)       # Zeile = z, Spalte = x
    img[:, :, 0] = (land.T * 255)
    img[:, :, 1] = (dist.T * 255 // 12)
    img[:, :, 2] = (boat.T * 255)
    MASK.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(MASK)
    notes["water_mask"] = {"file": str(MASK.relative_to(STYLE)), "x0": wx0, "z0": wz0, "cell_m": S,
                           "size": [nx, nz], "channels": "R Land/Objekt auf Wasserhöhe, G Abstand zum Ufer "
                           "(0..12 Zellen -> 0..255), B Bootsrumpf"}
    tot_f = sum(v["faces"] for v in notes["objects"].values())
    notes["faces_total"] = int(tot_f)
    notes["triangles_total"] = int(tot_f * 2)
    notes["seconds"] = round(time.time() - t0, 1)
    NOTES.write_text(json.dumps(notes, indent=1, ensure_ascii=False))
    print(f"fertig: {OUT} ({OUT.stat().st_size / 1e6:.1f} MB), {tot_f} Flächen, {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
