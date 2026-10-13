extends Control
## Leuchttisch-Feld: dieselbe Pose dreimal nebeneinander, so wie die Rotoskopie sie entstehen lässt:
## Vorlage aus Blender (Graustufen mit Innenlinien), klassischer Weg ohne KI (Konturen und Flächen per Skript)
## und die KI-Übermalung, die in der Szene läuft. Unter jedem Bild die Bodenlinie mit den aufgesetzten Sohlen aus
## den 3D-Daten (rote Striche); unter der KI-Fassung die gemessene Deckung mit der Vorlage.

const INK := Color(0.13, 0.10, 0.12)
const FRAME_BG := Color(0.11, 0.12, 0.19, 0.93)
const PAPER := Color(0.97, 0.95, 0.89)
const PENCIL := Color(0.45, 0.58, 0.85, 0.55)
const SOLE := Color(0.85, 0.2, 0.15)
const LABEL := Color(0.93, 0.89, 0.80)
const DIM := Color(0.66, 0.66, 0.74)
const SCALE := 0.76

var pose := 0
var phase_text := ""
var iou := 0.0
var meta: Dictionary
var tex: Array = []
var font: Font
var font_sc: Font


func setup(m: Dictionary) -> void:
	meta = m
	tex = [load("res://art/badger_template.png"), load("res://art/badger_classic.png"), load("res://art/badger_ai.png")]
	font = load("res://fonts/PatrickHand-Regular.ttf")
	font_sc = load("res://fonts/PatrickHandSC-Regular.ttf")


func _draw() -> void:
	if tex.is_empty():
		return
	var w := size.x
	var h := size.y
	var sb := StyleBoxFlat.new()
	sb.bg_color = FRAME_BG
	sb.set_corner_radius_all(10)
	sb.set_border_width_all(2)
	sb.border_color = Color(0.32, 0.34, 0.46, 0.9)
	sb.shadow_color = Color(0.02, 0.02, 0.06, 0.4)
	sb.shadow_size = 5
	draw_style_box(sb, Rect2(Vector2.ZERO, size))
	draw_string(font_sc, Vector2(16, 27), "Rotoskopie", HORIZONTAL_ALIGNMENT_LEFT, -1, 22, LABEL)
	draw_string(font, Vector2(16, 27), phase_text, HORIZONTAL_ALIGNMENT_RIGHT, w - 32, 19, DIM)
	var fw: float = meta["frame"][0]
	var fh: float = meta["frame"][1]
	var ax: float = meta["anchor"][0]
	var ay: float = meta["anchor"][1]
	var slot_w := 128.0
	var slot_h := 136.0
	var gap := (w - 32.0 - 3.0 * slot_w) / 2.0
	var labels := ["Vorlage aus 3D", "Skript, ohne KI", "KI übermalt"]
	for i in 3:
		var sx := 16.0 + i * (slot_w + gap)
		var sy := 38.0
		var slot := Rect2(sx, sy, slot_w, slot_h)
		draw_rect(slot, PAPER)
		# Lochleiste wie auf Animationspapier
		for k in 3:
			draw_rect(Rect2(sx + slot_w / 2.0 - 25.0 + k * 20.0, sy + 4.0, 10.0, 4.0), Color(0.75, 0.74, 0.70))
		var ground := sy + slot_h - 9.0
		var ox := sx + slot_w / 2.0 - ax * SCALE + 4.0
		var oy := ground - ay * SCALE
		draw_line(Vector2(sx + 6, ground), Vector2(sx + slot_w - 6, ground), PENCIL, 1.0)
		var src := Rect2(pose * fw, 0, fw, fh)
		draw_texture_rect_region(tex[i], Rect2(ox, oy, fw * SCALE, fh * SCALE), src)
		for s in meta["soles_px"][pose]:
			draw_line(Vector2(ox + s[0] * SCALE, ground + 3.0), Vector2(ox + s[1] * SCALE, ground + 3.0), SOLE, 2.0)
		draw_rect(slot, INK, false, 1.5)
		var lab: String = labels[i]
		draw_string(font, Vector2(sx, sy + slot_h + 19.0), lab, HORIZONTAL_ALIGNMENT_CENTER, slot_w, 17, LABEL)
	var note := "Deckung mit der Vorlage: %d %%" % int(round(iou * 100.0))
	var sx3 := 16.0 + 2.0 * (slot_w + gap)
	draw_string(font, Vector2(16, h - 8.0), "rot: Sohlen am Boden laut 3D", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, DIM)
	draw_string(font, Vector2(sx3 - 40.0, h - 8.0), note, HORIZONTAL_ALIGNMENT_RIGHT, slot_w + 40.0, 15, DIM)
