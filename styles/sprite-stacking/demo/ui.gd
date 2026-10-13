extends Node2D
## Oberfläche im Stil eines Pixel-Indiespiels: Ortsschild oben links, Textleiste unten mit Erzählzeile,
## Eingabezeile, drei Antworten und einem Ansichtsfenster, in dem sich das Paket als Sprite-Stack dreht
## (dieselbe Technik und derselbe Shader wie die Szene, Licht ohne Weltlage).
## Alles in Basisauflösung 426x240, Pixelschriften ohne Glättung.

const STACKS := "res://stacks/"
const LINE := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PROMPT := "> nimm paket"
const LOCATION := "HAFEN VON LORNHOLM"
const SELECTED := 1

const C_FILL := Color8(22, 24, 48)
const C_FILL_HI := Color8(35, 38, 74)
const C_OUTER := Color8(7, 8, 15)
const C_BRASS := Color8(196, 154, 92)
const C_BRASS_DK := Color8(110, 82, 48)
const C_TEXT := Color8(241, 228, 198)
const C_DIM := Color8(150, 142, 160)
const C_ACCENT := Color8(246, 166, 64)
const C_SEL := Color8(43, 46, 88)
const C_PROMPT := Color8(150, 214, 198)
const C_BOX := Color8(13, 15, 34)

var body: FontVariation
var title: FontVariation
var t := 0.0
var parcel_slices: Array = []
var parcel_info: Dictionary
var box := Rect2(378, 186, 39, 46)


func _ready() -> void:
	body = make_font("res://fonts/PixelOperator8.ttf")
	title = make_font("res://fonts/Silkscreen-Regular.ttf")
	if "--mask" in OS.get_cmdline_user_args():
		return
	# Paket-Stack für das Ansichtsfenster
	var cfg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(STACKS + "stacks.json"))
	parcel_info = cfg.stacks["parcel_big"]
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/voxel.gdshader")
	m.set_shader_parameter("normal_tex", load(STACKS + "parcel_big_n.png"))
	m.set_shader_parameter("ramp_tex", load(STACKS + "ramps.png"))
	m.set_shader_parameter("glow_start", int(cfg.glow_start))
	m.set_shader_parameter("portrait", 1.0)
	var tex: Texture2D = load(STACKS + "parcel_big.png")
	for z in int(parcel_info.layers):
		var sp := Sprite2D.new()
		sp.texture = tex
		sp.region_enabled = true
		sp.centered = false
		sp.material = m
		add_child(sp)
		sp.self_modulate = Color(float(z) / 255.0, float(z) / 255.0, 0, 1)
		parcel_slices.append(sp)
	_process(0.0)


func make_font(path: String) -> FontVariation:
	var f: FontFile = load(path)
	f.antialiasing = TextServer.FONT_ANTIALIASING_NONE
	f.hinting = TextServer.HINTING_NONE
	f.subpixel_positioning = TextServer.SUBPIXEL_POSITIONING_DISABLED
	var v := FontVariation.new()
	v.base_font = f
	v.opentype_features = {"liga": 0}
	return v


func _process(delta: float) -> void:
	t += delta
	if parcel_slices.size() > 0:
		var a := 0.6 + t * 1.25                       # Drehteller, etwa 72° je Sekunde
		var c := Vector2(box.position.x + box.size.x * 0.5, box.position.y + box.size.y - 12)
		var cells: Array = parcel_info.cells
		for z in parcel_slices.size():
			var sp: Sprite2D = parcel_slices[z]
			var cell = cells[z]
			if cell == null:
				sp.visible = false
				continue
			sp.region_rect = Rect2(cell[0], cell[1], cell[2], cell[3])
			sp.offset = Vector2(cell[4], cell[5])
			sp.position = c + Vector2(0, -z)
			sp.rotation = a
	queue_redraw()


func frame_box(r: Rect2, fill: Color) -> void:
	## Pixelrahmen: dunkle Außenkante, Messinglinie mit abgeschrägten Ecken, Schattenlinie innen
	draw_rect(r.grow(1), C_OUTER)
	draw_rect(r, C_BRASS)
	draw_rect(Rect2(r.position.x, r.position.y, 1, 1), C_OUTER)
	draw_rect(Rect2(r.end.x - 1, r.position.y, 1, 1), C_OUTER)
	draw_rect(Rect2(r.position.x, r.end.y - 1, 1, 1), C_OUTER)
	draw_rect(Rect2(r.end.x - 1, r.end.y - 1, 1, 1), C_OUTER)
	draw_rect(r.grow(-1), C_BRASS_DK)
	draw_rect(Rect2(r.position + Vector2(2, 2), r.size - Vector2(3, 3)), fill)


func _draw() -> void:
	if "--mask" in OS.get_cmdline_user_args():
		return
	# Ortsschild
	var tw := title.get_string_size(LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x
	var tag := Rect2(5, 5, tw + 22, 14)
	frame_box(tag, C_FILL)
	draw_rect(Rect2(tag.position.x + 6, tag.position.y + 5, 3, 3), C_ACCENT)    # kleine Raute
	draw_rect(Rect2(tag.position.x + 7, tag.position.y + 4, 1, 5), C_ACCENT)
	draw_rect(Rect2(tag.position.x + 5, tag.position.y + 6, 5, 1), C_ACCENT)
	draw_string(title, Vector2(tag.position.x + 14, tag.position.y + 10), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, C_TEXT)
	# Textleiste
	var panel := Rect2(4, 181, 418, 55)
	frame_box(panel, C_FILL)
	draw_rect(Rect2(panel.position.x + 2, panel.position.y + 2, panel.size.x - 3, 1), C_FILL_HI)
	for i in LINE.size():
		draw_string(body, Vector2(12, 196 + i * 11), LINE[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 8, C_TEXT)
	draw_string(body, Vector2(12, 228), PROMPT, HORIZONTAL_ALIGNMENT_LEFT, -1, 8, C_PROMPT)
	var pw := body.get_string_size(PROMPT, HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x
	if fmod(t, 0.8) < 0.45:
		draw_rect(Rect2(14 + pw, 221, 5, 8), C_PROMPT)
	# Trennlinie
	draw_rect(Rect2(219, 187, 1, 44), C_BRASS_DK)
	# Antworten
	for i in CHOICES.size():
		var y := 196 + i * 12
		var sel := i == SELECTED
		if sel:
			var cw := body.get_string_size(CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 8).x
			draw_rect(Rect2(223, y - 9, cw + 16, 11), C_SEL)
			draw_rect(Rect2(223, y - 9, 1, 11), C_ACCENT)
			var bump := 1.0 if fmod(t, 0.6) < 0.3 else 0.0      # Pfeil wippt
			var ax := 226.0 + bump
			for k in 3:
				draw_rect(Rect2(ax + k, y - 7 + k, 1, 7 - 2 * k), C_ACCENT)
		draw_string(body, Vector2(232, y), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 8, C_ACCENT if sel else C_TEXT)
	# Ansichtsfenster mit dem Paket
	frame_box(box, C_BOX)
	draw_rect(Rect2(box.position.x + 9, box.end.y - 10, box.size.x - 18, 1), Color8(30, 33, 62))
