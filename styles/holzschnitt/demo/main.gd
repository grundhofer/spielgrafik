extends Node2D
## Holz- und Linolschnitt: Hafen von Lornholm.
## Alles, was gedruckt wird (Hafen, Dachs, Schatten, Schrift), zeichnet in einen Platten-Viewport: R = Schwarzstock,
## G = Petrol, B = Zinnober (Farbe 0 = Papier). Ein Vollbild-Shader (print.gdshader) druckt die drei Platten
## mit Passerversatz, Kantenwackeln, Einfärbung und Papierbogen der aktuellen Druckfassung.
## Prüfschalter nach "--": --probe-badger (nur Dachs, Platten roh), --probe-raw (alle Platten roh, ohne Druckfehler),
## --probe-log (Takt, Bild und Lage je Frame), --t0=<s> (Umgebung und Druckfassungen um s Sekunden vorstellen,
## für die Langzeitprüfung; der Dachs bleibt beim Ablauf der 6 s).

const W := 1280
const H := 720
const BLOCK_POS := Vector2(60, 18)
const BLOCK_SIZE := Vector2(1160, 580)
const VERSION_TICKS := 5          # neue Druckfassung alle 5 Takte (6 je Sekunde)
const VERSIONS := 4               # vier Abzüge im Wechsel (klassischer Boil)
const ANIM_TICKS := 3             # Umgebungsanimation auf Dreien (10 Bilder/s)
const BEAM_PERIOD := 7.0          # s je Umlauf des Leuchtfeuers

const INK := Color(1, 0, 0)       # Schwarzstock
const TEAL := Color(0, 1, 0)
const ORANGE := Color(0, 0, 1)
const PAPER := Color(0, 0, 0)

var t := 0.0
var tick := -1
var rng := RandomNumberGenerator.new()
var plates: SubViewport
var block_mat: ShaderMaterial
var print_mat: ShaderMaterial
var badger: Sprite2D
var shadow: Sprite2D
var bg: Sprite2D
var cursor: Polygon2D
var timeline: Dictionary
var scene: Dictionary
var versions: Array = []
var flick: Array = []
var probe_badger := false
var probe_raw := false
var probe_log := false
var t0_ticks := 0


func load_json(path: String) -> Variant:
	var txt := FileAccess.get_file_as_string(path)
	var data: Variant = JSON.parse_string(txt)
	if data == null:
		push_error("JSON fehlt oder kaputt: " + path)
	return data


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe_badger = "--probe-badger" in args
	probe_raw = "--probe-raw" in args or probe_badger
	probe_log = "--probe-log" in args
	for a in args:
		if a.begins_with("--t0="):
			t0_ticks = int(round(float(a.substr(5)) * 30.0))
	rng.seed = 18981015
	scene = load_json("res://art/scene.json")
	timeline = load_json("res://art/timeline.json")

	# Druckfassungen: Passer je Platte (fester Grundversatz + kleine Abweichung je Abzug), Rauschversatz, Bogen
	for i in VERSIONS:
		versions.append({
			"reg_k": Vector2(rng.randf_range(-0.6, 0.6), rng.randf_range(-0.6, 0.6)),
			"reg_t": Vector2(2.4, -1.6) + Vector2(rng.randf_range(-0.9, 0.9), rng.randf_range(-0.9, 0.9)),
			"reg_o": Vector2(-1.8, 2.0) + Vector2(rng.randf_range(-0.9, 0.9), rng.randf_range(-0.9, 0.9)),
			"seed": Vector2(rng.randf(), rng.randf()),
			"sheet": Vector2(rng.randf_range(0, W), rng.randf_range(0, H)),
		})
	for i in 64:
		flick.append(rng.randf())

	plates = SubViewport.new()
	plates.size = Vector2i(W, H)
	plates.disable_3d = true
	plates.transparent_bg = false
	plates.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(plates)
	var clear := ColorRect.new()
	clear.color = TEAL if probe_badger else PAPER     # Prüfbild: Figur samt Papierrand vor Petrol
	clear.size = Vector2(W, H)
	plates.add_child(clear)

	# Druckstock (Bildfeld): beschneidet Dachs und Schatten an der Stockkante
	var block := Control.new()
	block.position = BLOCK_POS
	block.size = BLOCK_SIZE
	block.clip_contents = true
	plates.add_child(block)

	bg = Sprite2D.new()
	bg.centered = false
	bg.texture = load("res://art/plates_bg.png")
	block_mat = ShaderMaterial.new()
	block_mat.shader = load("res://shaders/block.gdshader")
	block_mat.set_shader_parameter("regions_tex", load("res://art/regions.png"))
	block_mat.set_shader_parameter("horizon", float(scene["horizon_y"]))
	block_mat.set_shader_parameter("lamp_pos", Vector2(scene["lamp"]["cx"], scene["lamp"]["cy"]))
	block_mat.set_shader_parameter("lantern_pos", Vector2(scene["lantern"]["cx"], scene["lantern"]["cy"]))
	bg.material = block_mat
	bg.visible = not probe_badger
	block.add_child(bg)

	shadow = Sprite2D.new()
	shadow.centered = false
	shadow.texture = load("res://art/shadow.png")
	shadow.visible = not probe_badger
	block.add_child(shadow)

	badger = Sprite2D.new()
	badger.centered = false
	badger.texture = load("res://art/badger.png")
	badger.hframes = int(timeline["frames"])
	block.add_child(badger)

	if not probe_badger:
		build_text()

	var pr := TextureRect.new()
	pr.size = Vector2(W, H)
	pr.texture = plates.get_texture()
	pr.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
	print_mat = ShaderMaterial.new()
	print_mat.shader = load("res://shaders/print.gdshader")
	print_mat.set_shader_parameter("plates_tex", plates.get_texture())
	print_mat.set_shader_parameter("paper_tex", load("res://art/paper.png"))
	print_mat.set_shader_parameter("grain_tex", load("res://art/grain.png"))
	print_mat.set_shader_parameter("noise_tex", load("res://art/noise.png"))
	print_mat.set_shader_parameter("probe", 1 if probe_raw else 0)
	pr.material = print_mat
	add_child(pr)
	_step()


