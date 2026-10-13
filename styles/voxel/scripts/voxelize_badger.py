#!/usr/bin/env python3
"""Voxelisiert den Dachs-Kurier (shared/3d/badger.glb) zu demo/models/badger_voxel.glb.

    .venv/bin/python styles/voxel/scripts/voxelize_badger.py [--size 0.03125]

- Ruhepose (Bindepose) in einem eigenen Gitter (Standard 1/32 m, also 32 Voxel Höhe); z = 0 liegt in einer
  Zellmitte, damit das Gesicht symmetrisch bleibt.
- Jede Zelle gehört starr zu genau einem Knochen (dominantes Gewicht des nächsten Originalpunkts): Die Figur
  ist ein Satz starrer Voxelteile wie in Voxelspielen (Kopf, Rumpf, Arme, Beine, Schalende, Schwanz, Paket).
  Geschrieben als skinned Mesh mit Gewicht 1 auf diesen Knochen, mit Skelett, Skin und den Animationen Idle,
  Walk, Wave unverändert aus dem Original: Godot spielt sie ohne weitere Arbeit ab.
- Flächen zwischen Voxeln verschiedener Knochen bleiben stehen (sonst sähe man beim Beugen in hohle Teile).
- Ein paar Regeln als Code statt Handarbeit: Gesicht nach Kopfknochen gespiegelt (symmetrisch), Augen als
  je zwei schwarze Voxel übereinander in einem etwas helleren Augenstreifen, Nase als 3 Voxel breiter Block
  oben an der Schnauzenspitze, Schal in Strickreihen, Paket als Quader mit Schnur (siehe parcel_box).
"""
import argparse, json, pathlib, sys
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from glb import read_glb, write_glb, compact
from voxcore import voxelize_solid, build_faces, faces_to_arrays, face_materials, voxel_materials_from_faces

HERE = pathlib.Path(__file__).resolve().parent
STYLE = HERE.parent
ROOT = STYLE.parent.parent
SRC = ROOT / "shared/3d/badger.glb"

PALETTE = {
    "FurDark": "4d403d", "FurLight": "f4e7cf", "Cap": "4f6d34", "Brass": "e8b04c", "Vest": "617d3b",
    "Shirt": "f2e2c2", "Scarf": "cf3430", "Satchel": "7f452b", "Parcel": "cf9a62", "Nose": "1e1614",
    "Eye": "0c0808",
}
STRIPE = "6b5a55"       # Augenstreifen etwas heller als das übrige dunkle Fell, damit sich die Augen abheben
STRING = "4a2e1c"       # Paketschnur (Material Shirt wie im Original, Farbe dunkel für den Kontrast)
# Paket als Quader in Zellen (Bindepose): x vorn/hinten, y Höhe, z relativ zur Mittelzelle (+ = rechte Seite)
PARCEL_BOX = {"x": (12, 20), "y": (9, 13), "z": (4, 8)}
WEIGHT = {"Eye": 30.0, "Nose": 8.0, "Brass": 3.0, "Scarf": 1.6, "Satchel": 1.5, "Cap": 1.3, "Parcel": 1.2}


def hex2rgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], float)


