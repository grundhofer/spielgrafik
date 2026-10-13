#!/usr/bin/env python3
"""SVG -> Godot-Szene (.tscn) aus Polygon2D-Knoten.

    .venv/bin/python styles/flat-vektor/scripts/svg2godot.py in.svg out.tscn [--tol 0.25] [--stats out.json]

Wiederverwendbarer Weg für flache Vektorgrafik: Ein Ort wird als SVG gezeichnet (Vektorprogramm, Code oder
vtracer), dieses Skript macht daraus eine Godot-Szene, in der jede Form ein eigener, animierbarer Knoten ist.

Unterstützt (bewusst klein, siehe Fehlermeldungen):
  * <g> mit id, transform (translate/rotate/scale/matrix ohne Scherung), opacity  -> Node2D (position/rotation/
    scale/modulate). Gruppen mit id behalten ihren Ursprung: so legt das SVG die Drehpunkte für die Animation fest.
  * <path> (M L H V C S Q T A Z, absolut und relativ), <rect> (rx/ry), <circle>, <ellipse>, <polygon>
    -> Polygon2D; Kurven werden adaptiv mit Toleranz --tol (px) in Punkte zerlegt. Mehrere Teilpfade ergeben
    mehrere Polygon2D (keine Löcher: Löcher im SVG vermeiden oder vtracer im Modus "stacked" verwenden).
  * fill (#rgb, #rrggbb, rgb(), none, url(#id)), fill-opacity, opacity, auch in style="…".
  * <linearGradient>/<radialGradient> (userSpaceOnUse oder objectBoundingBox, gradientTransform, href,
    stop-color/stop-opacity) -> GradientTexture2D + UV je Punkt (UV ist affin zur Position, daher exakt).
  * data-blend="add" (Element oder Gruppe) -> CanvasItemMaterial mit additiver Mischung (Lichtschein).
Warnt (stderr und --stats) bei sich selbst schneidenden Polygonen und bei Verläufen, deren UV die Textur nicht trifft.
"""
import argparse, json, math, pathlib, re, sys
import xml.etree.ElementTree as ET

SVG = "{http://www.w3.org/2000/svg}"
XLINK = "{http://www.w3.org/1999/xlink}"
TEX_W = 1024   # Breite der linearen Verlaufstexturen
TEX_R = 256    # Kantenlänge der radialen Verlaufstexturen

# ---------------------------------------------------------------- Affine Abbildungen (SVG-Reihenfolge a b c d e f)
I = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def mul(m, n):  # m nach n anwenden: (m ∘ n)(p) = m(n(p))
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + c * B, b * A + d * B, a * C + c * D, b * C + d * D, a * E + c * F + e, b * E + d * F + f)


def ap(m, p):
    return (m[0] * p[0] + m[2] * p[1] + m[4], m[1] * p[0] + m[3] * p[1] + m[5])


def inv(m):
    a, b, c, d, e, f = m
    det = a * d - b * c
    if abs(det) < 1e-12:
        raise ValueError("Transformation nicht umkehrbar")
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * e + ic * f), -(ib * e + id_ * f))


def parse_transform(s):
    m = I
    for name, args in re.findall(r"(\w+)\s*\(([^)]*)\)", s or ""):
        v = [float(x) for x in re.split(r"[\s,]+", args.strip()) if x]
        if name == "translate":
            t = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0.0)
        elif name == "scale":
            t = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            r = math.radians(v[0])
            t = (math.cos(r), math.sin(r), -math.sin(r), math.cos(r), 0, 0)
            if len(v) == 3:
                t = mul(mul((1, 0, 0, 1, v[1], v[2]), t), (1, 0, 0, 1, -v[1], -v[2]))
        elif name == "matrix":
            t = tuple(v)
        elif name == "skewX":
            t = (1, 0, math.tan(math.radians(v[0])), 1, 0, 0)
        elif name == "skewY":
            t = (1, math.tan(math.radians(v[0])), 0, 1, 0, 0)
        else:
            raise ValueError(f"unbekannte Transformation {name}")
        m = mul(m, t)
    return m


def scale_of(m):
    return math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0


# ---------------------------------------------------------------- Farben und Stil
NAMED = {"black": "#000000", "white": "#ffffff", "red": "#ff0000", "none": None}


