extends Node2D
## Rig-Ansicht (Einblendung oben links): eine zweite Instanz von badger.tscn, deren Knochen jedes Bild aus der
## Hauptfigur kopiert werden. Darüber Gewichtsfarben je Gitterpunkt, das Dreiecksgitter und die Knochen.
## Gitter und Farben werden hier auf der CPU mit denselben Gewichten verformt wie auf der GPU
## (Endlage = aktuelle Knochenlage * inverse Ruhelage, gewichtet gemittelt); dass beides deckungsgleich ist,
## prüft scripts/check_overlay.py.

const SIZE := Vector2(268, 318)
const FIG_SCALE := 0.84
const FIG_POS := Vector2(134, 268)

var src: Node2D
var fig: Node2D
var overlay: Node2D
var src_bones: Array[Bone2D] = []
var fig_bones: Array[Bone2D] = []
var skel: Skeleton2D
var meshes := []          # je Polygon2D: {poly, bones:[{node, rest_inv, w}], colors, edges, tris}
var mono: Font
var caption := ""
var mode_line := ""
var check := ""           # Prüfmodus --overlay-check=gpu|cpu (scripts/check_overlay.py)

const COLORS := {
	"hip": Color(1.0, 0.80, 0.25), "spine": Color(1.0, 0.70, 0.20), "neck": Color(1.0, 0.86, 0.35),
	"head": Color(1.0, 0.93, 0.55), "belly": Color(1.0, 0.55, 0.30), "tail": Color(0.95, 0.45, 0.35),
	"satchel": Color(0.85, 0.50, 0.30),
	"thigh_n": Color(0.30, 0.85, 1.0), "shin_n": Color(0.45, 0.65, 1.0), "foot_n": Color(0.60, 0.95, 0.95),
	"thigh_f": Color(0.30, 0.55, 0.95), "shin_f": Color(0.40, 0.45, 0.90), "foot_f": Color(0.45, 0.75, 0.85),
	"arm_n": Color(1.0, 0.45, 0.70), "fore_n": Color(0.95, 0.60, 0.90),
	"arm_f": Color(0.75, 0.45, 0.95), "fore_f": Color(0.85, 0.60, 1.0),
	"scarf_b1": Color(0.45, 0.95, 0.50), "scarf_b2": Color(0.30, 0.85, 0.60), "scarf_b3": Color(0.55, 1.0, 0.70),
	"scarf_f1": Color(0.60, 0.95, 0.35), "scarf_f2": Color(0.45, 0.85, 0.35), "scarf_f3": Color(0.75, 1.0, 0.50),
}


static func make_rigid(root: Node) -> void:
	# Vergleich "starr": jedes Dreieck gehört ganz zu dem Knochen mit dem größten Gewicht seiner drei Punkte,
	# Punkte werden je Dreieck verdoppelt. So entstehen getrennte, starre Teile wie bei einer Puppe ohne
	# überlappende Gelenke; an Knie, Hals und Schal öffnen sich Fugen oder Teile schieben sich übereinander.
	for p: Polygon2D in root.find_children("*", "Polygon2D", false, false):
		var n := p.get_bone_count()
		var ws := []
		var paths := []
		for i in n:
			ws.append(p.get_bone_weights(i))
			paths.append(p.get_bone_path(i))
		var pts := p.polygon
		var uvs := p.uv
		var npts := PackedVector2Array()
		var nuv := PackedVector2Array()
		var ntris := []
		var nw := []
		for i in n:
			nw.append(PackedFloat32Array())
		for tri in p.polygons:
			var ids: PackedInt32Array = tri
			var best := 0
			var best_s := -1.0
			for i in n:
				var sum: float = ws[i][ids[0]] + ws[i][ids[1]] + ws[i][ids[2]]
				if sum > best_s:
					best_s = sum
					best = i
			var base := npts.size()
			for k in 3:
				npts.append(pts[ids[k]])
				nuv.append(uvs[ids[k]])
				for i in n:
					nw[i].append(1.0 if i == best else 0.0)
			ntris.append(PackedInt32Array([base, base + 1, base + 2]))
		p.clear_bones()
		p.polygon = npts
		p.uv = nuv
		p.polygons = ntris
		for i in n:
			p.add_bone(paths[i], nw[i])