def hash3(c, seed=0):
    x = c[:, 0] * 12.9898 + c[:, 1] * 78.233 + c[:, 2] * 37.719 + seed * 4.1414
    return np.modf(np.abs(np.sin(x) * 43758.5453))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", type=float, default=1 / 32)
    ap.add_argument("--out", default=str(STYLE / "demo/models/badger_voxel.glb"))
    ap.add_argument("--notes", default=str(STYLE / "assets/badger_voxel.json"))
    ap.add_argument("--no-face", dest="face", action="store_false", help="Gesicht nicht nachzeichnen")
    ap.add_argument("--no-parcel-box", dest="parcel", action="store_false",
                    help="Paket wie abgetastet lassen (ohne Quader und Schnur)")
    a = ap.parse_args()
    s = a.size

    j, A = read_glb(SRC)
    mats = [m["name"] for m in j["materials"]]
    T, M, MESH, VP, VJ = [], [], [], [], []
    for n in j["nodes"]:
        if "mesh" not in n:
            continue
        for p in j["meshes"][n["mesh"]]["primitives"]:
            v = A[p["attributes"]["POSITION"]].astype(float)
            idx = A[p["indices"]].reshape(-1, 3)
            T.append(v[idx]); M += [p["material"]] * len(idx); MESH += [n["mesh"]] * len(idx)
            jw = A[p["attributes"]["WEIGHTS_0"]]
            jj = A[p["attributes"]["JOINTS_0"]]
            VP.append(v); VJ.append(np.stack([jj[np.arange(len(jj)), jw.argmax(1)], np.full(len(v), n["mesh"])], 1))
    T = np.concatenate(T); M = np.array(M); VP = np.concatenate(VP); VJ = np.concatenate(VJ)
    g0 = np.array([-0.40 - 0.5 * s, 0.0, -0.5 * s - 12 * s])
    weights = {mats.index(k): v for k, v in WEIGHT.items()}
    lo, solid, mat = voxelize_solid(T, M, g0, s, weights, comp_small=0.08)
    cells = np.argwhere(solid) + lo
    m = mat[solid].astype(int)
    centers = g0 + (cells + 0.5) * s

    # Material je Voxel: was man von außen auf seinen freien Flächen sieht (Gerade entlang der Normale)
    occ0 = np.zeros(np.ptp(cells, 0) + 3, bool)
    olo0 = cells.min(0) - 1
    occ0[tuple((cells - olo0).T)] = True
    fc0 = build_faces(cells, occ0, olo0, g0, s)
    fm0 = face_materials(fc0[0], fc0[1], g0, s, T, M)
    print("Flächen mit Treffer:", (fm0 >= 0).mean().round(3))
    m = voxel_materials_from_faces(cells, m, fc0[0], fm0, weights, len(mats))

    # Knochen und Mesh (Figur / Paket) je Zelle: vom nächsten Originalpunkt
    d = ((centers[:, None, :] - VP[None, :, :]) ** 2).sum(-1)
    near = d.argmin(1)
    bone = VJ[near, 0].astype(int)
    mesh = VJ[near, 1].astype(int)

    names = np.array(mats)
    skin_joints = j["skins"][0]["joints"]
    bone_name = [j["nodes"][k]["name"] for k in skin_joints]
    head = bone_name.index("head")

    # Weste und Tasche gehören zum Rumpf: Voxel dieser Materialien, die über den nächsten Originalpunkt
    # (Ärmel am Armloch) an einem Arm hängen, gehen an die Brust; sonst hebt das Winken ein grünes Stück
    # Weste mit hoch
    arm_bones = [bone_name.index(b) for b in bone_name if b.split(".")[0] in ("upper_arm", "forearm")]
    torso_mats = [mats.index(k) for k in ("Vest", "Satchel", "Brass")]
    on_arm = np.isin(m, torso_mats) & np.isin(bone, arm_bones) & (mesh == 0)
    print("Rumpfvoxel von den Armen an die Brust:", int(on_arm.sum()))
    bone[on_arm] = bone_name.index("chest")

    # --- Paket als Regelkörper (Quader mit Schnur, an der rechten Hand) -------------------------
    if a.parcel:
        cells, m, bone, mesh = parcel_box(cells, m, bone, mesh, VP, VJ, g0, s, mats, bone_name)

    # --- Regeln für das Gesicht ---------------------------------------------------------------
    zc = cells[:, 2] - int(round((0.0 - g0[2]) / s - 0.5))       # 0 = Mittelzelle
    key = {tuple(c): q for q, c in enumerate(cells)}
    # Kopf symmetrisch: Material der Seite z >= 0 (rechte Seite, zur Kamera) auf die andere spiegeln,
    # nur für Fell, Augen und Nase (Mütze, Schal und Tasche dürfen asymmetrisch sein)
    face_mats = {mats.index(k) for k in ("FurDark", "FurLight", "Eye", "Nose")}
    for q in np.nonzero((bone == head) & (zc < 0))[0]:
        c = cells[q].copy(); c[2] = cells[q, 2] - 2 * zc[q]
        r = key.get(tuple(c))
        if r is not None and m[r] in face_mats and m[q] in face_mats:
            m[q] = m[r]
    stripe = np.zeros(len(cells), bool)
    if a.face:
        m, stripe = paint_face(cells, m, bone == head, zc, s, mats)

    cols = np.stack([hex2rgb(PALETTE[names[k]]) for k in m])
    cols[stripe] = hex2rgb(STRIPE)
    cols[(mesh == 1) & (names[m] == "Shirt")] = hex2rgb(STRING)
    h = hash3(cells)
    cols *= (1.0 + (h - 0.5) * 0.06)[:, None]
    scarf = names[m] == "Scarf"
    cols[scarf] *= np.where(cells[scarf, 1] % 2 == 0, 0.9, 1.04)[:, None]
    vest = names[m] == "Vest"
    cols[vest] *= (1.0 + (hash3(cells[vest], 2) - 0.5) * 0.05)[:, None]
    cols = np.clip(cols, 0, 255).astype(np.uint8)

    # Flächen: verdeckt nur durch Voxel desselben Knochens; AO aus der ganzen Figur
    occ = np.zeros(np.ptp(cells, 0) + 3, bool)
    olo = cells.min(0) - 1
    occ[tuple((cells - olo).T)] = True
    faces = []
    for b in np.unique(bone):
        for me in np.unique(mesh[bone == b]):
            sel = (bone == b) & (mesh == me)
            own = np.zeros_like(occ); own[tuple((cells[sel] - olo).T)] = True
            fc = build_faces(cells[sel], own, olo, g0, s)
            if fc is None:
                continue
            fcell, fdir, corners, _ = fc
            # AO mit der ganzen Figur (gleiches Verfahren wie build_faces)
            ao = face_ao(fcell, fdir, occ, olo)
            row = np.array([key[tuple(c)] for c in fcell])
            faces.append((int(b), int(me), fdir, corners, ao, cols[row], m[row]))

    # glTF zusammensetzen: Meshes Badger/Parcel ersetzen, Skin/Skelett/Animationen behalten
    arrays = list(A)
    newprims = {0: [], 1: []}
    for (b, me, fdir, corners, ao, fcol, fmat) in faces:
        for mi in np.unique(fmat):
            sel = fmat == mi
            pos, nrm, col, uv, idx = faces_to_arrays(fdir[sel], corners[sel], ao[sel], fcol[sel])
            jnt = np.zeros((len(pos), 4), np.uint8); jnt[:, 0] = b
            wts = np.zeros((len(pos), 4), np.float32); wts[:, 0] = 1.0
            base = len(arrays)
            arrays += [pos, nrm, col, uv, jnt, wts, idx]
            j["accessors"] += [{"type": "VEC3"}, {"type": "VEC3"}, {"type": "VEC4", "normalized": True},
                               {"type": "VEC2", "normalized": True}, {"type": "VEC4"}, {"type": "VEC4"}, {"type": "SCALAR"}]
            newprims[me].append({"attributes": {"POSITION": base, "NORMAL": base + 1, "COLOR_0": base + 2,
                                                "TEXCOORD_0": base + 3, "JOINTS_0": base + 4,
                                                "WEIGHTS_0": base + 5}, "indices": base + 6, "material": int(mi)})
    for me in (0, 1):
        # gleiche Materialien einer Fläche zusammenfassen wäre möglich; Godot fasst nicht zusammen, das ist
        # bei ~40 Flächen ohne Belang
        j["meshes"][me]["primitives"] = newprims[me]
    j, arrays = compact(j, arrays)
    j["asset"]["generator"] = "spielgrafik/styles/voxel/scripts/voxelize_badger.py"
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_glb(out, j, arrays)

    nf = sum(len(f[2]) for f in faces)
    ext = (np.ptp(cells, 0) + 1)
    notes = {"voxel_m": s, "voxels": int(len(cells)), "faces": int(nf), "extent_voxels_xyz": ext.tolist(),
             "parts": {bone_name[b]: int((bone == b).sum()) for b in np.unique(bone)},
             "materials": {names[k]: int((m == k).sum()) for k in np.unique(m)}}
    pathlib.Path(a.notes).write_text(json.dumps(notes, indent=1, ensure_ascii=False))
    print(json.dumps(notes, ensure_ascii=False))