def parse_color(s):
    s = (s or "").strip()
    if s in NAMED:
        s = NAMED[s]
        if s is None:
            return None
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    m = re.match(r"rgb\(\s*([\d.]+)\s*,\s*([\d.]+)\s*,\s*([\d.]+)\s*\)", s)
    if m:
        return tuple(float(x) / 255.0 for x in m.groups())
    raise ValueError(f"Farbe nicht verstanden: {s!r}")


def style_of(el):
    st = dict(el.attrib)
    for part in (el.get("style") or "").split(";"):
        if ":" in part:
            k, v = part.split(":", 1)
            st[k.strip()] = v.strip()
    return st


# ---------------------------------------------------------------- Kurven zerlegen
def flatten_cubic(p0, p1, p2, p3, tol, out, depth=0):
    # Flachheit: Abstand der Kontrollpunkte von der Sehne
    dx, dy = p3[0] - p0[0], p3[1] - p0[1]
    d1 = abs((p1[0] - p3[0]) * dy - (p1[1] - p3[1]) * dx)
    d2 = abs((p2[0] - p3[0]) * dy - (p2[1] - p3[1]) * dx)
    if depth > 12 or (d1 + d2) ** 2 <= tol * tol * (dx * dx + dy * dy) * 4 or (dx == 0 and dy == 0 and depth > 4):
        out.append(p3)
        return
    m = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    p01, p12, p23 = m(p0, p1), m(p1, p2), m(p2, p3)
    p012, p123 = m(p01, p12), m(p12, p23)
    mid = m(p012, p123)
    flatten_cubic(p0, p01, p012, mid, tol, out, depth + 1)
    flatten_cubic(mid, p123, p23, p3, tol, out, depth + 1)


