extends Node2D
## Comic mit Panels und Rasterpunkten: Hafen von Lornholm als Comicseite.
## Gedruckt wird wie im Comic aus zwei Ebenen: Der Viewport "page" enthält nur Farbflächen (Kolorierung der Panels,
## Farbflächen der Effekte, Kästen und Sprechblase), der Viewport "ink" die Zeichnung (Tusche der Panels und des
## Dachses, Konturen der Effekte, Rahmen, Schrift) und Deckweiß. Ein Vollbild-Shader (print.gdshader) rastert die
## Farbflächen in C, M, Y, K und legt die Tusche in voller Auflösung darüber.
## Ablauf: Panels erscheinen nacheinander (A 0,0 s, B 1,3 s, C 2,5 s), dann die Auswahl (ab 3,9 s).
## Prüfschalter nach "--": --probe-flat (Farbflächen ungerastert), --probe-no-badger (ohne Dachs und Schatten),
## --probe-no-shadow (ohne Schatten; für die Fußmessung über Differenzbilder),
## --t0=<s> (alles um s Sekunden vorstellen, für die Langzeitprüfung).

const W := 1280
const H := 720
const FPS_WALK := 15.0
const REV_DUR := 0.4
const REV := {"A": 0.0, "B": 1.3, "C": 2.5}
const CAP_A := 0.45
const CAP_B := 1.75
const SFX_B := 2.05
const BUBBLE := 3.0
const TALK0 := 3.1
const TALK1 := 4.5
const CHOICE_T := [3.9, 4.05, 4.2]
const PARSER_T := 4.35
const TYPE_T := 4.55
const TYPE_RATE := 16.0
const BEAM_PERIOD := 6.0

const INK := Color(0.0, 0.0, 0.0)
const WHITE := Color(1.0, 1.0, 1.0)
const CAPTION := Color(1.0, 0.93, 0.48)       # Bildunterschrift: Gelb als Rasterton (etwa Y 50 %)
const SFX_YELLOW := Color(1.0, 1.0, 0.0)      # Geräuschwort: Gelb voll
const LIGHT := Color(1.0, 0.97, 0.72)

# Dachs: Laufen auf Zweien (15 Bilder/s), 8er-Zyklus, Halt aus walk_2, dann Stand und Drehung zur Kamera
const WALK_N := 54                            # Laufbilder
const WALK_START := 5                         # erstes Laufbild (so endet der Lauf auf walk_2)
const STOP_X := 340.0                         # Fußpunkt beim Halt (Panel-Koordinaten)
const GROUND_Y := 548.0
const TURN_TICK := 60                         # 4,0 s
const ANCHOR_X := 70.0

var t := 0.0
var t0 := 0.0
var rng := RandomNumberGenerator.new()
var scene: Dictionary
var bj: Dictionary
var probe_flat := false
var probe_no_badger := false
var probe_no_shadow := false

var page: SubViewport
var ink: SubViewport
var print_mat: ShaderMaterial
var panels := {}          # key -> {"c": Control (page), "i": Control (ink), "rv": [ColorRect, ColorRect]}
var borders := {}
var light_a: ShaderMaterial
var light_b: ShaderMaterial
var light_c: ShaderMaterial
var fx: Array = []        # Drawer, die jedes Bild neu zeichnen
var badger: Sprite2D
var badger_ink: Sprite2D
var shadow: Drawer
var bust: Sprite2D
var bust_ink: Sprite2D
var tex_c: Texture2D
var tex_c_talk: Texture2D
var ink_c: Texture2D
var ink_c_talk: Texture2D
var cap_a: Array
var cap_b: Array
var sfx: Array
var bubble: Array
var choices: Array = []
var parser_label: Label
var cursor: Drawer

var flicker: Array = []
var talk: Array = []
var glint_on: Array = []
var font_kalam: Font
var font_bangers: Font


class Drawer extends Node2D:
	var fn: Callable

	func _draw() -> void:
		fn.call(self)


func load_json(path: String) -> Variant:
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if data == null:
		push_error("JSON fehlt oder kaputt: " + path)
	return data


