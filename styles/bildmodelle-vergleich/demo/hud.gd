extends Node2D
## Oberfläche der Vergleichsansicht (1280×720): Rahmen um das Bildpaar, je eine Messkarte links (Codex) und
## rechts (agy) und die Textbox unten mit den Modellnamen, dem Paar und dem Urteil.

const FRAME := Rect2(205, 20, 870, 580)
const CARD_L := Rect2(16, 20, 177, 580)
const CARD_R := Rect2(1087, 20, 177, 580)
const BOX := Rect2(16, 612, 1248, 92)

const BG := Color(0.086, 0.094, 0.114)
const LINE := Color(0.23, 0.25, 0.29)
const TEXT := Color(0.93, 0.91, 0.86)
const MUTED := Color(0.62, 0.63, 0.66)
const CODEX := Color(0.93, 0.66, 0.38)
const AGY := Color(0.47, 0.72, 0.89)

var pair_index := 0
var sans: FontVariation
var sans_b: FontVariation
var mono: FontFile


func _ready() -> void:
	var ts := TextServerManager.get_primary_interface()
	sans = FontVariation.new()
	sans.base_font = load("res://fonts/SourceSans3.ttf")
	sans.variation_opentype = {ts.name_to_tag("wght"): 420}
	sans_b = FontVariation.new()
	sans_b.base_font = load("res://fonts/SourceSans3.ttf")
	sans_b.variation_opentype = {ts.name_to_tag("wght"): 640}
	mono = load("res://fonts/IBMPlexMono-Regular.ttf")


func _panel(r: Rect2) -> void:
	draw_rect(r, BG)
	draw_rect(r, LINE, false, 1.0)


func _card(r: Rect2, model: String, sub: String, col: Color, lines: Array) -> void:
	_panel(r)
	var x := r.position.x + 14
	var w := r.size.x - 28
	draw_rect(Rect2(r.position.x, r.position.y, r.size.x, 4), col)
	draw_string(sans_b, Vector2(x, r.position.y + 40), model, HORIZONTAL_ALIGNMENT_LEFT, -1, 30, col)
	draw_string(sans, Vector2(x, r.position.y + 64), sub, HORIZONTAL_ALIGNMENT_LEFT, -1, 17, MUTED)
	draw_line(Vector2(x, r.position.y + 80), Vector2(x + w, r.position.y + 80), LINE, 1.0)
	var y := r.position.y + 108
	for i in lines.size():
		var s: String = lines[i]
		var f: Font = mono if i < 2 else sans
		var fs := 15 if i < 2 else 17
		var c := TEXT if i < 2 else Color(0.86, 0.85, 0.81)
		if i == 2:
			y += 10
		var h := f.get_multiline_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, w, fs).y
		draw_multiline_string(f, Vector2(x, y), s, HORIZONTAL_ALIGNMENT_LEFT, w, fs, -1, c)
		y += h + (6 if i < 2 else 14)


func _draw() -> void:
	var main = get_parent()
	var p: Dictionary = main.PAIRS[pair_index]
	draw_rect(Rect2(FRAME.position - Vector2(1, 1), FRAME.size + Vector2(2, 2)), LINE, false, 1.0)
	_card(CARD_L, "Codex", "gpt-image · links", CODEX, p["codex"])
	_card(CARD_R, "agy", "Gemini · rechts", AGY, p["agy"])

	_panel(BOX)
	var y0 := BOX.position.y
	# Modellnamen links und rechts in der Textbox
	draw_string(sans_b, Vector2(BOX.position.x + 18, y0 + 36), "◀  Codex", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, CODEX)
	draw_string(sans, Vector2(BOX.position.x + 18, y0 + 62), "gpt-image", HORIZONTAL_ALIGNMENT_LEFT, -1, 17, MUTED)
	var rx := BOX.end.x - 18
	var t1 := "agy  ▶"
	draw_string(sans_b, Vector2(rx - sans_b.get_string_size(t1, HORIZONTAL_ALIGNMENT_LEFT, -1, 22).x, y0 + 36), t1,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 22, AGY)
	var t2 := "Gemini-Bildmodell"
	draw_string(sans, Vector2(rx - sans.get_string_size(t2, HORIZONTAL_ALIGNMENT_LEFT, -1, 17).x, y0 + 62), t2,
			HORIZONTAL_ALIGNMENT_LEFT, -1, 17, MUTED)
	# Mitte: Paar, Quelle, Urteil
	var cx := 190.0
	var cw := BOX.size.x - 2 * cx
	var head := "%d / %d   %s" % [pair_index + 1, main.PAIRS.size(), p["title"]]
	draw_string(sans_b, Vector2(BOX.position.x + cx, y0 + 30), head, HORIZONTAL_ALIGNMENT_CENTER, cw, 22, TEXT)
	draw_string(sans, Vector2(BOX.position.x + cx, y0 + 52), "Gleicher Prompt für beide Modelle, " + p["source"],
			HORIZONTAL_ALIGNMENT_CENTER, cw, 15, MUTED)
	draw_string(sans, Vector2(BOX.position.x + cx, y0 + 77), p["verdict"], HORIZONTAL_ALIGNMENT_CENTER, cw, 17,
			Color(0.95, 0.88, 0.70))