func font_var(path: String, wght: int) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = load(path)
	var ts := TextServerManager.get_primary_interface()
	fv.variation_opentype = {ts.name_to_tag("wght"): wght}
	return fv


func add_label(parent: Node, text: String, font: Font, size: int, color: Color, pos: Vector2) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	l.position = pos
	parent.add_child(l)
	return l


## Unregelmäßiges Viereck wie ein mit dem Messer geschnittener Block
func cut_block(parent: Node, rect: Rect2, color: Color, jitter: float) -> Polygon2D:
	var pg := Polygon2D.new()
	var r := rect
	var pts := PackedVector2Array()
	var corners := [r.position, Vector2(r.end.x, r.position.y), r.end, Vector2(r.position.x, r.end.y)]
	for i in 4:
		var a: Vector2 = corners[i]
		var b: Vector2 = corners[(i + 1) % 4]
		var n := int(max(2.0, a.distance_to(b) / 40.0))
		for j in n:
			var p := a.lerp(b, float(j) / n)
			pts.append(p + Vector2(rng.randf_range(-jitter, jitter), rng.randf_range(-jitter, jitter)))
	pg.polygon = pts
	pg.color = color
	parent.add_child(pg)
	return pg


func build_text() -> void:
	var ui := Control.new()
	ui.size = Vector2(W, H)
	plates.add_child(ui)
	var title_font: Font = load("res://fonts/HoltwoodOneSC-Regular.ttf")
	var body := font_var("res://fonts/Vollkorn-wght.ttf", 560)
	var body_b := font_var("res://fonts/Vollkorn-wght.ttf", 720)
	var italic := font_var("res://fonts/Vollkorn-Italic-wght.ttf", 560)

	var y1 := 614.0
	# Ortsschild: schwarzer Block, Schrift ausgespart (Papier)
	var loc := "HAFEN VON LORNHOLM"
	var tsz := title_font.get_string_size(loc, HORIZONTAL_ALIGNMENT_LEFT, -1, 17)
	cut_block(ui, Rect2(BLOCK_POS.x, y1, tsz.x + 30, 34), INK, 1.2)
	add_label(ui, loc, title_font, 17, PAPER, Vector2(BLOCK_POS.x + 15, y1 + 3))
	add_label(ui, "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich.", body, 25, INK,
		Vector2(BLOCK_POS.x + tsz.x + 48, y1 - 2))

	# Auswahl: Ziffern in Zinnober-Blöckchen, Text schwarz
	var y2 := 660.0
	var x := BLOCK_POS.x
	var choices: Array = ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
	for i in choices.size():
		cut_block(ui, Rect2(x, y2 + 3, 26, 28), ORANGE, 1.0)
		add_label(ui, str(i + 1), body_b, 21, PAPER, Vector2(x + 7, y2 + 1))
		var lab := add_label(ui, choices[i], body, 23, INK, Vector2(x + 36, y2 - 1))
		x += 36 + body.get_string_size(choices[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 23).x + 34
	# Eingabezeile rechts
	var prompt := "> nimm paket"
	var psz := italic.get_string_size(prompt, HORIZONTAL_ALIGNMENT_LEFT, -1, 23)
	var px := BLOCK_POS.x + BLOCK_SIZE.x - psz.x - 18
	add_label(ui, prompt, italic, 23, INK, Vector2(px, y2 - 1))
	cursor = Polygon2D.new()
	cursor.polygon = PackedVector2Array([Vector2(0, 0), Vector2(11, 1), Vector2(10, 25), Vector2(1, 24)])
	cursor.color = ORANGE
	cursor.position = Vector2(px + psz.x + 4, y2 + 5)
	ui.add_child(cursor)
	# Trennschnitt zwischen Ortszeile und Auswahl: eine geschnittene Linie
	cut_block(ui, Rect2(BLOCK_POS.x, y2 - 6, BLOCK_SIZE.x, 2.5), INK, 0.5)


func _process(delta: float) -> void:
	t += delta
	_step()


func _step() -> void:
	tick += 1
	var ticks: Array = timeline["ticks"]
	var e: Dictionary = ticks[min(tick, ticks.size() - 1)]
	var fw := float(timeline["frame_w"])
	badger.frame = int(e["f"])
	badger.position = Vector2(float(e["x"]), float(e["y"]) - float(timeline["sole_y"]))
	# Schatten: unter der Körpermitte (Bogenmitte), leicht nach rechts vorn (Laterne steht links hinten)
	shadow.position = Vector2(float(e["x"]) + fw * 0.5 - 68.0 + 16.0, float(e["y"]) - 13.0)

	# Druckfassung
	var at_tick := tick + t0_ticks
	var v: Dictionary = versions[(at_tick / VERSION_TICKS) % VERSIONS]
	print_mat.set_shader_parameter("reg_k", v["reg_k"])
	print_mat.set_shader_parameter("reg_t", v["reg_t"])
	print_mat.set_shader_parameter("reg_o", v["reg_o"])
	print_mat.set_shader_parameter("seed", v["seed"])
	print_mat.set_shader_parameter("sheet", v["sheet"])

	# Umgebung auf Dreien
	var at := float(at_tick - at_tick % ANIM_TICKS) / 30.0
	block_mat.set_shader_parameter("t_anim", at)
	var phase := TAU * (at / BEAM_PERIOD) + 1.0
	block_mat.set_shader_parameter("beam_phase", phase)
	block_mat.set_shader_parameter("flash", pow(max(0.0, cos(phase)), 12.0))
	var fi := (at_tick / ANIM_TICKS) % flick.size()
	block_mat.set_shader_parameter("flicker", flick[fi])
	block_mat.set_shader_parameter("flicker_seed", float(fi) * 1.37)
	block_mat.set_shader_parameter("puffs", smoke_puffs(at))
	if cursor:
		cursor.visible = (tick / 15) % 2 == 0
	if probe_log:
		print("TICK %d frame %d x %d" % [tick, int(e["f"]), int(e["x"])])


## Rauchfahne: alle 0,3 s ein Ballen; der Wind treibt sie flach nach rechts (oben ist wenig Himmel), die Ballen
## wachsen, überlappen zu einer gebogten Fahne und werden am Ende kleiner.
func smoke_puffs(at: float) -> PackedVector4Array:
	var out := PackedVector4Array()
	var top := Vector2(scene["chimney"]["cx"], scene["chimney"]["y0"])
	var interval := 0.3
	var life := 2.9
	var n0 := int(floor(at / interval))
	for k in 10:
		var n := n0 - k
		var age := at - n * interval
		if age < 0.0 or age > life:
			out.append(Vector4(0, 0, 0, 0))
			continue
		var u := age / life
		var wob := sin(float(n) * 2.1 + age * 2.3) * 3.0
		var pos := top + Vector2(2.0 + age * 36.0, -4.0 - age * 11.0 + wob)
		var r := (5.0 + 12.0 * sqrt(u)) * (1.0 - smoothstep(0.7, 1.0, u))
		out.append(Vector4(pos.x, pos.y, r, u))
	return out