func v2(a: Array) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func drawer(parent: Node, f: Callable, animated := true) -> Drawer:
	var d := Drawer.new()
	d.fn = f
	parent.add_child(d)
	if animated:
		fx.append(d)
	return d


func make_viewport(transparent: bool) -> SubViewport:
	var v := SubViewport.new()
	v.size = Vector2i(W, H)
	v.disable_3d = true
	v.transparent_bg = transparent
	v.msaa_2d = Viewport.MSAA_4X
	v.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(v)
	return v


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe_flat = "--probe-flat" in args
	probe_no_badger = "--probe-no-badger" in args
	probe_no_shadow = "--probe-no-shadow" in args
	for a in args:
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
	rng.seed = 20261012
	for i in 400:
		flicker.append(rng.randf())
	for i in 60:
		talk.append(rng.randf())
	for i in 600:
		glint_on.append(rng.randf())
	scene = load_json("res://art/scene.json")
	bj = load_json("res://art/badger.json")
	font_kalam = load("res://fonts/Kalam-Bold.ttf")
	font_bangers = load("res://fonts/Bangers-Regular.ttf")

	page = make_viewport(false)
	ink = make_viewport(true)
	var paper := ColorRect.new()
	paper.color = WHITE
	paper.size = Vector2(W, H)
	page.add_child(paper)

	build_panel_a()
	build_panel_b()
	build_panel_c()
	build_ui()

	var pr := TextureRect.new()
	pr.size = Vector2(W, H)
	pr.texture = page.get_texture()
	print_mat = ShaderMaterial.new()
	print_mat.shader = load("res://shaders/print.gdshader")
	print_mat.set_shader_parameter("page_tex", page.get_texture())
	print_mat.set_shader_parameter("ink_tex", ink.get_texture())
	print_mat.set_shader_parameter("probe", 1 if probe_flat else 0)
	pr.material = print_mat
	add_child(pr)
	t = t0
	step()


# ---------------------------------------------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------------------------------------------
func make_panel(key: String) -> Dictionary:
	var p: Dictionary = scene["panels"][key]
	var d := {}
	for layer in ["c", "i"]:
		var c := Control.new()
		c.position = v2(p["pos"])
		c.size = v2(p["size"])
		c.clip_contents = true
		(page if layer == "c" else ink).add_child(c)
		d[layer] = c
	panels[key] = d
	return d


func finish_panel(key: String) -> void:
	var d: Dictionary = panels[key]
	var rvs: Array = []
	for layer in ["c", "i"]:
		var c: Control = d[layer]
		var rv := ColorRect.new()
		rv.size = c.size
		var m := ShaderMaterial.new()
		m.shader = load("res://shaders/reveal.gdshader")
		m.set_shader_parameter("rect_size", c.size)
		rv.material = m
		c.add_child(rv)
		rvs.append(rv)
	d["rv"] = rvs
	var sz: Vector2 = d["c"].size
	var b := drawer(ink, func(n: Node2D) -> void:
		n.draw_rect(Rect2(Vector2(2, 2), sz - Vector2(4, 4)), INK, false, 4.0), false)
	b.position = d["c"].position
	borders[key] = b


func sprite_pair(key: String, color_tex: Texture2D, ink_tex: Texture2D) -> Array:
	var out: Array = []
	for layer in ["c", "i"]:
		var s := Sprite2D.new()
		s.centered = false
		s.texture = color_tex if layer == "c" else ink_tex
		panels[key][layer].add_child(s)
		out.append(s)
	return out


func light_material(tex_size: Vector2) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/light.gdshader")
	m.set_shader_parameter("tex_size", tex_size)
	return m