func setup(main_badger: Node2D, packed: PackedScene, font: Font, rigid: bool) -> void:
	src = main_badger
	mono = font
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--overlay-check="):
			check = a.substr(16)
	fig = packed.instantiate()
	fig.position = FIG_POS
	fig.scale = Vector2(FIG_SCALE, FIG_SCALE)
	add_child(fig)
	if rigid:
		make_rigid(fig)
	var wmat := ShaderMaterial.new()
	wmat.shader = preload("res://shaders/weights.gdshader")
	var ap: AnimationPlayer = fig.get_node("AnimationPlayer")
	ap.active = false
	skel = fig.get_node("Skeleton2D")
	for b in src.get_node("Skeleton2D").find_children("*", "Bone2D", true, false):
		src_bones.append(b)
		fig_bones.append(fig.get_node("Skeleton2D").get_node(src.get_node("Skeleton2D").get_path_to(b)))
	var n_tris := 0
	for p: Polygon2D in fig.find_children("*", "Polygon2D", false, false):
		var m := {"poly": p, "bones": [], "colors": PackedColorArray(), "edges": PackedInt32Array(), "tris": PackedInt32Array()}
		var nv := p.polygon.size()
		var cols := PackedColorArray()
		cols.resize(nv)
		cols.fill(Color(0, 0, 0, 0))
		for i in p.get_bone_count():
			var bn: Bone2D = skel.get_node(p.get_bone_path(i))
			var w := p.get_bone_weights(i)
			m.bones.append({"node": bn, "rest_inv": bn.get_skeleton_rest().affine_inverse(), "w": w})
			var c: Color = COLORS.get(String(bn.name), Color.WHITE)
			for v in nv:
				cols[v] += Color(c.r, c.g, c.b, 1.0) * w[v]
		for v in nv:
			var s: float = max(cols[v].a, 1e-4)
			cols[v] = Color(cols[v].r / s, cols[v].g / s, cols[v].b / s, 1.0)
		m.colors = cols
		p.vertex_colors = cols
		p.color = Color.WHITE
		p.material = wmat
		if check == "gpu":
			p.texture = grid_texture(p)
			p.material = null
			p.vertex_colors = PackedColorArray()
			p.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		elif check == "cpu":
			p.visible = false
		var seen := {}
		for tri in p.polygons:
			var ids: PackedInt32Array = tri
			m.tris.append_array(ids)
			n_tris += 1
			for k in 3:
				var a: int = min(ids[k], ids[(k + 1) % 3])
				var b: int = max(ids[k], ids[(k + 1) % 3])
				var key := a * 100000 + b
				if not seen.has(key):
					seen[key] = true
					var ua: Vector2 = p.uv[a]
					var ub: Vector2 = p.uv[b]
					# im Prüfmodus nur Rasterkanten (gleiches u oder v), keine Diagonalen
					if check == "" or is_equal_approx(ua.x, ub.x) or is_equal_approx(ua.y, ub.y):
						m.edges.append(a)
						m.edges.append(b)
		meshes.append(m)
	overlay = Node2D.new()
	overlay.name = "Overlay"
	fig.add_child(overlay)
	overlay.draw.connect(_draw_overlay)
	caption = "%d Knochen · %d Gitter · %d Dreiecke" % [fig_bones.size(), meshes.size(), n_tris]
	mode_line = "starr: Teile je Knochen getrennt" if rigid else "Gewichte: weich (bis 3 je Punkt)"


