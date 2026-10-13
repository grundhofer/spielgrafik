extends Node2D
## Hauptdemo der Ortsserie: drei Stile an drei neuen Orten von Lornholm, alle Bilder mit agy (Gemini-Bildmodell).
## Jede Zelle ist die lebende Szene eines Stils (res://<stil>/<ort>.tscn, gebaut von den Skripten in
## styles/ortsserie/<stil>/scripts/) in einer eigenen SubViewport 1280×720; das Raster zeigt sie über
## shaders/verkleinern.gdshader verkleinert auf 368×207.
##
## Zeitplan (6 s, 30 Bilder/s):
##   0,00–2,00 s  Raster 3×3: Zeilen = Stile, Spalten = Orte
##   2,00–2,35 s  Zoom in Bilderbuch & Gouache · Stube, groß bis 3,50 s
##   3,50–3,70 s  Überblendung zu Digital gemalt (lebendes Standbild) · Klippenpfad, groß bis 4,75 s
##   4,75–4,95 s  Überblendung zu Japanischer 16-Bit-PC · Lampenraum, groß bis zum Ende
## Jede Großansicht zeigt einen anderen Stil und einen anderen Ort und steht 1,05–1,15 s ruhig. Die Überblendungen
## liegen zwischen den Zeitpunkten von media/frames.jpg (2,5 / 3,4 / 4,2 / 5,1 / 6,0 s), damit dort jede Großansicht
## unvermischt erscheint.
##
## Zeit aus dem Bildzähler: t = t0 + n / 30. Alle neun Szenen bekommen dieselbe Zeit über ihre eigene Schnittstelle
## (Gouache: autoplay = false + set_time(t); Digital gemalt: frozen + t0 + _update(); 16-Bit-PC: n + _update(n)).
## Bild n der Aufnahme zeigt t = n / 30. Benutzerargumente nach „--“: --t0=<s> (Startzeit), --grid (Raster ohne
## Großansichten), --solo=<zeile>,<spalte> (eine Zelle von Anfang an groß, z. B. --solo=2,0).

const FPS := 30.0
const STILE := [
	{"dir": "bilderbuch-gouache", "name": "Bilderbuch & Gouache", "label": "Bilderbuch &\nGouache",
		"sub": "Hafenbild des Stils als Referenz"},
	{"dir": "painterly-digital", "name": "Digital gemalt", "label": "Digital gemalt",
		"sub": "lebendes Standbild; Klippe ohne Referenz"},
	{"dir": "pc98-adventure", "name": "Japanischer 16-Bit-PC", "label": "Japanischer\n16-Bit-PC",
		"sub": "Serienpalette; Klippe mit Himmel aus dem Anker"},
]
const ORTE := [
	{"key": "leuchtturm", "name": "Lampenraum im Leuchtturm"},
	{"key": "stube", "name": "Stube des Hafenmeisters"},
	{"key": "klippe", "name": "Klippenpfad"},
]
const SCREEN := Vector2(1280, 720)
const CELL := Vector2(368, 207)
const GAP := 6.0
const GRID0 := Vector2(152, 77)
const BIG := [[0, 1, 2.0], [1, 2, 3.5], [2, 0, 4.75]]   # Zeile, Spalte, Beginn in s
const ZOOM := 0.35
const FADE := 0.2
const CREAM := Color(0.95, 0.92, 0.85)
const DIM := Color(0.72, 0.70, 0.66)
const AMBER := Color(0.93, 0.72, 0.42)

var n := 0
var t0 := 0.0
var grid_only := false
var big := BIG.duplicate(true)
var scenes := []          # [zeile][spalte] -> Szene
var cells := []           # [zeile][spalte] -> TextureRect
var caption: PanelContainer
var caption_lbl: Label
var font_sans: FontVariation
var font_sc: FontVariation


func _ready() -> void:
	process_priority = -10   # vor den Szenen, damit alle im selben Bild dieselbe Zeit zeigen
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--grid":
			grid_only = true
		elif a.begins_with("--solo="):
			var rc := a.substr(7).split(",")
			big = [[int(rc[0]), int(rc[1]), -ZOOM]]
	font_sans = _font("res://painterly-digital/fonts/AlegreyaSans-Medium.ttf")
	font_sc = _font("res://painterly-digital/fonts/AlegreyaSC-Medium.ttf", 2)

	var bg := ColorRect.new()
	bg.color = Color(0.06, 0.055, 0.08)
	bg.size = SCREEN
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)

	var mat := ShaderMaterial.new()
	mat.shader = load("res://shaders/verkleinern.gdshader")
	for r in STILE.size():
		var row_s := []
		var row_c := []
		for c in ORTE.size():
			var sv := SubViewport.new()
			sv.size = Vector2i(SCREEN)
			sv.disable_3d = true
			sv.transparent_bg = false
			sv.render_target_update_mode = SubViewport.UPDATE_ALWAYS
			add_child(sv)
			var inst = load("res://%s/%s.tscn" % [STILE[r]["dir"], ORTE[c]["key"]]).instantiate()
			if r == 0:
				inst.autoplay = false
			sv.add_child(inst)
			if r == 1:
				inst.frozen = true
			row_s.append(inst)
			var tr := TextureRect.new()
			tr.texture = sv.get_texture()
			tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			tr.stretch_mode = TextureRect.STRETCH_SCALE
			tr.material = mat
			tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
			row_c.append(tr)
		scenes.append(row_s)
		cells.append(row_c)

	_build_labels()
	for r in cells.size():
		for c in cells[r].size():
			add_child(cells[r][c])
	_build_caption()
	_step(t0)