func build_panel_a() -> void:
	make_panel("A")
	var bg := sprite_pair("A", load("res://art/panel_a.png"), load("res://art/panel_a_ink.png"))
	light_a = light_material(bg[0].texture.get_size())
	bg[0].material = light_a
	drawer(panels["A"]["c"], draw_fx_a_color)
	drawer(panels["A"]["i"], draw_fx_a_ink)
	shadow = drawer(panels["A"]["c"], func(n: Node2D) -> void:
		n.draw_set_transform(Vector2.ZERO, 0.0, Vector2(1.0, 0.22))
		n.draw_circle(Vector2.ZERO, 46.0, Color(0.30, 0.29, 0.40)), false)
	shadow.visible = not probe_no_badger and not probe_no_shadow
	var bd := sprite_pair("A", load("res://art/badger.png"), load("res://art/badger_ink.png"))
	badger = bd[0]
	badger_ink = bd[1]
	for s in bd:
		s.hframes = bj["frames"].size()
		s.offset = Vector2(-ANCHOR_X, -float(bj["foot_y"]))
		s.visible = not probe_no_badger
	cap_a = make_caption("A", Vector2(12, 12), "HAFEN VON LORNHOLM", font_bangers, 30, Vector2(14, 3))
	finish_panel("A")


func build_panel_b() -> void:
	make_panel("B")
	var bg := sprite_pair("B", load("res://art/panel_b.png"), load("res://art/panel_b_ink.png"))
	light_b = light_material(bg[0].texture.get_size())
	bg[0].material = light_b
	drawer(panels["B"]["i"], draw_fx_b_ink)
	cap_b = make_caption("B", Vector2(0, 0), "DIE LATERNE\nFLACKERT\nIM WIND.", font_kalam, 19, Vector2(12, 5))
	# Geräuschwort (Inflektiv wie im deutschen Comic): gelbe Füllung in der Seite, Kontur in der Tusche
	sfx = []
	for layer in ["c", "i"]:
		var n := Node2D.new()
		n.rotation = deg_to_rad(-9.0)
		var l := Label.new()
		l.text = "FLACKER!"
		var ls := LabelSettings.new()
		ls.font = font_bangers
		ls.font_size = 44
		if layer == "c":
			ls.font_color = SFX_YELLOW
		else:
			# Kontur schwarz; die Buchstaben selbst in reinem Gelb: in der Tusche-Ebene weder Schwarz noch
			# Deckweiß (Alpha minus Helligkeit = 0, kleinster Kanal = 0), dort scheint die gelbe Füllung durch.
			ls.font_color = Color(1, 1, 0)
			ls.outline_size = 6
			ls.outline_color = INK
		l.label_settings = ls
		var sz := l.get_minimum_size()
		l.position = -sz * 0.5
		n.add_child(l)
		panels["B"][layer].add_child(n)
		sfx.append(n)
	finish_panel("B")


func build_panel_c() -> void:
	make_panel("C")
	tex_c = load("res://art/panel_c.png")
	tex_c_talk = load("res://art/panel_c_talk.png")
	ink_c = load("res://art/panel_c_ink.png")
	ink_c_talk = load("res://art/panel_c_talk_ink.png")
	var bs := sprite_pair("C", tex_c, ink_c)
	bust = bs[0]
	bust_ink = bs[1]
	light_c = light_material(tex_c.get_size())
	bust.material = light_c
	bubble = [drawer(panels["C"]["c"], draw_bubble_fill), drawer(panels["C"]["i"], draw_bubble_ink)]
	var l := Label.new()
	l.text = "AM KAI WARTET\nEIN PAKET\nAUF DICH."
	var ls := LabelSettings.new()
	ls.font = font_kalam
	ls.font_size = 17
	ls.font_color = INK
	ls.line_spacing = -5.0
	l.label_settings = ls
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.size = Vector2(160, 84)
	l.position = Vector2(-80, -43)
	bubble[1].add_child(l)
	finish_panel("C")


func make_caption(key: String, pos: Vector2, text: String, font: Font, size: int, pad: Vector2) -> Array:
	var l := Label.new()
	l.text = text
	var ls := LabelSettings.new()
	ls.font = font
	ls.font_size = size
	ls.font_color = INK
	ls.line_spacing = -4.0
	l.label_settings = ls
	var tsz := font.get_multiline_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1, size)
	tsz.y = l.get_minimum_size().y
	var box := (tsz + pad * 2.0).ceil()
	var fill := drawer(panels[key]["c"], func(d: Node2D) -> void:
		d.draw_rect(Rect2(-box * 0.5, box), CAPTION, true), false)
	var line := drawer(panels[key]["i"], func(d: Node2D) -> void:
		# Fläche in reinem Gelb: deckt die Tusche des Panels ab, ohne selbst Tusche zu sein (Füllung kommt aus der Seite)
		d.draw_rect(Rect2(-box * 0.5, box), Color(1, 1, 0), true)
		d.draw_rect(Rect2(-box * 0.5, box).grow(-1.5), INK, false, 3.0), false)
	l.position = -box * 0.5 + pad
	line.add_child(l)
	fill.position = pos + box * 0.5
	line.position = fill.position
	return [fill, line]


