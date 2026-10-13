extends Node2D
## Lichter: Laterne und Fenster flackern nach Rauschfunktionen (die Laterne zusätzlich mit den Böen,
## die auch den Schal bewegen), Leuchtfeuer mit zwei Keilen, die sich um die senkrechte Achse drehen.

const Util := preload("res://scripts/util.gd")

var scene: Dictionary
var glow_tex: Texture2D
var add_mat: CanvasItemMaterial
var lantern: Sprite2D
var lantern_core: Sprite2D
var pool: Sprite2D
var win: Sprite2D
var halo: Sprite2D
var beams: Array[Polygon2D] = []
var lantern_k := 1.0
var front := true


func v2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _glow() -> Texture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.25, 0.6, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.55), Color(1, 1, 1, 0.14), Color(1, 1, 1, 0)])
	var t := GradientTexture2D.new()
	t.gradient = g
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	t.width = 128
	t.height = 128
	return t


func _spr(pos: Vector2, sc: Vector2, col: Color) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = glow_tex
	s.material = add_mat
	s.position = pos
	s.scale = sc
	s.modulate = col
	add_child(s)
	return s


## part = "back" (Leuchtfeuer hinter Möwen und Booten) oder "front" (Laterne, Fenster, Lichtfleck)
func setup(sc: Dictionary, part: String) -> void:
	scene = sc
	front = part == "front"
	glow_tex = _glow()
	add_mat = CanvasItemMaterial.new()
	add_mat.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	if front:
		var lp := v2(scene["lantern"])
		var pb := v2(scene["lantern_post_base"])
		pool = _spr(pb + Vector2(-6, 42), Vector2(2.4, 0.42), Color(1.0, 0.66, 0.34, 0.25))
		lantern = _spr(lp, Vector2(1.5, 1.5), Color(1.0, 0.68, 0.36, 0.5))
		lantern_core = _spr(lp + Vector2(0, 2), Vector2(0.28, 0.36), Color(1.0, 0.86, 0.6, 0.65))
		var wp := v2(scene["window"])
		win = _spr(wp, Vector2(0.95, 1.3), Color(1.0, 0.72, 0.4, 0.22))
	else:
		var lamp := v2(scene["lighthouse_lamp"])
		for k in 2:
			var p := Polygon2D.new()
			p.material = add_mat
			p.antialiased = true
			add_child(p)
			beams.append(p)
		halo = _spr(lamp, Vector2(0.6, 0.6), Color(1.0, 0.9, 0.7, 0.4))


func update(t: float) -> void:
	if front:
		var gust := maxf(0.0, Util.fbm(t * 0.55, 11))
		lantern_k = clampf(0.78 + 0.16 * Util.fbm(t * 2.3, 3) + 0.10 * Util.fbm(t * 9.0, 5) - 0.30 * gust * (0.5 + 0.5 * Util.vnoise(t * 7.0, 9)), 0.35, 1.0)
		lantern.modulate.a = 0.75 * lantern_k
		lantern.scale = Vector2.ONE * (1.25 + 0.35 * lantern_k)
		lantern_core.modulate.a = 0.95 * lantern_k
		pool.modulate.a = 0.42 * lantern_k
		var wk := 0.85 + 0.15 * Util.fbm(t * 1.3, 41)
		win.modulate.a = 0.24 * wk
	else:
		var lamp := v2(scene["lighthouse_lamp"])
		var phi := TAU * t / 6.5 + 1.1
		var flash := 0.0
		for k in 2:
			var a := phi + PI * k
			var sx := sin(a)
			var toward := -cos(a)      # > 0: Strahl zeigt zur Kamera
			var L := 360.0 * absf(sx)
			var w_far := 14.0 + 46.0 * maxf(toward, 0.0)
			var tip := lamp + Vector2(L * signf(sx), 5.0 * absf(sx))
			var dirn := Vector2(0, 1)
			var al := 0.20 + 0.18 * maxf(toward, 0.0)
			beams[k].visible = absf(sx) > 0.06
			beams[k].polygon = PackedVector2Array([lamp + Vector2(0, -3), tip - dirn * w_far, tip + dirn * w_far * 0.7, lamp + Vector2(0, 3)])
			beams[k].vertex_colors = PackedColorArray([Color(1, 0.93, 0.75, al), Color(1, 0.93, 0.75, 0), Color(1, 0.93, 0.75, 0), Color(1, 0.93, 0.75, al)])
			flash = maxf(flash, pow(maxf(toward, 0.0), 6.0))
		halo.scale = Vector2.ONE * (0.45 + 0.75 * flash)
		halo.modulate.a = 0.30 + 0.35 * flash
