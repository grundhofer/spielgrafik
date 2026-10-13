"""Minimaler glTF-2.0-Leser und -Schreiber (nur .glb, nur numpy) für die Voxel-Skripte.

read_glb(path)  -> (json, [numpy-Array je Accessor])
write_glb(path, json, arrays)  baut den Binärpuffer neu: jedes Array bekommt eine eigene bufferView,
                               accessor i = arrays[i]. Nicht mehr referenzierte Accessors vorher
                               mit compact() entfernen.
"""
import json, struct
import numpy as np

CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
CT_INV = {np.dtype(v): k for k, v in CT.items()}
NCOMP = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


def read_glb(path):
    b = open(path, "rb").read()
    assert b[:4] == b"glTF"
    jl = struct.unpack("<I", b[12:16])[0]
    j = json.loads(b[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack("<I", b[off:off + 4])[0]
    binc = b[off + 8:off + 8 + bl]
    arrays = []
    for a in j["accessors"]:
        dt = np.dtype(CT[a["componentType"]])
        nc = NCOMP[a["type"]]
        bv = j["bufferViews"][a["bufferView"]]
        start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = bv.get("byteStride", 0) or dt.itemsize * nc
        cnt = a["count"]
        if stride == dt.itemsize * nc:
            arr = np.frombuffer(binc, dt, cnt * nc, start).reshape(cnt, nc).copy()
        else:
            arr = np.stack([np.frombuffer(binc, dt, nc, start + i * stride) for i in range(cnt)])
        if a.get("normalized"):
            arr = arr.astype(np.float32) / np.iinfo(dt).max
        arrays.append(arr if nc > 1 else arr[:, 0])
    return j, arrays


def quat_to_mat(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def node_matrix(n):
    if "matrix" in n:
        return np.array(n["matrix"], float).reshape(4, 4).T
    m = np.eye(4)
    s = np.array(n.get("scale", [1, 1, 1]), float)
    m[:3, :3] = quat_to_mat(n.get("rotation", [0, 0, 0, 1])) * s
    m[:3, 3] = n.get("translation", [0, 0, 0])
    return m


def world_matrices(j):
    """Weltmatrix (4x4) je Knotenindex."""
    parent = {}
    for i, n in enumerate(j["nodes"]):
        for c in n.get("children", []):
            parent[c] = i
    out = {}

    def w(i):
        if i not in out:
            m = node_matrix(j["nodes"][i])
            out[i] = (w(parent[i]) @ m) if i in parent else m
        return out[i]

    for i in range(len(j["nodes"])):
        w(i)
    return out, parent


def compact(j, arrays):
    """Entfernt Accessors, auf die nichts mehr zeigt; nummeriert die Verweise um."""
    used = set()

    def walk(o):
        pass

    for m in j.get("meshes", []):
        for p in m["primitives"]:
            used.update(p["attributes"].values())
            if "indices" in p:
                used.add(p["indices"])
    for s in j.get("skins", []):
        if "inverseBindMatrices" in s:
            used.add(s["inverseBindMatrices"])
    for a in j.get("animations", []):
        for s in a["samplers"]:
            used.add(s["input"]); used.add(s["output"])
    order = sorted(used)
    remap = {old: new for new, old in enumerate(order)}
    for m in j.get("meshes", []):
        for p in m["primitives"]:
            p["attributes"] = {k: remap[v] for k, v in p["attributes"].items()}
            if "indices" in p:
                p["indices"] = remap[p["indices"]]
    for s in j.get("skins", []):
        if "inverseBindMatrices" in s:
            s["inverseBindMatrices"] = remap[s["inverseBindMatrices"]]
    for a in j.get("animations", []):
        for s in a["samplers"]:
            s["input"] = remap[s["input"]]; s["output"] = remap[s["output"]]
    j["accessors"] = [j["accessors"][i] for i in order]
    return j, [arrays[i] for i in order]


def write_glb(path, j, arrays, normalized=()):
    """arrays[i] gehört zu j['accessors'][i]; Typ, Anzahl, min/max werden neu gesetzt."""
    blob = bytearray()
    views = []
    for i, (a, arr) in enumerate(zip(j["accessors"], arrays)):
        arr = np.ascontiguousarray(arr)
        nc = 1 if arr.ndim == 1 else arr.shape[1]
        a.pop("byteOffset", None)
        a.pop("sparse", None)
        a["componentType"] = CT_INV[arr.dtype]
        a["count"] = int(arr.shape[0])
        if a.get("type") not in ("MAT4", "MAT3", "MAT2"):
            a["type"] = {1: "SCALAR", 2: "VEC2", 3: "VEC3", 4: "VEC4"}[nc]
        if a.get("normalized") and arr.dtype == np.float32:
            a.pop("normalized")
        while len(blob) % 4:
            blob.append(0)
        bv = {"buffer": 0, "byteOffset": len(blob), "byteLength": arr.nbytes}
        if a.pop("_target", None) is not None:
            pass
        views.append(bv)
        a["bufferView"] = i
        if a["type"] == "VEC3" and "min" in a or a.get("_minmax"):
            pass
        a.pop("_minmax", None)
        if a["type"] in ("VEC3",) and arr.dtype == np.float32:
            a["min"] = [float(v) for v in arr.min(0)]
            a["max"] = [float(v) for v in arr.max(0)]
        elif a["type"] == "SCALAR" and "min" in a and arr.dtype == np.float32:
            a["min"] = [float(arr.min())]; a["max"] = [float(arr.max())]
        blob += arr.tobytes()
    while len(blob) % 4:
        blob.append(0)
    j["bufferViews"] = views
    j["buffers"] = [{"byteLength": len(blob)}]
    js = json.dumps(j, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(blob), b"BIN\x00")); f.write(blob)