func build_ui() -> void:
	var texts: Array = ["ZUM LEUCHTTURM GEHEN", "DAS PAKET ANSEHEN", "MIT DEM DACHS SPRECHEN"]
	var x := 16.0
	var y := 657.0
	var hgt := 52.0
	for i in 4:
		var l := Label.new()
		l.text = texts[i] if i < 3 else "> NIMM PAKET"
		var ls := LabelSettings.new()
		ls.font = font_kalam
		ls.font_size = 21
		ls.font_color = INK
		l.label_settings = ls
		var tsz := l.get_minimum_size()
		var w := tsz.x + 74.0 if i < 3 else 1264.0 - x
		var fillc := CAPTION if i < 3 else WHITE
		var fill := drawer(page, func(d: Node2D) -> void:
			d.draw_rect(Rect2(-w * 0.5, -hgt * 0.5, w, hgt), fillc, true), false)
		var has_num := i < 3
		var line := drawer(ink, func(d: Node2D) -> void:
			d.draw_rect(Rect2(-w * 0.5, -hgt * 0.5, w, hgt).grow(-1.5), INK, false, 3.0)
			if has_num:
				d.draw_circle(Vector2(-w * 0.5 + 30.0, 0), 16.0, INK), false)
		fill.position = Vector2(x + w * 0.5, y)
		line.position = fill.position
		var lx := 56.0 if i < 3 else 16.0
		l.position = Vector2(-w * 0.5 + lx, -tsz.y * 0.5 + 1.0)
		line.add_child(l)
		if i < 3:
			var num := Label.new()
			num.text = str(i + 1)
			var ns := LabelSettings.new()
			ns.font = font_bangers
			ns.font_size = 26
			ns.font_color = WHITE            # Deckweiß in der schwarzen Scheibe
			num.label_settings = ns
			var nsz := num.get_minimum_size()
			num.position = Vector2(-w * 0.5 + 30.0 - nsz.x * 0.5, -nsz.y * 0.5 + 1.0)
			line.add_child(num)
		else:
			parser_label = l
			l.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
			cursor = drawer(line, func(d: Node2D) -> void:
				d.draw_rect(Rect2(0, -12, 10, 24), INK, true), false)
		choices.append([fill, line])
		x += w + 14.0


# ---------------------------------------------------------------------------------------------------------------
# Zeichnen
# ---------------------------------------------------------------------------------------------------------------
func pop_scale(dt: float) -> float:
	# Comic-Aufpoppen in Bildern zu 30/s: 0,55 → 0,85 → 1,10 → 1,04 → 0,97 → 1
	if dt < 0.0:
		return 0.0
	var k := int(dt * 30.0 + 0.001)
	var seq := [0.55, 0.85, 1.1, 1.04, 0.97, 1.0]
	return seq[k] if k < seq.size() else 1.0


func set_pair(pair: Array, pos: Vector2, s: float, vis: bool) -> void:
	for n in pair:
		n.position = pos
		n.scale = Vector2.ONE * maxf(s, 0.001)
		n.visible = vis


func smoke_puffs() -> Array:
	var ch := v2(scene["A"]["chimney"])
	var puffs: Array = []
	var period := 0.45
	var life := 3.2
	var first := int(floor((t - life) / period))
	for i in range(first, int(floor(t / period)) + 1):
		var age := t - i * period
		if age < 0.0 or age > life:
			continue
		var u := age / life
		var wob := sin(i * 1.7 + age * 2.2) * 3.0
		puffs.append([ch + Vector2(age * 15.0 + wob, -age * 17.0 - 4.0), 5.0 + 11.0 * u])
	return puffs