def arc_to_cubics(p0, rx, ry, phi, large, sweep, p1):
    """SVG-Bogen als Folge kubischer Bézierkurven (Standardverfahren aus der SVG-Implementierungsnotiz)."""
    if rx == 0 or ry == 0:
        return [(p0, p0, p1, p1)]
    cp, sp = math.cos(phi), math.sin(phi)
    dx, dy = (p0[0] - p1[0]) / 2, (p0[1] - p1[1]) / 2
    x1, y1 = cp * dx + sp * dy, -sp * dx + cp * dy
    rx, ry = abs(rx), abs(ry)
    lam = x1 * x1 / (rx * rx) + y1 * y1 / (ry * ry)
    if lam > 1:
        rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1
    den = rx * rx * y1 * y1 + ry * ry * x1 * x1
    co = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cx1, cy1 = co * rx * y1 / ry, -co * ry * x1 / rx
    cx = cp * cx1 - sp * cy1 + (p0[0] + p1[0]) / 2
    cy = sp * cx1 + cp * cy1 + (p0[1] + p1[1]) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    t1 = ang(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry)
    dt = ang((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry)
    if not sweep and dt > 0:
        dt -= 2 * math.pi
    elif sweep and dt < 0:
        dt += 2 * math.pi
    n = max(1, int(math.ceil(abs(dt) / (math.pi / 2))))
    out, step = [], dt / n
    k = 4 / 3 * math.tan(step / 4)
    pt = lambda t: (cx + rx * math.cos(t) * cp - ry * math.sin(t) * sp, cy + rx * math.cos(t) * sp + ry * math.sin(t) * cp)
    der = lambda t: (-rx * math.sin(t) * cp - ry * math.cos(t) * sp, -rx * math.sin(t) * sp + ry * math.cos(t) * cp)
    t = t1
    for _ in range(n):
        a, b = pt(t), pt(t + step)
        da, db = der(t), der(t + step)
        out.append((a, (a[0] + k * da[0], a[1] + k * da[1]), (b[0] - k * db[0], b[1] - k * db[1]), b))
        t += step
    return out


TOKEN = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def path_to_subpaths(d, tol):
    toks = TOKEN.findall(d)
    i, cmd = 0, None
    cur, start = (0.0, 0.0), (0.0, 0.0)
    last_c = last_q = None
    subs, pts = [], []

    def num():
        nonlocal i
        v = float(toks[i]); i += 1
        return v

    def close_sub():
        nonlocal pts
        if len(pts) >= 3:
            subs.append(pts)
        pts = []

    while i < len(toks):
        if re.match(r"[A-Za-z]", toks[i]):
            cmd = toks[i]; i += 1
        rel = cmd.islower()
        C = cmd.upper()
        ox, oy = cur if rel else (0.0, 0.0)
        if C == "Z":
            close_sub(); cur = start; last_c = last_q = None
            continue
        if C == "M":
            close_sub()
            cur = (ox + num(), oy + num()); start = cur; pts = [cur]
            cmd = "l" if rel else "L"
            last_c = last_q = None
            continue
        if C == "L":
            cur = (ox + num(), oy + num()); pts.append(cur); last_c = last_q = None
        elif C == "H":
            cur = ((ox if rel else 0) + num(), cur[1]); pts.append(cur); last_c = last_q = None
        elif C == "V":
            cur = (cur[0], (oy if rel else 0) + num()); pts.append(cur); last_c = last_q = None
        elif C in "CS":
            if C == "C":
                c1 = (ox + num(), oy + num())
            else:
                c1 = (2 * cur[0] - last_c[0], 2 * cur[1] - last_c[1]) if last_c else cur
            c2 = (ox + num(), oy + num()); p = (ox + num(), oy + num())
            flatten_cubic(cur, c1, c2, p, tol, pts)
            last_c, last_q, cur = c2, None, p
        elif C in "QT":
            if C == "Q":
                q = (ox + num(), oy + num())
            else:
                q = (2 * cur[0] - last_q[0], 2 * cur[1] - last_q[1]) if last_q else cur
            p = (ox + num(), oy + num())
            c1 = (cur[0] + 2 / 3 * (q[0] - cur[0]), cur[1] + 2 / 3 * (q[1] - cur[1]))
            c2 = (p[0] + 2 / 3 * (q[0] - p[0]), p[1] + 2 / 3 * (q[1] - p[1]))
            flatten_cubic(cur, c1, c2, p, tol, pts)
            last_q, last_c, cur = q, None, p
        elif C == "A":
            rx, ry, rot, la, sw = num(), num(), num(), num(), num()
            p = (ox + num(), oy + num())
            for a, b, c, e in arc_to_cubics(cur, rx, ry, math.radians(rot), int(la), int(sw), p):
                flatten_cubic(a, b, c, e, tol, pts)
            cur = p; last_c = last_q = None
        else:
            raise ValueError(f"Pfadbefehl {cmd} nicht unterstützt")
    close_sub()
    return subs


def ellipse_pts(cx, cy, rx, ry, tol):
    r = max(rx, ry)
    n = max(16, int(math.ceil(math.pi / math.acos(max(-1.0, 1 - tol / max(r, 1e-6))))))
    return [(cx + rx * math.cos(2 * math.pi * k / n), cy + ry * math.sin(2 * math.pi * k / n)) for k in range(n)]


def rect_pts(x, y, w, h, rx, ry, tol):
    if rx <= 0 and ry <= 0:
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    rx = min(rx or ry, w / 2); ry = min(ry or rx, h / 2)
    corner = ellipse_pts(0, 0, rx, ry, tol)
    n = len(corner) // 4
    out = []
    for q, (cx, cy) in enumerate([(x + w - rx, y + h - ry), (x + rx, y + h - ry), (x + rx, y + ry), (x + w - rx, y + ry)]):
        for k in range(n + 1):
            t = (q + k / n) * math.pi / 2
            out.append((cx + rx * math.cos(t), cy + ry * math.sin(t)))
    return out


def self_intersects(pts):
    """True, wenn sich zwei nicht benachbarte Kanten schneiden (Godot zeichnet solche Polygon2D stillschweigend nicht)."""
    n = len(pts)
    if n > 1500:
        return False
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    edges = [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        a, b = edges[i]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            c, d = edges[j]
            if max(a[0], b[0]) < min(c[0], d[0]) or max(c[0], d[0]) < min(a[0], b[0]) or \
               max(a[1], b[1]) < min(c[1], d[1]) or max(c[1], d[1]) < min(a[1], b[1]):
                continue
            d1, d2, d3, d4 = cross(c, d, a), cross(c, d, b), cross(a, b, c), cross(a, b, d)
            if ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0)) and d1 * d2 < 0 and d3 * d4 < 0:
                return True
    return False


def clean(pts):
    out = []
    for p in pts:
        if not out or abs(p[0] - out[-1][0]) > 1e-3 or abs(p[1] - out[-1][1]) > 1e-3:
            out.append(p)
    if len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-3 and abs(out[0][1] - out[-1][1]) < 1e-3:
        out.pop()
    return out


