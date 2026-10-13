# Voxelisiert Figur und Requisiten aus shared/3d für das Sprite-Stacking.
#
#   blender -b --factory-startup -P styles/sprite-stacking/blender/voxelize.py -- \
#       --spec styles/sprite-stacking/blender/voxel_jobs.json --out <Ordner für .npz>
#
# Jeder Auftrag in der Spec-Datei nennt eine glb, Objektnamen (Kinder werden mitgenommen), die Voxelgröße in Metern,
# optional eine Animation mit Bildnummern und einen festen Gitterrahmen (bounds, in Blender-Koordinaten relativ zum
# Ursprung des ersten Objekts). Ergebnis je Auftrag: <name>.npz mit
#   mat    uint8 [frames, Z, Y, X]  Materialnummer je Voxel (0 = leer), Y = Bildzeile = -Blender-y (Süden unten)
#   names  Materialnamen zu den Nummern
#   vs, origin  Voxelgröße und Weltlage der Gitterecke (Blender-Koordinaten)
# Innen/außen: je zusammenhängendem Teil ein Strahl je Gittersäule von unten nach oben (Paritätsregel), dazu eine Hülle
# aus allen Voxeln, deren Mitte näher als eine halbe Voxelgröße an der Oberfläche liegt (dünne Teile, offene Flächen).
# Material = Material der nächstgelegenen Fläche.
import bpy, bmesh, json, math, os, sys
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
spec_path = argv[argv.index("--spec") + 1]
out_dir = argv[argv.index("--out") + 1]
only = argv[argv.index("--only") + 1].split(",") if "--only" in argv else None
os.makedirs(out_dir, exist_ok=True)
spec = json.load(open(spec_path))
root = os.path.dirname(os.path.abspath(spec_path))

MATS = spec["materials"]          # feste Reihenfolge, Nummer = Index + 1
MAT_ID = {n: i + 1 for i, n in enumerate(MATS)}


def base_name(n):
    return n.split(".")[0]


def load_glb(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=path)


def collect(names):
    obs = []
    for n in names:
        ob = bpy.data.objects[n]
        stack = [ob]
        while stack:
            o = stack.pop()
            if o.type == "MESH" and o.name != "Icosphere":
                obs.append(o)
            stack.extend(o.children)
    return obs