func grid_texture(p: Polygon2D) -> ImageTexture:
	# Linien genau auf den Rasterlinien des Gitters (u bzw. v = Vielfaches der Zellgröße)
	var sz := p.texture.get_size()
	var c := 1e9
	for uv in p.uv:
		if uv.x > 0.5:
			c = min(c, uv.x)
	var img := Image.create(int(sz.x), int(sz.y), false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var step := int(round(c))
	for x in range(0, int(sz.x), step):
		for y in int(sz.y):
			img.set_pixel(x, y, Color(1, 0, 0, 1))
	for y in range(0, int(sz.y), step):
		for x in int(sz.x):
			img.set_pixel(x, y, Color(1, 0, 0, 1))
	return ImageTexture.create_from_image(img)


func sync() -> void:
	for i in src_bones.size():
		fig_bones[i].transform = src_bones[i].transform
	overlay.queue_redraw()
	queue_redraw()


func skinned(m: Dictionary) -> PackedVector2Array:
	var p: Polygon2D = m.poly
	var src_pts := p.polygon
	var out := PackedVector2Array()
	out.resize(src_pts.size())
	var mats := []
	for b in m.bones:
		var cur: Transform2D = skel.global_transform.affine_inverse() * (b.node as Bone2D).global_transform
		mats.append(cur * (b.rest_inv as Transform2D))
	for v in src_pts.size():
		var acc := Vector2.ZERO
		var ws := 0.0
		for i in mats.size():
			var w: float = m.bones[i].w[v]
			if w > 0.0:
				acc += (mats[i] as Transform2D) * src_pts[v] * w
				ws += w
		out[v] = acc / ws if ws > 0.0 else src_pts[v]
	return out


func _draw_overlay() -> void:
	if check == "gpu":
		return
	for m in meshes:
		var pts := skinned(m)
		var lines := PackedVector2Array()
		for i in range(0, m.edges.size(), 2):
			lines.append(pts[m.edges[i]])
			lines.append(pts[m.edges[i + 1]])
		if check == "cpu":
			overlay.draw_multiline(lines, Color(0, 1, 0, 1), -1.0)
			continue
		overlay.draw_multiline(lines, Color(0.85, 0.92, 1.0, 0.16), 1.0 / FIG_SCALE)
	if check != "":
		return
	var inv := skel.global_transform.affine_inverse()
	for b in fig_bones:
		var cur := inv * b.global_transform
		var a := cur.origin
		var dir := Vector2.from_angle(cur.get_rotation() + b.get_bone_angle())
		var tip := a + dir * b.get_length()
		var wdt: float = clamp(b.get_length() * 0.16, 1.6, 5.0)
		var perp := Vector2(-dir.y, dir.x) * wdt
		var mid := a + dir * b.get_length() * 0.22
		var c: Color = COLORS.get(String(b.name), Color.WHITE)
		var kite := PackedVector2Array([a, mid + perp, tip, mid - perp])
		overlay.draw_colored_polygon(kite, Color(c.r, c.g, c.b, 0.85))
		kite.append(a)
		overlay.draw_polyline(kite, Color(0.05, 0.06, 0.08, 0.9), 1.0 / FIG_SCALE)
		overlay.draw_circle(a, 1.9 / FIG_SCALE, Color(0.05, 0.06, 0.08, 0.95))


func _draw() -> void:
	if check != "":
		return
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.07, 0.08, 0.11, 0.84)
	sb.border_color = Color(0.55, 0.62, 0.72, 0.55)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(10)
	draw_style_box(sb, Rect2(Vector2.ZERO, SIZE))
	draw_line(Vector2(12, 34), Vector2(SIZE.x - 12, 34), Color(0.55, 0.62, 0.72, 0.35), 1.0)
	draw_string(mono, Vector2(14, 24), "Skeleton2D + Polygon2D", HORIZONTAL_ALIGNMENT_LEFT, -1, 13, Color(0.86, 0.90, 0.96))
	draw_line(Vector2(12, SIZE.y - 44), Vector2(SIZE.x - 12, SIZE.y - 44), Color(0.55, 0.62, 0.72, 0.35), 1.0)
	draw_string(mono, Vector2(14, SIZE.y - 27), caption, HORIZONTAL_ALIGNMENT_LEFT, SIZE.x - 20, 11, Color(0.70, 0.76, 0.84))
	draw_string(mono, Vector2(14, SIZE.y - 11), mode_line, HORIZONTAL_ALIGNMENT_LEFT, SIZE.x - 20, 11, Color(1.0, 0.80, 0.45))