# ---------------------------------------------------------------- Umwandlung
class Conv:
    def __init__(self, root, tol):
        self.tol, self.root = tol, root
        self.defs = {el.get("id"): el for el in root.iter() if el.get("id") and el.tag in (SVG + "linearGradient", SVG + "radialGradient")}
        self.res = []        # (id, text) Unterressourcen
        self.grad_res = {}   # Verlauf-id -> Texturressource
        self.add_mat = None
        self.nodes = []      # (name, type, parent_path, props)
        self.stats = {"polygons": 0, "points": 0, "groups": 0, "gradients": 0, "warnings": []}

    # --- Verläufe
    def grad_chain(self, el):
        attrs, stops, seen = {}, None, set()
        while el is not None and el.get("id") not in seen:
            seen.add(el.get("id"))
            for k, v in el.attrib.items():
                attrs.setdefault(k, v)
            if stops is None:
                s = [c for c in el if c.tag == SVG + "stop"]
                if s:
                    stops = s
            href = el.get("href") or el.get(XLINK + "href")
            el = self.defs.get(href[1:]) if href else None
        return attrs, stops or []

    def gradient(self, gid):
        el = self.defs[gid]
        attrs, stops = self.grad_chain(el)
        radial = el.tag == SVG + "radialGradient"
        if gid not in self.grad_res:
            offs, cols = [], []
            for s in stops:
                st = style_of(s)
                o = st.get("offset", "0")
                o = float(o[:-1]) / 100 if o.endswith("%") else float(o)
                c = parse_color(st.get("stop-color", "#000"))
                a = float(st.get("stop-opacity", "1"))
                offs.append(min(1, max(0, o))); cols.append((*c, a))
            g = f"Gradient_{len(self.grad_res) + 1}"
            t = f"GradientTexture2D_{len(self.grad_res) + 1}"
            self.res.append((g, "Gradient", [
                "offsets = PackedFloat32Array(" + ", ".join(f"{o:.4f}" for o in offs) + ")",
                "colors = PackedColorArray(" + ", ".join(", ".join(f"{v:.4f}" for v in c) for c in cols) + ")"]))
            if radial:
                props = [f'gradient = SubResource("{g}")', f"width = {TEX_R}", f"height = {TEX_R}", "fill = 1",
                         "fill_from = Vector2(0.5, 0.5)", "fill_to = Vector2(1, 0.5)"]
            else:
                props = [f'gradient = SubResource("{g}")', f"width = {TEX_W}", "height = 1"]
            self.res.append((t, "GradientTexture2D", props))
            self.grad_res[gid] = t
            self.stats["gradients"] += 1
        return self.grad_res[gid], attrs, radial

    def uv_for(self, pts_local, attrs, radial):
        units = attrs.get("gradientUnits", "objectBoundingBox")
        gt = parse_transform(attrs.get("gradientTransform", ""))
        if units == "objectBoundingBox":
            xs, ys = [p[0] for p in pts_local], [p[1] for p in pts_local]
            bx, by = min(xs), min(ys)
            bw, bh = (max(xs) - bx) or 1, (max(ys) - by) or 1
            to_unit = (1 / bw, 0, 0, 1 / bh, -bx / bw, -by / bh)
            m = mul(inv(gt), to_unit)
            frac = lambda v, dflt: float(v[:-1]) / 100 if v.endswith("%") else float(v)
        else:
            m = inv(gt)
            frac = lambda v, dflt: float(v[:-1]) / 100 if v.endswith("%") else float(v)
        uvs = []
        if radial:
            cx, cy = frac(attrs.get("cx", "50%"), 0.5), frac(attrs.get("cy", "50%"), 0.5)
            r = frac(attrs.get("r", "50%"), 0.5)
            if attrs.get("fx") not in (None, attrs.get("cx")) or attrs.get("fy") not in (None, attrs.get("cy")):
                self.stats["warnings"].append("Brennpunkt fx/fy ignoriert")
            for p in pts_local:
                g = ap(m, p)
                uvs.append((((g[0] - cx) / r * 0.5 + 0.5) * TEX_R, ((g[1] - cy) / r * 0.5 + 0.5) * TEX_R))
        else:
            x1, y1 = frac(attrs.get("x1", "0%"), 0), frac(attrs.get("y1", "0%"), 0)
            x2, y2 = frac(attrs.get("x2", "100%"), 1), frac(attrs.get("y2", "0%"), 0)
            dx, dy = x2 - x1, y2 - y1
            L2 = dx * dx + dy * dy or 1
            for p in pts_local:
                g = ap(m, p)
                t = ((g[0] - x1) * dx + (g[1] - y1) * dy) / L2
                uvs.append((t * TEX_W, 0.5))
        return uvs

    def check_uv(self, uvs, radial, gid, where):
        """Warnt, wenn das UV eines Polygons die Verlaufstextur gar nicht trifft: Die Fläche erscheint dann einfarbig
        in der ersten oder letzten Stufe. Typische Ursache: userSpaceOnUse-Koordinaten absolut angegeben, die Form
        liegt aber in einer verschobenen Gruppe (SVG rechnet den Verlauf im lokalen System der Form)."""
        lim = TEX_R if radial else TEX_W
        us = [u for u, _ in uvs]
        lo, hi = min(us), max(us)
        outside = hi <= 0 or lo >= lim
        if radial:
            vs = [v for _, v in uvs]
            outside = outside or max(vs) <= 0 or min(vs) >= lim
        if outside:
            self.stats["gradient_uv_outside"] = self.stats.get("gradient_uv_outside", 0) + 1
            self.stats["warnings"].append(f"Verlauf {gid} wirkt nicht auf {where}: UV u {lo:.0f}…{hi:.0f} liegt ganz "
                                          f"außerhalb von 0…{lim} (Fläche wird einfarbig)")

    # --- Knoten
    def name(self, parent, wanted):
        base = re.sub(r"[.:@/\"%\s]", "_", wanted) or "n"
        used = self.used.setdefault(parent, set())
        n, k = base, 2
        while n in used:
            n, k = f"{base}_{k}", k + 1
        used.add(n)
        return n

    def run(self):
        self.used = {}
        vb = self.root.get("viewBox")
        self.size = [float(v) for v in re.split(r"[\s,]+", vb.strip())][2:] if vb else [float(self.root.get("width", 0)), float(self.root.get("height", 0))]
        rootname = self.root.get("id") or "svg"
        self.nodes.append((rootname, "Node2D", None, []))
        self.walk(self.root, ".", I, {"fill": "#000000", "blend": None})
        return self

    def walk(self, el, parent, ctm, inh):
        for ch in el:
            tag = ch.tag.replace(SVG, "")
            if tag in ("defs", "title", "desc", "metadata", "linearGradient", "radialGradient", "style") or ch.get("display") == "none":
                continue
            st = style_of(ch)
            sub = dict(inh)
            if "fill" in st:
                sub["fill"] = st["fill"]
            if "data-blend" in st:
                sub["blend"] = st["data-blend"]
            t = parse_transform(ch.get("transform"))
            if tag == "g":
                gname = self.name(parent, ch.get("id") or f"g{self.stats['groups'] + 1}")
                props = []
                a, b, c, d, e, f = t
                if abs(a * c + b * d) > 1e-6 * max(1, abs(a * d - b * c)):
                    raise ValueError(f"Gruppe {gname}: Scherung nicht unterstützt")
                if (e, f) != (0, 0):
                    props.append(f"position = Vector2({e:.3f}, {f:.3f})")
                rot = math.atan2(b, a)
                sx = math.hypot(a, b)
                sy = (a * d - b * c) / sx if sx else 0
                if abs(rot) > 1e-9:
                    props.append(f"rotation = {rot:.6f}")
                if abs(sx - 1) > 1e-9 or abs(sy - 1) > 1e-9:
                    props.append(f"scale = Vector2({sx:.5f}, {sy:.5f})")
                op = float(st.get("opacity", "1"))
                if op < 1:
                    props.append(f"modulate = Color(1, 1, 1, {op:.4f})")
                self.nodes.append((gname, "Node2D", parent, props))
                self.stats["groups"] += 1
                self.walk(ch, gname if parent == "." else f"{parent}/{gname}", mul(ctm, t), sub)
                continue
            tol = self.tol / scale_of(mul(ctm, t))
            if tag == "path":
                subs = path_to_subpaths(ch.get("d", ""), tol)
            elif tag == "rect":
                g = lambda k: float(ch.get(k, "0"))
                subs = [rect_pts(g("x"), g("y"), g("width"), g("height"), g("rx"), g("ry"), tol)]
            elif tag == "circle":
                r = float(ch.get("r"))
                subs = [ellipse_pts(float(ch.get("cx", 0)), float(ch.get("cy", 0)), r, r, tol)]
            elif tag == "ellipse":
                subs = [ellipse_pts(float(ch.get("cx", 0)), float(ch.get("cy", 0)), float(ch.get("rx")), float(ch.get("ry")), tol)]
            elif tag == "polygon":
                v = [float(x) for x in re.split(r"[\s,]+", ch.get("points").strip())]
                subs = [list(zip(v[0::2], v[1::2]))]
            else:
                self.stats["warnings"].append(f"Element <{tag}> übersprungen")
                continue
            fill = sub["fill"]
            if fill in (None, "none"):
                continue
            alpha = float(st.get("fill-opacity", "1")) * float(st.get("opacity", "1"))
            tex = attrs = None
            m = re.match(r"url\(#([^)]+)\)", fill)
            if m:
                tex, attrs, radial = self.gradient(m.group(1))
                col = (1, 1, 1, alpha)
            else:
                col = (*parse_color(fill), alpha)
            for k, pts in enumerate(subs):
                pts = clean(pts)
                if len(pts) < 3:
                    continue
                world = [ap(t, p) for p in pts]   # nur die eigene Transformation backen
                if self_intersects(world):
                    self.stats["self_intersecting"] = self.stats.get("self_intersecting", 0) + 1
                    self.stats["warnings"].append(f"Polygon {ch.get('id') or '?'} schneidet sich selbst (Godot zeichnet es nicht)")
                nm = ch.get("id") or f"p{self.stats['polygons'] + 1}"
                if len(subs) > 1:
                    nm = f"{nm}_{k + 1}"
                nm = self.name(parent, nm)
                props = [f"color = Color({col[0]:.4f}, {col[1]:.4f}, {col[2]:.4f}, {col[3]:.4f})"]
                if sub["blend"] == "add":
                    if not self.add_mat:
                        self.add_mat = "CanvasItemMaterial_add"
                        self.res.append((self.add_mat, "CanvasItemMaterial", ["blend_mode = 1"]))
                    props.append(f'material = SubResource("{self.add_mat}")')
                if tex:
                    props.append(f'texture = SubResource("{tex}")')
                props.append("polygon = PackedVector2Array(" + ", ".join(f"{x:.2f}, {y:.2f}" for x, y in world) + ")")
                if tex:
                    uvs = self.uv_for(pts, attrs, radial)
                    self.check_uv(uvs, radial, m.group(1), f"{parent}/{nm}")
                    props.append("uv = PackedVector2Array(" + ", ".join(f"{u:.2f}, {v:.2f}" for u, v in uvs) + ")")
                self.nodes.append((nm, "Polygon2D", parent, props))
                self.stats["polygons"] += 1
                self.stats["points"] += len(world)

    def tscn(self):
        out = ["[gd_scene format=3]", ""]
        for rid, typ, props in self.res:
            out += [f'[sub_resource type="{typ}" id="{rid}"]', *props, ""]
        for name, typ, parent, props in self.nodes:
            head = f'[node name="{name}" type="{typ}"' + (f' parent="{parent}"' if parent else "") + "]"
            out += [head, *props, ""]
        return "\n".join(out)


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("svg")
    ap_.add_argument("out")
    ap_.add_argument("--tol", type=float, default=0.25, help="Toleranz der Kurvenzerlegung in px")
    ap_.add_argument("--stats", help="Kennzahlen als JSON schreiben")
    a = ap_.parse_args()
    root = ET.parse(a.svg).getroot()
    c = Conv(root, a.tol).run()
    pathlib.Path(a.out).write_text(c.tscn())
    c.stats["size"] = c.size
    c.stats["warnings"] = sorted(set(c.stats["warnings"]))
    if a.stats:
        pathlib.Path(a.stats).write_text(json.dumps(c.stats, indent=1, ensure_ascii=False))
    print(f"{a.out}: {c.stats['polygons']} Polygone, {c.stats['points']} Punkte, {c.stats['groups']} Gruppen, "
          f"{c.stats['gradients']} Verläufe" + (f"; {len(c.stats['warnings'])} Hinweise" if c.stats["warnings"] else ""))
    for w in c.stats["warnings"]:
        print(f"WARNUNG: {w}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
