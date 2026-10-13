"""Schreibt demo/badger.tscn: Skeleton2D mit Bone2D-Kette, Polygon2D je Teil (Gitter, UV, Gewichte) und
AnimationPlayer mit den Animationen walk / stop / idle (Teil von build_rig.py)."""
import math

import rig_def as R

FAR = {"arm_f", "leg_f"}


def f(x):
    """Gleitkommazahl immer mit Dezimalpunkt: Godot liest "0" als int, und eine Werte-Spur mit gemischten
    Typen (float/int) wird beim Abspielen übergangen (die Hüftdrehung blieb so bei 0)."""
    s = f"{x:.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return "0.0" if s in ("-0.0", "") else s


def v2(p):
    return f"Vector2({f(p[0])}, {f(p[1])})"


def bone_paths(bones):
    paths = {}
    for k, b in bones.items():
        chain, cur = [], k
        while cur:
            chain.append(cur)
            cur = bones[cur]["parent"]
        paths[k] = "/".join(reversed(chain))
    return paths


def write(path, bones, meshes, anims, meta=None):
    paths = bone_paths(bones)
    L = []
    ext = []
    for i, name in enumerate(sorted(meshes, key=lambda k: meshes[k]["draw"])):
        ext.append((f"{i + 1}_{name}", "Texture2D", f"res://art/badger_{name}.png", name))
    ext.append(("90_shader", "Shader", "res://shaders/badger.gdshader", None))
    n_sub = 2 + len(anims)
    L.append(f'[gd_scene load_steps={len(ext) + n_sub + 1} format=3]\n')
    for rid, typ, p, _ in ext:
        L.append(f'[ext_resource type="{typ}" path="{p}" id="{rid}"]')
    L.append("")
    L.append('[sub_resource type="ShaderMaterial" id="mat_badger"]')
    L.append('shader = ExtResource("90_shader")')
    L.append("")
    # Animationen
    for an, (length, loop, keys) in anims.items():
        L.append(f'[sub_resource type="Animation" id="anim_{an}"]')
        L.append(f'resource_name = &"{an}"')
        L.append(f"length = {f(length)}")
        if loop:
            L.append("loop_mode = 1")
        L.append(f"step = {f(1 / 60)}")
        tracks = []
        names = []
        for _, pose in keys:
            for b, props in pose.items():
                for pr in props:
                    if (b, pr) not in names:
                        names.append((b, pr))
        names.sort(key=lambda t: (list(bones).index(t[0]), t[1]))
        for ti, (b, pr) in enumerate(names):
            prop = {"rot": "rotation", "pos": "position", "scale": "scale"}[pr]
            times, vals = [], []
            for t, pose in keys:
                if b in pose and pr in pose[b]:
                    times.append(f(t))
                    x = pose[b][pr]
                    vals.append(f(x) if pr == "rot" else v2(x))
            L.append(f'tracks/{ti}/type = "value"')
            L.append(f"tracks/{ti}/imported = false")
            L.append(f"tracks/{ti}/enabled = true")
            L.append(f'tracks/{ti}/path = NodePath("Skeleton2D/{paths[b]}:{prop}")')
            L.append(f"tracks/{ti}/interp = 1")
            L.append(f"tracks/{ti}/loop_wrap = true")
            L.append(f"tracks/{ti}/keys = {{")
            L.append(f'"times": PackedFloat32Array({", ".join(times)}),')
            L.append(f'"transitions": PackedFloat32Array({", ".join(["1"] * len(times))}),')
            L.append('"update": 0,')
            L.append(f'"values": [{", ".join(vals)}]')
            L.append("}")
        L.append("")
    L.append('[sub_resource type="AnimationLibrary" id="animlib"]')
    L.append("_data = {")
    L.append(",\n".join(f'&"{an}": SubResource("anim_{an}")' for an in anims))
    L.append("}")
    L.append("")
    # Knoten
    L.append('[node name="Badger" type="Node2D"]')
    for k, v in (meta or {}).items():
        L.append(f"metadata/{k} = {f(v)}")
    L.append("")
    L.append('[node name="Skeleton2D" type="Skeleton2D" parent="."]')
    L.append("")
    for k, b in bones.items():
        par = b["parent"]
        pos = [b["pos"][0] - (bones[par]["pos"][0] if par else 0), b["pos"][1] - (bones[par]["pos"][1] if par else 0)]
        dx, dy = b["tip"][0] - b["pos"][0], b["tip"][1] - b["pos"][1]
        parent = "Skeleton2D" + ("/" + paths[par] if par else "")
        L.append(f'[node name="{k}" type="Bone2D" parent="{parent}"]')
        L.append(f"position = {v2(pos)}")
        L.append(f"rest = Transform2D(1, 0, 0, 1, {f(pos[0])}, {f(pos[1])})")
        L.append("auto_calculate_length_and_angle = false")
        L.append(f"length = {f(max(2.0, math.hypot(dx, dy)))}")
        L.append(f"bone_angle = {f(math.degrees(math.atan2(dy, dx)))}")
        L.append("")
    for rid, _, _, name in ext:
        if name is None:
            continue
        m = meshes[name]
        L.append(f'[node name="{name}" type="Polygon2D" parent="."]')
        L.append('material = SubResource("mat_badger")')
        if name in FAR:
            L.append(f"color = Color({f(R.FAR_TINT)}, {f(R.FAR_TINT)}, {f(R.FAR_TINT * 1.03)}, 1)")
        L.append("texture_filter = 4")
        L.append(f'texture = ExtResource("{rid}")')
        L.append('skeleton = NodePath("../Skeleton2D")')
        L.append("polygon = PackedVector2Array(" + ", ".join(f"{f(p[0])}, {f(p[1])}" for p in m["pos"]) + ")")
        L.append("uv = PackedVector2Array(" + ", ".join(f"{f(p[0])}, {f(p[1])}" for p in m["uv"]) + ")")
        L.append("polygons = [" + ", ".join(f"PackedInt32Array({a}, {b}, {c})" for a, b, c in m["tris"]) + "]")
        bl = []
        for b, w in sorted(m["weights"].items(), key=lambda t: list(bones).index(t[0])):
            bl.append(f'NodePath("{paths[b]}"), PackedFloat32Array(' + ", ".join(f(x) for x in w) + ")")
        L.append("bones = [" + ", ".join(bl) + "]")
        L.append("internal_vertex_count = 0")
        L.append("")
    L.append('[node name="AnimationPlayer" type="AnimationPlayer" parent="."]')
    L.append("libraries = {")
    L.append('&"": SubResource("animlib")')
    L.append("}")
    L.append("")
    path.write_text("\n".join(L) + "\n")
    print("geschrieben:", path, f"({path.stat().st_size // 1024} KB)")