func beam_shape() -> Dictionary:
	var lamp := v2(scene["A"]["lamp"])
	var th := TAU * t / BEAM_PERIOD
	var cs := cos(th)
	var sn := sin(th)
	var length := 360.0 * absf(cs)
	var dir := 1.0 if cs > 0.0 else -1.0
	var half := 9.0 + 0.10 * length
	var tip := lamp + Vector2(dir * length, 0)
	var pts := PackedVector2Array([lamp + Vector2(0, -4), tip + Vector2(0, -half), tip + Vector2(0, half), lamp + Vector2(0, 4)])
	var flash := 0.0
	if sn > 0.0:
		flash = clampf(1.0 - absf(cs) / 0.22, 0.0, 1.0)
	return {"pts": pts, "on": length > 12.0, "front": sn > 0.0, "flash": flash, "lamp": lamp}


func gulls() -> Array:
	var tick10 := int(floor(t * 10.0))
	var flaps := [1.0, 0.35, -0.45, 0.35]
	var out: Array = []
	var gl := [[fposmod(-40.0 + t * 46.0, 900.0) - 40.0, 128.0, 1.0, 0], [fposmod(640.0 - t * 32.0, 900.0) - 40.0, 58.0, 0.8, 2]]
	for g in gl:
		var gp := Vector2(g[0], g[1] + sin(t * 1.3 + g[3]) * 4.0)
		var s: float = g[2]
		var fl: float = flaps[(tick10 + int(g[3])) % 4]
		out.append([PackedVector2Array([gp + Vector2(-13, -6.0 * fl) * s, gp + Vector2(-6, -1.0 - 4.0 * fl) * s, gp,
			gp + Vector2(6, -1.0 - 4.0 * fl) * s, gp + Vector2(13, -6.0 * fl) * s]), s])
	return out


func draw_fx_a_color(n: Node2D) -> void:
	var b := beam_shape()
	if b["on"]:
		n.draw_colored_polygon(b["pts"], LIGHT if b["front"] else Color(0.96, 0.9, 0.78))
	if b["flash"] > 0.0:
		n.draw_circle(b["lamp"], 9.0 + 9.0 * b["flash"], LIGHT)


func draw_fx_a_ink(n: Node2D) -> void:
	# Rauch: weiße Wölkchen mit gemeinsamer Außenkontur (erst alle schwarzen Scheiben, dann alle Deckweiß-Scheiben)
	var puffs := smoke_puffs()
	for pf in puffs:
		n.draw_circle(pf[0], pf[1] + 2.5, INK)
	for pf in puffs:
		n.draw_circle(pf[0], pf[1], WHITE)
	var b := beam_shape()
	if b["on"]:
		var pts: PackedVector2Array = b["pts"]
		n.draw_line(pts[0], pts[1], INK, 2.0, true)
		n.draw_line(pts[3], pts[2], INK, 2.0, true)
	if b["flash"] > 0.0:
		var f: float = b["flash"]
		for k in 8:
			var a := TAU * k / 8.0 + 0.2
			var d := Vector2(cos(a), sin(a))
			n.draw_line(b["lamp"] + d * (14.0 + 4.0 * f), b["lamp"] + d * (22.0 + 14.0 * f), INK, 2.0, true)
	for g in gulls():
		n.draw_polyline(g[0], INK, 3.0 * g[1], true)
	# Glitzern: Deckweiß-Striche auf offenem Wasser, wechseln 6-mal pro Sekunde
	var tick6 := int(floor(t * 6.0))
	var gl: Array = scene["A"]["glints"]
	for i in gl.size():
		var on: float = glint_on[(i * 7 + tick6 * 13) % glint_on.size()]
		if on < 0.45:
			continue
		var p := v2(gl[i])
		var w := 6.0 + 9.0 * on
		n.draw_rect(Rect2(p - Vector2(w * 0.5, 1.0), Vector2(w, 2.0)), WHITE, true)


