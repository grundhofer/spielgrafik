extends Control
## Textoberfläche über dem geraymarchten Bild: normale Godot-Control in voller Auflösung (1280×720),
## gezeichnet in _draw(). Ortsschild oben links, Textkasten unten rechts mit Zeile, Auswahl und Parser.
## Text aus data/motif.json → ui_text.

const LOCATION := "Hafen von Lornholm"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"

const INK := Color(0.96, 0.93, 0.86)
const INK_DIM := Color(0.78, 0.76, 0.82)
const WARM := Color(1.0, 0.68, 0.32)
const PANEL := Color(0.055, 0.06, 0.12, 0.8)
const BOX := Rect2(500, 516, 752, 180)
const T_BOX := 3.45

var sans: FontVariation
var sans_bold: FontVariation
var mono: FontVariation
var t := 0.0


func _ready() -> void:
	var sg := load("res://fonts/SpaceGrotesk-wght.ttf") as FontFile
	sans = FontVariation.new()
	sans.base_font = sg
	sans.variation_opentype = {"wght": 450}
	sans_bold = FontVariation.new()
	sans_bold.base_font = sg
	sans_bold.variation_opentype = {"wght": 640}
	var jb := load("res://fonts/JetBrainsMono-wght.ttf") as FontFile
	mono = FontVariation.new()
	mono.base_font = jb
	mono.variation_opentype = {"wght": 500}
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func set_time(tt: float) -> void:
	t = tt
	queue_redraw()


func _panel(r: Rect2, radius: float, fill: Color, border: Color, bw: float) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = fill
	sb.set_corner_radius_all(int(radius))
	sb.border_color = border
	sb.set_border_width_all(int(bw))
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 18
	sb.anti_aliasing = true
	draw_style_box(sb, r)


func _draw() -> void:
	# Ortsschild
	var tag_a := 1.0
	var tag := Rect2(28, 26, 300, 52)
	_panel(tag, 14, Color(PANEL, PANEL.a * tag_a), Color(WARM, 0.45 * tag_a), 1)
	draw_rect(Rect2(tag.position + Vector2(18, 17), Vector2(4, 18)), Color(WARM, tag_a))
	draw_string(sans_bold, tag.position + Vector2(34, 34), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 24, Color(INK, tag_a))

	# Textkasten: erscheint, wenn die Kamera beim Dachs ankommt (vorher läuft er durch diesen Bereich);
	# die Zeile erscheint Zeichen für Zeichen
	var box_a := clampf((t - T_BOX) / 0.3, 0.0, 1.0)
	if box_a <= 0.0:
		return
	var off := Vector2(0, 24.0 * pow(1.0 - box_a, 2.0))
	var r := Rect2(BOX.position + off, BOX.size)
	_panel(r, 18, Color(PANEL, PANEL.a * box_a), Color(WARM, 0.4 * box_a), 1)
	var n := int(clampf((t - T_BOX - 0.25) * 70.0, 0.0, LINE.length()))
	var shown := LINE.substr(0, n)
	# Zeilenumbruch nach Satz
	var lines := ["", ""]
	var cut := LINE.find(". ") + 1
	lines[0] = shown.substr(0, mini(n, cut))
	if n > cut + 1:
		lines[1] = shown.substr(cut + 1)
	var p := r.position + Vector2(28, 44)
	draw_string(sans, p, lines[0], HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color(INK, box_a))
	draw_string(sans, p + Vector2(0, 32), lines[1], HORIZONTAL_ALIGNMENT_LEFT, -1, 22, Color(INK, box_a))
	# Auswahl rechts, untereinander; Markierung wandert von der ersten zur zweiten Wahl
	var ch_a := clampf((t - T_BOX - 1.1) / 0.3, 0.0, 1.0) * box_a
	var sel := 0 if t < T_BOX + 1.9 else 1
	var cx := r.position.x + 470
	var cy := r.position.y + 50
	draw_rect(Rect2(r.position.x + 446, r.position.y + 22, 1, r.size.y - 44), Color(WARM, 0.25 * box_a))
	for i in CHOICES.size():
		var w := sans.get_string_size(CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 19).x
		var col := INK_DIM
		if i == sel:
			draw_rect(Rect2(cx - 12, cy - 22, w + 46, 32), Color(WARM, 0.2 * ch_a))
			draw_rect(Rect2(cx - 12, cy - 22, 3, 32), Color(WARM, ch_a))
			col = INK
		draw_string(mono, Vector2(cx, cy), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color(WARM, ch_a))
		draw_string(sans, Vector2(cx + 20, cy), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 19, Color(col, ch_a))
		cy += 44
	# Parser-Zeile mit Schreibmarke
	var pn := int(clampf((t - T_BOX - 1.3) * 10.0, 0.0, PARSER.length()))
	var pp := Vector2(r.position.x + 28, r.position.y + 162)
	var ptxt := PARSER.substr(0, maxi(pn, 1))
	draw_string(mono, pp, ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18, Color(WARM, box_a))
	var tw := mono.get_string_size(ptxt, HORIZONTAL_ALIGNMENT_LEFT, -1, 18).x
	if fmod(t, 0.8) < 0.45:
		draw_rect(Rect2(pp.x + tw + 3, pp.y - 15, 10, 19), Color(INK, 0.85 * box_a))