def paint_face(cells, m, is_head, zc, s, mats):
    """Gesicht nach Regeln statt nach der Abtastung: Auf 1/32 m bleiben zwischen Mützenschirm und Schal nur
    drei bis vier Voxelreihen, die Abtastung macht daraus Flecken. Regeln wie bei Pixel-Art in Metern
    (Augenhöhe 0,84 m laut badger_notes.md): weißer Mittelstreifen, dunkle Augenstreifen mit je zwei
    schwarzen Augenvoxeln übereinander am Rand zur weißen Wange, weiße Wangen und Schnauze, Nase als 3 Voxel
    breiter, 2 Voxel hoher schwarzer Block oben an der Schnauzenspitze (darunter weiß).
    Gibt (Material je Voxel, Maske des Augenstreifens) zurück; der Streifen bekommt eine eigene, etwas
    hellere Farbe (STRIPE), damit sich die schwarzen Augen abheben."""
    FD, FL, EY, NO = (mats.index(k) for k in ("FurDark", "FurLight", "Eye", "Nose"))
    face = is_head & np.isin(m, [FD, FL, EY, NO])
    x, y = cells[:, 0], cells[:, 1]
    az = np.abs(zc)
    ye = int(0.84 / s)                       # Augenreihe
    xmax = x[is_head].max()                  # Schnauzenspitze
    hx = x[is_head]
    out = m.copy()
    front = face & (x >= xmax - 6)           # vorderer Teil des Kopfs (Gesicht); dahinter bleibt das Fell
    c_center = front & (az <= 1) & (y >= ye - 1)
    c_stripe = front & (az >= 2) & (az <= 3) & (y >= ye - 1)
    c_cheek = front & ((az >= 4) | (y <= ye - 2))
    out[c_cheek] = FL
    out[c_stripe] = FD
    out[c_center] = FL
    # Augenstreifen nach hinten bis zu den Ohren
    c_back = face & (x < xmax - 6) & (az >= 2) & (y >= ye - 1) & (y <= ye + 1)
    out[c_back] = FD
    # Nase: 3 Voxel breit (|z| <= 1), 2 hoch (Augenreihe und darunter) oben an der Schnauzenspitze; darunter
    # (Kinn) und auf der Oberseite der Schnauze bleibt es weiß. Ein 1 Voxel breiter, senkrechter Nasenbalken
    # las sich in der Nahaufnahme wie zwei Schneidezähne, ein 1 Voxel hoher Block mitten in der Spitze wie ein
    # Schlitz.
    tip = face & (x == xmax)
    out[tip & (az <= 1)] = FL
    out[tip & (y >= ye - 1) & (az <= 1)] = NO
    # Augen: je zwei schwarze Voxel (Augenreihe und darunter) am äußeren Rand des Streifens (|z| = 3),
    # vorderste Lage; daneben liegt die weiße Wange, so heben sie sich ab
    for side in (-1, 1):
        for yy in (ye, ye - 1):
            sel = face & (y == yy) & (zc == 3 * side)
            if sel.any():
                q = np.nonzero(sel)[0][np.argmax(x[sel])]
                out[q] = EY
    stripe = (c_stripe | c_back) & (out == FD)
    return out, stripe