func draw_fx_b_ink(n: Node2D) -> void:
	# Leuchtstriche um die Laterne (Comic-Kürzel für Licht), Länge wechselt 10-mal pro Sekunde
	var B: Dictionary = scene["B"]
	var c := v2(B["glass"])
	var tick10 := int(floor(t * 10.0))
	var r0 := float(B["glass_r"]) + 12.0
	for k in 12:
		var a := deg_to_rad(-180.0 + k * 30.0 + 15.0)
		if absf(sin(a)) > 0.8:
			continue                       # oben Kette und Dach, unten Boden der Laterne
		var f: float = flicker[(tick10 * 12 + k) % flicker.size()]
		if f < 0.2:
			continue
		var d := Vector2(cos(a), sin(a))
		n.draw_line(c + d * (r0 + 4.0 * f), c + d * (r0 + 14.0 + 22.0 * f), INK, 3.5, true)


func bubble_points(n: Node2D) -> PackedVector2Array:
	var rx := 90.0
	var ry := 50.0
	var mouth := (mouth_pos() - n.position) / n.scale.x
	var pts := PackedVector2Array()
	var steps := 48
	var a_tail := atan2(mouth.y / ry, mouth.x / rx)
	var gap := 0.22
	for i in steps:
		var a := a_tail + gap + (TAU - 2.0 * gap) * i / float(steps - 1)
		pts.append(Vector2(cos(a) * rx, sin(a) * ry))
	pts.append(mouth.normalized() * (mouth.length() - 16.0))
	return pts


func draw_bubble_fill(n: Node2D) -> void:
	n.draw_colored_polygon(bubble_points(n), WHITE)


func draw_bubble_ink(n: Node2D) -> void:
	var pts := bubble_points(n)
	n.draw_colored_polygon(pts, WHITE)          # Deckweiß: keine Tusche des Panels in der Blase
	pts.append(pts[0])
	n.draw_polyline(pts, INK, 3.0, true)


func mouth_pos() -> Vector2:
	var C: Dictionary = scene["C"]
	var zc := v2(C["zoom_center"])
	return zc + (v2(C["mouth"]) - zc) * zoom_c()


func zoom_c() -> float:
	var u := clampf((t - REV["C"]) / (6.0 - REV["C"]), 0.0, 1.0)
	return 1.006 + 0.044 * (u * u * (3.0 - 2.0 * u))


# ---------------------------------------------------------------------------------------------------------------
# Ablauf
# ---------------------------------------------------------------------------------------------------------------
func _process(delta: float) -> void:
	t += delta
	step()


