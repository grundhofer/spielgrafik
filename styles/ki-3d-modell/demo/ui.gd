extends Control
## Oberfläche der Technik-Demo:
##   - oben links das Fenster „KI-Bild → 3D“: ein großer Drehteller mit dem KI-Dachs (spielt Idle) samt
##     Eingabebild, darunter drei kleine Drehteller mit Fass, Laterne und Boot. Jeder Drehteller ist ein
##     SubViewport mit eigener Welt, Licht und Kamera; die Modelle drehen sich mit 60°/s, also einmal ganz
##     herum in 6 s (auch die geratene Rückseite ist zu sehen).
##   - unten rechts der Dialogkasten mit ui_text aus data/motif.json (Ort, Zeile, Auswahl, Parser).
## Zeit kommt je Bild aus main.gd (set_time), aus aufsummiertem delta.

const BG := Color(0.06, 0.07, 0.095, 0.84)
const TILE := Color(0.13, 0.145, 0.18, 0.92)
const EDGE := Color(0.95, 0.80, 0.55, 0.28)
const TEXT := Color(0.95, 0.94, 0.91)
const DIM := Color(0.66, 0.68, 0.72)
const ACCENT := Color(1.0, 0.76, 0.42)

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const PANEL := Rect2(18, 18, 330, 434)
const BIG := Rect2(30, 62, 306, 238)
const SMALL := [Rect2(30, 334, 98, 92), Rect2(134, 334, 98, 92), Rect2(238, 334, 98, 92)]
const BOX := Rect2(724, 566, 538, 136)
const SPIN := 60.0               # Grad je Sekunde
const BIG_OFFSET := 46.0         # Startwinkel: um 4,4 s (Poster) zeigt der Dachs seine Dreiviertel-Vorderseite
const BOX_T := 0.15
const TYPE_T := 0.4
const TYPE_RATE := 40.0
const CHOICE_T := 2.2
const PARSER_T := 3.2

var t := 0.0
var tiles: Array[Dictionary] = []
var body: FontVariation
var bold: FontVariation
var mono: Font
var mono_b: Font
var overlay: Control
var thumb: Texture2D


func _ready() -> void:
	var ts := TextServerManager.get_primary_interface()
	var src := load("res://fonts/SourceSans3.ttf") as FontFile
	body = FontVariation.new()
	body.base_font = src
	body.variation_opentype = {ts.name_to_tag("wght"): 500}
	bold = FontVariation.new()
	bold.base_font = src
	bold.variation_opentype = {ts.name_to_tag("wght"): 700}
	mono = load("res://fonts/IBMPlexMono-Regular.ttf") as Font
	mono_b = load("res://fonts/IBMPlexMono-SemiBold.ttf") as Font
	thumb = load("res://art/in_badger.png") as Texture2D

	tiles.append(_make_tile(BIG, load("res://models/badger_tsr.glb"), 8.0, BIG_OFFSET, true))
	var props := ["res://models/barrel_tsr.glb", "res://models/lantern_tsr.glb", "res://models/boat_tsr.glb"]
	var offs := [30.0, 26.0, 40.0]
	for i in 3:
		tiles.append(_make_tile(SMALL[i], load(props[i]), 18.0, offs[i], false))
	overlay = Control.new()
	overlay.size = size
	overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(overlay)
	overlay.draw.connect(_draw_overlay)


func set_time(time_s: float) -> void:
	t = time_s
	for tl in tiles:
		(tl.pivot as Node3D).rotation.y = deg_to_rad(tl.offset + SPIN * t)
	queue_redraw()
	overlay.queue_redraw()


## Ein Drehteller: SubViewport mit eigener Welt; Kamera so weit weg, dass das Modell in jeder Drehung passt.
func _make_tile(rect: Rect2, scene: PackedScene, elev: float, offset: float, idle: bool) -> Dictionary:
	var cont := SubViewportContainer.new()
	cont.position = rect.position
	cont.size = rect.size
	cont.stretch = true
	cont.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(cont)
	var vp := SubViewport.new()
	vp.size = Vector2i(rect.size)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_4X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	cont.add_child(vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.62, 0.64, 0.70)
	env.ambient_light_energy = 0.75
	env.tonemap_mode = Environment.TONE_MAPPER_AGX
	var we := WorldEnvironment.new()
	we.environment = env
	vp.add_child(we)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-38.0, -32.0, 0.0)
	key.light_color = Color(1.0, 0.93, 0.84)
	key.light_energy = 1.25
	vp.add_child(key)
	var fill := DirectionalLight3D.new()
	fill.rotation_degrees = Vector3(-12.0, 145.0, 0.0)
	fill.light_color = Color(0.70, 0.80, 1.0)
	fill.light_energy = 0.55
	vp.add_child(fill)

	var pivot := Node3D.new()
	vp.add_child(pivot)
	var model := scene.instantiate() as Node3D
	pivot.add_child(model)
	if idle:
		var ap := model.get_node("AnimationPlayer") as AnimationPlayer
		ap.get_animation("Idle").loop_mode = Animation.LOOP_LINEAR
		ap.play("Idle")
	# Größe aus den Eckpunkten (Ruhepose): Höhe und größter Abstand von der Drehachse
	var lo := Vector3(INF, INF, INF)
	var hi := -lo
	var pts: Array[Vector3] = []
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		var xf := model.global_transform.affine_inverse() * mi.global_transform
		for v: Vector3 in mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_VERTEX]:
			var p := xf * v
			pts.append(p)
			lo = lo.min(p)
			hi = hi.max(p)
	var ctr := (lo + hi) * 0.5
	model.position = Vector3(-ctr.x, -lo.y, -ctr.z)
	var r := 0.0
	for p in pts:
		r = maxf(r, Vector2(p.x - ctr.x, p.z - ctr.z).length())
	var h := hi.y - lo.y
	var disc := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = r * 1.06
	cyl.bottom_radius = r * 1.06
	cyl.height = 0.025 * h
	cyl.radial_segments = 48
	disc.mesh = cyl
	var dm := StandardMaterial3D.new()
	dm.albedo_color = Color(0.22, 0.23, 0.26)
	dm.roughness = 0.7
	disc.material_override = dm
	disc.position.y = -0.0125 * h
	vp.add_child(disc)

	var cam := Camera3D.new()
	cam.fov = 26.0
	var aspect := rect.size.x / rect.size.y
	var th := tan(deg_to_rad(cam.fov * 0.5))
	var dist := maxf(h * 0.60 / th, r * 1.18 / (th * aspect)) + r
	var e := deg_to_rad(elev)
	var target := Vector3(0.0, h * 0.47, 0.0)
	cam.position = target + Vector3(0.0, sin(e), cos(e)) * dist
	vp.add_child(cam)
	cam.look_at(target)
	cam.current = true
	var tris := 0
	for mi: MeshInstance3D in model.find_children("*", "MeshInstance3D", true, false):
		tris += (mi.mesh.surface_get_arrays(0)[Mesh.ARRAY_INDEX] as PackedInt32Array).size() / 3
	return {"pivot": pivot, "offset": offset, "tris": tris, "rect": rect}