def triangles(obs):
    """Weltkoordinaten-Dreiecke (ausgewertet, also mit Pose) und Materialnummer je Dreieck."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, tris, mats = [], [], []
    for ob in obs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        mw = ev.matrix_world
        base = len(verts)
        verts.extend([tuple(mw @ v.co) for v in me.vertices])
        slots = [base_name(s.material.name) if s.material else "" for s in ob.material_slots]
        for lt in me.loop_triangles:
            tris.append(tuple(base + i for i in lt.vertices))
            name = slots[lt.material_index] if lt.material_index < len(slots) else ""
            if name not in MAT_ID:
                raise SystemExit(f"unbekanntes Material {name!r} in {ob.name}")
            mats.append(MAT_ID[name])
        ev.to_mesh_clear()
    return verts, tris, mats


def components(n_verts, tris):
    parent = list(range(n_verts))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for t in tris:
        ra = find(t[0])
        for b in t[1:]:
            rb = find(b)
            if ra != rb:
                parent[rb] = ra
    groups = {}
    for i, t in enumerate(tris):
        groups.setdefault(find(t[0]), []).append(i)
    return list(groups.values())


def voxelize(verts, tris, mats, vsz, lo, shape):
    """lo = Gitterecke (Blender x, y_max, z_min): Spalte X wächst mit x, Zeile Y wächst mit -y, Schicht Z mit z.
    vsz = (Größe in x/y, Größe in z): feinere Schichten als Rasterweite heißt flacherer Blickwinkel."""
    vs, vz = vsz
    nx, ny, nz = shape
    solid = np.zeros((nz, ny, nx), bool)
    V = np.array(verts)
    full = BVHTree.FromPolygons(verts, tris, all_triangles=True)
    # Parität je Teil und Säule
    for comp in components(len(verts), tris):
        ctris = [tris[i] for i in comp]
        used = sorted({v for t in ctris for v in t})
        remap = {v: k for k, v in enumerate(used)}
        cv = [verts[v] for v in used]
        ct = [tuple(remap[v] for v in t) for t in ctris]
        bvh = BVHTree.FromPolygons(cv, ct, all_triangles=True)
        P = V[used]
        x0 = max(0, int(math.floor((P[:, 0].min() - lo[0]) / vs)))
        x1 = min(nx - 1, int(math.floor((P[:, 0].max() - lo[0]) / vs)))
        y0 = max(0, int(math.floor((lo[1] - P[:, 1].max()) / vs)))
        y1 = min(ny - 1, int(math.floor((lo[1] - P[:, 1].min()) / vs)))
        zmin = P[:, 2].min() - 1.0
        for X in range(x0, x1 + 1):
            for Y in range(y0, y1 + 1):
                px = lo[0] + (X + 0.5) * vs + 1.37e-5
                py = lo[1] - (Y + 0.5) * vs + 2.11e-5
                o = Vector((px, py, zmin))
                hits = []
                for _ in range(64):
                    loc, nrm, idx, dist = bvh.ray_cast(o, Vector((0, 0, 1)))
                    if loc is None:
                        break
                    hits.append(loc.z)
                    o = Vector((px, py, loc.z + 1e-6))
                for a, b in zip(hits[0::2], hits[1::2]):
                    za = int(math.ceil((a - lo[2]) / vz - 0.5))
                    zb = int(math.floor((b - lo[2]) / vz - 0.5))
                    za, zb = max(za, 0), min(zb, nz - 1)
                    if zb >= za:
                        solid[za:zb + 1, Y, X] = True
    # Hülle und Material
    mat = np.zeros((nz, ny, nx), np.uint8)
    half = 0.5 * min(vs, vz)
    pmin, pmax = V.min(0), V.max(0)
    for Z in range(nz):
        pz = lo[2] + (Z + 0.5) * vz
        if pz < pmin[2] - vz or pz > pmax[2] + vz:
            continue
        for Y in range(ny):
            py = lo[1] - (Y + 0.5) * vs
            if py < pmin[1] - vs or py > pmax[1] + vs:
                continue
            for X in range(nx):
                px = lo[0] + (X + 0.5) * vs
                if px < pmin[0] - vs or px > pmax[0] + vs:
                    continue
                loc, nrm, idx, dist = full.find_nearest(Vector((px, py, pz)), 4 * vs)
                if loc is None:
                    continue
                # Hülle: Abstand im gestreckten Gitter (z auf Rasterweite umgerechnet)
                dz = (loc.z - pz) * (vs / vz)
                d2 = math.sqrt((loc.x - px) ** 2 + (loc.y - py) ** 2 + dz * dz)
                if solid[Z, Y, X] or d2 <= 0.5 * vs * 1.02:
                    mat[Z, Y, X] = mats[idx]
    return mat


def set_pose(arm, action_name, frame, bone_scale=None, bone_tilt=None):
    ad = arm.animation_data
    for t in ad.nla_tracks:
        t.mute = True
    act = bpy.data.actions[action_name]
    ad.action = act
    if hasattr(ad, "action_slot") and len(act.slots):
        ad.action_slot = act.slots[0]
    f = int(math.floor(frame))
    bpy.context.scene.frame_set(f, subframe=frame - f)
    # Stilisierung: einzelne Knochen vergrößern (z. B. Kopf), damit Gesicht und Mütze bei wenigen Voxeln lesbar bleiben
    for bone, k in (bone_scale or {}).items():
        arm.pose.bones[bone].scale = (k, k, k)
    bpy.context.view_layer.update()
    # Kopf nach hinten neigen (Gesicht zur hoch stehenden Kamera), Drehung um das Gelenk, Achse in Weltkoordinaten
    for bone, (axis, deg) in (bone_tilt or {}).items():
        pb = arm.pose.bones[bone]
        A = arm.matrix_world
        h = A @ pb.head
        R = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, Vector(axis)) @ Matrix.Translation(-h)
        pb.matrix = A.inverted() @ R @ A @ pb.matrix
        bpy.context.view_layer.update()


loaded = None
for job in spec["jobs"]:
    if only and job["name"] not in only:
        continue
    glb = os.path.normpath(os.path.join(root, job["glb"]))
    if loaded != glb:
        load_glb(glb)
        loaded = glb
    obs = collect(job["objects"])
    vs, vz = (job["vs"], job["vs"]) if not isinstance(job["vs"], list) else job["vs"]
    ref = bpy.data.objects[job["objects"][0]].matrix_world.translation.copy()
    frames = job.get("frames", [None])
    if job.get("bounds", "auto") == "auto":
        # Rahmen aus den Dreiecken (nur für unbewegte Objekte), eine Voxelgröße Rand
        V = np.array(triangles(obs)[0])
        pad = job.get("pad", 1)
        x0 = math.floor((V[:, 0].min() - ref.x) / vs) - pad
        x1 = math.ceil((V[:, 0].max() - ref.x) / vs) + pad
        y0 = math.floor((V[:, 1].min() - ref.y) / vs) - pad
        y1 = math.ceil((V[:, 1].max() - ref.y) / vs) + pad
        zc = job.get("zcut", None)          # Schnitt unten (z. B. Wasserlinie der Boote), in Metern relativ zum Ursprung
        z0 = math.floor(((V[:, 2].min() - ref.z) if zc is None else zc) / vz)
        z1 = math.ceil((V[:, 2].max() - ref.z) / vz) + 1
        b = [x0 * vs, x1 * vs, y0 * vs, y1 * vs, z0 * vz, z1 * vz]
    else:
        b = job["bounds"]   # [xmin, xmax, ymin, ymax, zmin, zmax] relativ zum Ursprung
    lo = (ref.x + b[0], ref.y + b[3], ref.z + b[4])
    shape = (int(round((b[1] - b[0]) / vs)), int(round((b[3] - b[2]) / vs)), int(round((b[5] - b[4]) / vz)))
    # Ursprung des Objekts im Gitter (Spalte, Zeile, Schicht) = Drehpunkt und Bodenhöhe beim Stapeln
    pivot = np.array([-b[0] / vs, b[3] / vs, -b[4] / vz])
    out = []
    for fr in frames:
        if fr is not None:
            set_pose(bpy.data.objects[job["armature"]], job["action"], fr, job.get("bone_scale"), job.get("bone_tilt"))
        verts, tris, mats = triangles(obs)
        out.append(voxelize(verts, tris, mats, (vs, vz), lo, shape))
        print(f"{job['name']} frame {fr}: {int((out[-1] > 0).sum())} Voxel, Gitter {shape}", flush=True)
    np.savez_compressed(os.path.join(out_dir, job["name"] + ".npz"), mat=np.stack(out),
                        names=np.array(MATS), vs=np.array([vs, vz]), origin=np.array(lo), pivot=pivot)
print("fertig", flush=True)