func step() -> void:
	# Panels erscheinen
	for key in ["A", "B", "C"]:
		var start: float = REV[key]
		var d: Dictionary = panels[key]
		var p := clampf((t - start) / REV_DUR, 0.0, 1.0)
		for layer in ["c", "i"]:
			d[layer].visible = t >= start
		for rv in d["rv"]:
			rv.visible = p < 1.0
			(rv.material as ShaderMaterial).set_shader_parameter("progress", p)
		borders[key].visible = t >= start

	var tick10 := int(floor(t * 10.0))
	var fl: float = flicker[tick10 % flicker.size()]
	var fl2: float = flicker[(tick10 + 37) % flicker.size()]
	var A: Dictionary = scene["A"]
	var B: Dictionary = scene["B"]
	var C: Dictionary = scene["C"]
	# Licht: Laterne flackert, Fenster, Leuchtfeuer blitzt mit dem Strahl
	var flash: float = beam_shape()["flash"]
	var la := v2(A["lantern"])
	var wa := v2(A["window"])
	var lp := v2(A["lamp"])
	light_a.set_shader_parameter("lights", [Vector4(la.x, la.y, 50.0 + 14.0 * fl, 0.6 + 0.4 * fl),
		Vector4(wa.x, wa.y, 46.0, 0.45 + 0.05 * fl2), Vector4(lp.x, lp.y, 26.0 + 30.0 * flash, 0.5 + 0.5 * flash),
		Vector4(0, 0, 0, 0)])
	light_a.set_shader_parameter("light_col", [Vector3(1.0, 0.95, 0.65), Vector3(1.0, 0.92, 0.6),
		Vector3(1.0, 0.98, 0.8), Vector3(1, 1, 1)])
	var gb := v2(B["glass"])
	var wb := v2(B["window"])
	light_b.set_shader_parameter("lights", [Vector4(gb.x, gb.y, 125.0 + 45.0 * fl, 0.6 + 0.4 * fl),
		Vector4(wb.x, wb.y, 70.0, 0.4 + 0.08 * fl2), Vector4(0, 0, 0, 0), Vector4(0, 0, 0, 0)])
	light_b.set_shader_parameter("light_col", [Vector3(1.0, 0.96, 0.62), Vector3(1.0, 0.92, 0.6),
		Vector3(1, 1, 1), Vector3(1, 1, 1)])
	var tex_k := float(C["zoom"])
	var lc := (v2(C["lamp"]) + Vector2(float(C["crop_x_at_zoom1"]), 0)) * tex_k
	light_c.set_shader_parameter("lights", [Vector4(lc.x, lc.y, 20.0 + 26.0 * flash, 0.45 + 0.55 * flash),
		Vector4(0, 0, 0, 0), Vector4(0, 0, 0, 0), Vector4(0, 0, 0, 0)])
	light_c.set_shader_parameter("light_col", [Vector3(1.0, 0.98, 0.8), Vector3(1, 1, 1), Vector3(1, 1, 1), Vector3(1, 1, 1)])

	# Dachs
	var wt := int(floor((t + 0.0001) * FPS_WALK))
	var step_px := float(bj["walk_step_px"])
	var stop_adv := float(bj["walk2_to_stand_px"])
	var x_start := STOP_X - (WALK_N - 1) * step_px - stop_adv
	var frame := 0
	var x := STOP_X
	if wt < WALK_N:
		frame = (WALK_START + wt) % 8
		x = x_start + wt * step_px
	else:
		frame = 8 if wt < TURN_TICK else 9
	for s in [badger, badger_ink]:
		s.frame = frame
		s.position = Vector2(round(x), GROUND_Y)
	shadow.position = Vector2(round(x) + 6.0, GROUND_Y - 1.0)

	# Panel C: Kamerafahrt aufs Gesicht, Mundbild beim Sprechen (auf Dreien)
	var k := zoom_c()
	var zc := v2(C["zoom_center"])
	var cxo := float(C["crop_x_at_zoom1"])
	var talking := false
	if t >= TALK0 and t < TALK1:
		var ti := int(floor((t - TALK0) * 10.0))
		talking = talk[ti % talk.size()] < 0.58 and ti % 4 != 3
	for s in [bust, bust_ink]:
		s.scale = Vector2.ONE * (k / tex_k)
		s.position = zc * (1.0 - k) - Vector2(cxo, 0) * k
	bust.texture = tex_c_talk if talking else tex_c
	bust_ink.texture = ink_c_talk if talking else ink_c

	# Kästen, Geräuschwort, Blase, Auswahl
	set_pair(cap_a, cap_a[0].position, pop_scale(t - CAP_A), t >= CAP_A)
	set_pair(cap_b, cap_b[0].position, pop_scale(t - CAP_B), t >= CAP_B)
	var jit := Vector2(float(tick10 % 2), float((tick10 / 2) % 2)) if t >= SFX_B + 0.3 else Vector2.ZERO
	set_pair(sfx, Vector2(300, 240) + jit, pop_scale(t - SFX_B), t >= SFX_B)
	set_pair(bubble, Vector2(94, 53), pop_scale(t - BUBBLE), t >= BUBBLE)
	for i in choices.size():
		var start: float = CHOICE_T[i] if i < 3 else PARSER_T
		set_pair(choices[i], choices[i][0].position, pop_scale(t - start), t >= start)
	var nchar := int(floor(maxf(0.0, t - TYPE_T) * TYPE_RATE))
	parser_label.visible_characters = mini(nchar, parser_label.text.length())
	var shown := parser_label.text.substr(0, parser_label.visible_characters)
	var tw := font_kalam.get_string_size(shown, HORIZONTAL_ALIGNMENT_LEFT, -1, 21).x
	cursor.position = parser_label.position + Vector2(tw + 4.0, 16.0)
	cursor.visible = t >= TYPE_T - 0.2 and (int(floor(t * 2.5)) % 2 == 0 or nchar < parser_label.text.length())

	for d in fx:
		d.queue_redraw()
	for d in bubble:
		d.queue_redraw()