func _draw() -> void:
	# Hintergründe (die Drehteller liegen darüber, Beschriftung im Overlay)
	_panel(PANEL, BG, 10)
	_panel(BIG, TILE, 6)
	for r: Rect2 in SMALL:
		_panel(r, TILE, 6)


func _draw_overlay() -> void:
	var ov := overlay
	# Kopf des Fensters
	ov.draw_string(bold, Vector2(PANEL.position.x + 14, PANEL.position.y + 26), "KI-Bild → 3D-Modell",
		HORIZONTAL_ALIGNMENT_LEFT, -1, 19, TEXT)
	ov.draw_string(mono, Vector2(PANEL.position.x + 14, PANEL.position.y + 42),
		"TripoSR lokal · Blender · Godot", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, DIM)
	# Eingabebild in der Ecke des großen Drehtellers
	var tr := Rect2(BIG.position + Vector2(8, 8), Vector2(62, 62))
	_panel(tr.grow(3), Color(0.92, 0.90, 0.86, 0.95), 4, ov)
	ov.draw_texture_rect(thumb, tr, false)
	ov.draw_string(mono, Vector2(tr.position.x, tr.end.y + 15), "KI-Bild", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, DIM)
	ov.draw_string(mono, Vector2(BIG.position.x + 2, BIG.end.y + 17),
		"Dachs  %s Dreiecke · Rig: shared/3d" % _num(tiles[0].tris), HORIZONTAL_ALIGNMENT_LEFT, -1, 11, TEXT)
	var names := ["Fass", "Laterne", "Boot"]
	for i in 3:
		var r: Rect2 = SMALL[i]
		ov.draw_string(mono, Vector2(r.position.x + 2, r.end.y + 15), "%s %s" % [names[i], _num(tiles[i + 1].tris)],
			HORIZONTAL_ALIGNMENT_LEFT, -1, 11, TEXT)
	_draw_box(ov)


func _draw_box(ov: Control) -> void:
	var a := smoothstep(BOX_T, BOX_T + 0.35, t)
	if a <= 0.0:
		return
	var r := BOX
	_panel(r, Color(BG, BG.a * a), 10, ov)
	var x := r.position.x + 20
	var y := r.position.y + 28
	ov.draw_string(bold, Vector2(x, y), LOCATION.to_upper(), HORIZONTAL_ALIGNMENT_LEFT, -1, 14,
		Color(ACCENT, a))
	var n := clampi(int((t - TYPE_T) * TYPE_RATE), 0, LINE.length())
	ov.draw_string(body, Vector2(x, y + 27), LINE.substr(0, n), HORIZONTAL_ALIGNMENT_LEFT, r.size.x - 40, 19,
		Color(TEXT, a))
	var ca := smoothstep(CHOICE_T, CHOICE_T + 0.4, t)
	for i in 3:
		var cy := y + 56 + i * 22
		var col := Color(ACCENT if i == 0 else TEXT, ca)
		ov.draw_string(bold, Vector2(x, cy), "%d" % (i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(ACCENT, ca))
		ov.draw_string(body, Vector2(x + 18, cy), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 17, col)
	var pa := smoothstep(PARSER_T, PARSER_T + 0.3, t)
	if pa > 0.0:
		var px := r.end.x - 170
		var py := y + 100
		var shown := clampi(int((t - PARSER_T - 0.3) * 14.0) + 2, 2, PARSER.length())
		var s := PARSER.substr(0, shown)
		ov.draw_string(mono_b, Vector2(px, py), s, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(ACCENT, pa))
		if fmod(t, 0.8) < 0.45:
			var w := mono_b.get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
			ov.draw_rect(Rect2(px + w + 3, py - 13, 8, 16), Color(ACCENT, pa))


func _panel(r: Rect2, c: Color, radius: int, target: CanvasItem = self) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = c
	sb.set_corner_radius_all(radius)
	sb.border_color = Color(EDGE, EDGE.a * c.a)
	sb.set_border_width_all(1)
	sb.anti_aliasing = true
	target.draw_style_box(sb, r)


static func _num(n: int) -> String:
	var s := str(n)
	return s if s.length() <= 3 else s.substr(0, s.length() - 3) + " " + s.substr(s.length() - 3)