func _process(_delta: float) -> void:
	_step(t0 + n / FPS)
	n += 1


func _step(t: float) -> void:
	var frame := int(roundf(t * FPS))
	for r in scenes.size():
		for c in scenes[r].size():
			var s = scenes[r][c]
			match r:
				0:
					s.set_time(t)
				1:
					s.t0 = t
					s.t = t
					s._update()
				2:
					s.n = frame
					s._update(frame)
	_layout(t)


func _font(path: String, spacing := 0) -> FontVariation:
	var f := FontVariation.new()
	f.base_font = load(path)
	f.spacing_glyph = spacing
	var ts := TextServerManager.get_primary_interface()
	f.opentype_features = {ts.name_to_tag("liga"): 0, ts.name_to_tag("clig"): 0}
	return f


func _label(text: String, font: Font, size: int, col: Color, pos: Vector2, width: float,
		align := HORIZONTAL_ALIGNMENT_LEFT) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.horizontal_alignment = align
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.position = pos
	l.size = Vector2(width, 0)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(l)
	return l


func _cell_rect(r: int, c: int) -> Rect2:
	return Rect2(GRID0 + Vector2(c * (CELL.x + GAP), r * (CELL.y + GAP)), CELL)


func _build_labels() -> void:
	_label("Ortsserie · ein Look, drei neue Orte · alle Bilder agy (Gemini-Bildmodell)", font_sans, 21, CREAM,
			Vector2(12, 8), 1256)
	for c in ORTE.size():
		var rc := _cell_rect(0, c)
		_label(ORTE[c]["name"], font_sc, 20, AMBER, Vector2(rc.position.x, 44), CELL.x, HORIZONTAL_ALIGNMENT_CENTER)
	for r in STILE.size():
		var rc := _cell_rect(r, 0)
		var w := GRID0.x - 12.0 - 10.0
		var name_l := _label(STILE[r]["label"], font_sans, 20, CREAM, Vector2(12, 0), w)
		var sub_l := _label(STILE[r]["sub"], font_sans, 15, DIM, Vector2(12, 0), w)
		# senkrecht mittig zur Zeile: Höhe erst nach dem Umbruch bekannt
		var h_name := name_l.get_minimum_size().y
		var h_sub := sub_l.get_minimum_size().y
		var y := rc.position.y + (CELL.y - h_name - 6.0 - h_sub) * 0.5
		name_l.position.y = roundf(y)
		sub_l.position.y = roundf(y + h_name + 6.0)


func _build_caption() -> void:
	caption = PanelContainer.new()
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.05, 0.05, 0.08, 0.82)
	sb.border_color = Color(0.95, 0.85, 0.65, 0.35)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(6)
	sb.content_margin_left = 12
	sb.content_margin_right = 12
	sb.content_margin_top = 4
	sb.content_margin_bottom = 6
	caption.add_theme_stylebox_override("panel", sb)
	caption.position = Vector2(16, 16)
	caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	caption_lbl = Label.new()
	caption_lbl.add_theme_font_override("font", font_sans)
	caption_lbl.add_theme_font_size_override("font_size", 20)
	caption_lbl.add_theme_color_override("font_color", CREAM)
	caption.add_child(caption_lbl)
	add_child(caption)
	caption.visible = false


func _layout(t: float) -> void:
	for r in cells.size():
		for c in cells[r].size():
			var tr: TextureRect = cells[r][c]
			var rc := _cell_rect(r, c)
			tr.position = rc.position
			tr.size = rc.size
			tr.z_index = 0
			tr.modulate = Color.WHITE
	caption.visible = false
	if grid_only:
		return
	var full := Rect2(Vector2.ZERO, SCREEN)
	for i in big.size():
		var b: Array = big[i]
		var start: float = b[2]
		if t < start:
			continue
		var tr: TextureRect = cells[b[0]][b[1]]
		tr.z_index = 10 + i
		var rc := full
		if i == 0:
			var u := smoothstep(0.0, 1.0, clampf((t - start) / ZOOM, 0.0, 1.0))
			var a := _cell_rect(b[0], b[1])
			rc = Rect2(a.position.lerp(full.position, u), a.size.lerp(full.size, u))
			# ganze Pixel, damit die Großansicht am Ende genau 1:1 liegt
			rc = Rect2(rc.position.round(), rc.size.round())
		else:
			tr.modulate = Color(1, 1, 1, clampf((t - start) / FADE, 0.0, 1.0))
		tr.position = rc.position
		tr.size = rc.size
		var settled := start + (ZOOM if i == 0 else FADE)
		caption.visible = true
		caption.z_index = 20
		caption_lbl.text = "%s · %s" % [STILE[b[0]]["name"], ORTE[b[1]]["name"]]
		caption.modulate = Color(1, 1, 1, clampf((t - settled) / 0.15, 0.0, 1.0))