def parcel_box(cells, m, bone, mesh, VP, VJ, g0, s, mats, bone_name):
    """Paket als Regelkörper: Die Abtastung ergab ein flaches, gemischtes Stück (Packpapier, Weste und Fell
    durcheinander, teils an Brust und Hüfte statt an der Hand), das sich in der Nahaufnahme wie ein Brett las.
    Hier wird es ein Quader aus PARCEL_BOX (9 × 5 × 5 Voxel), etwas weiter vorn und außen als das Original,
    ganz an hand.R, mit einer dunklen Schnur aus je einer Voxelreihe in den drei Mittelebenen (auf jeder Seite
    ein Kreuz). Übrige Körpervoxel, die nur über einen Paketpunkt an der Hand hingen, gehen an den Körper
    zurück; Packpapier-Voxel außerhalb des Quaders bekommen das Material ihrer Nachbarn."""
    PA, SH = mats.index("Parcel"), mats.index("Shirt")
    z0 = int(round((0.0 - g0[2]) / s - 0.5))
    hand = bone_name.index("hand.R")
    body_v = VJ[:, 1] == 0
    BP, BJ = VP[body_v], VJ[body_v, 0].astype(int)

    def nearest_body_bone(c):
        cen = g0 + (c + 0.5) * s
        return BJ[((cen[:, None, :] - BP[None]) ** 2).sum(-1).argmin(1)]

    (x0, x1), (y0, y1), (za, zb) = PARCEL_BOX["x"], PARCEL_BOX["y"], PARCEL_BOX["z"]
    gx, gy, gz = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1), np.arange(za, zb + 1) + z0,
                             indexing="ij")
    box = np.stack([gx, gy, gz], -1).reshape(-1, 3)
    bkey = {tuple(c) for c in box}
    inside = np.array([tuple(c) in bkey for c in cells])
    keep = ~inside
    cells, m, bone, mesh = cells[keep], m[keep], bone[keep], mesh[keep]

    # Körpervoxel, die am Paket-Mesh hingen, und Packpapier außerhalb des Quaders an den Körper
    stray = (mesh == 1) | (m == PA)
    if stray.any():
        bone[stray] = nearest_body_bone(cells[stray])
        mesh[stray] = 0
        key = {tuple(c): q for q, c in enumerate(cells)}
        for q in np.nonzero(m == PA)[0]:
            votes = {}
            for d in np.array(np.meshgrid([-1, 0, 1], [-1, 0, 1], [-1, 0, 1])).reshape(3, -1).T:
                r = key.get(tuple(cells[q] + d))
                if r is not None and m[r] != PA:
                    votes[m[r]] = votes.get(m[r], 0) + 1
            if votes:
                m[q] = max(votes, key=votes.get)

    # Quader mit Schnur in den drei Mittelebenen (nur die Oberfläche ist sichtbar)
    bm = np.full(len(box), PA)
    xm, ym, zm = (x0 + x1) // 2, (y0 + y1) // 2, (za + zb) // 2 + z0
    bm[(box[:, 0] == xm) | (box[:, 1] == ym) | (box[:, 2] == zm)] = SH
    print("Paket:", len(box), "Voxel, davon Schnur", int((bm == SH).sum()), "; ersetzt", int(inside.sum()),
          "; an den Körper zurück", int(stray.sum()))
    return (np.concatenate([cells, box]), np.concatenate([m, bm]),
            np.concatenate([bone, np.full(len(box), hand)]), np.concatenate([mesh, np.ones(len(box), int)]))


def face_ao(fcell, fdir, occ, olo):
    from voxcore import FACE_DIRS
    shp = np.array(occ.shape)

    def occ_at(idx):
        r = idx - olo
        ok = np.all((r >= 0) & (r < shp), axis=1)
        o = np.zeros(len(idx), bool)
        o[ok] = occ[r[ok, 0], r[ok, 1], r[ok, 2]]
        return o

    ao = np.zeros((len(fcell), 4), int)
    for d, (n, u, v) in enumerate(FACE_DIRS):
        sel = fdir == d
        if not sel.any():
            continue
        L = fcell[sel] + n
        for q, (su, sv) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
            s1 = occ_at(L + su * u); s2 = occ_at(L + sv * v); cc = occ_at(L + su * u + sv * v)
            ao[sel, q] = np.where(s1 & s2, 0, 3 - (s1.astype(int) + s2 + cc))
    return ao


if __name__ == "__main__":
    main()
