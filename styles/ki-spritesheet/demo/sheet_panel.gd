extends Node2D
## Erklärfeld der Technik: zeigt zum aktuellen Zustand das KI-Blatt (alle Bilder als Vorschau, ausgesortierte
## und nur teilweise genutzte Bilder markiert, das gerade gezeigte Quellbild umrahmt), daneben dieselbe
## Bewegung zweimal: „roh“ (Blatt mit tools/sprites.py slice zerlegt, alle Bilder in Blattreihenfolge) und
## „korrigiert“ (die AnimatedSprite2D-Bilder des Dachses). Darunter Befund und Gegenmittel aus anim.json.

const W := 620.0
const H := 236.0
const MONO := preload("res://fonts/JetBrainsMono-var.ttf")
const STATES := ["walk", "idle", "jump", "wave"]
const RAW_X := 400.0
const FIX_X := 532.0
const BASE_Y := 168.0
const RAW_SCALE := 0.90
const FIX_SCALE := 0.55
const ACCENT := Color(1.0, 0.76, 0.40)
const BAD := Color(1.0, 0.45, 0.42)
const GOOD := Color(0.55, 0.88, 0.62)

var meta: Dictionary
var thumbs := {}
var cur := {"anim": "walk", "frame": 0, "local": 0, "cell": 0}
var fv_head: FontVariation
var fv_text: FontVariation
var fv_bold: FontVariation

@onready var raw_mini: AnimatedSprite2D = $RawMini
@onready var fix_mini: AnimatedSprite2D = $FixMini


func setup(m: Dictionary, frames_res: SpriteFrames, raw_res: SpriteFrames) -> void:
	meta = m
	for s in STATES:
		thumbs[s] = load("res://art/thumbs_%s.png" % s)
	fix_mini.sprite_frames = frames_res
	raw_mini.sprite_frames = raw_res
	raw_mini.scale = Vector2(RAW_SCALE, RAW_SCALE)
	fix_mini.scale = Vector2(FIX_SCALE, FIX_SCALE)
	raw_mini.centered = false
	fix_mini.centered = false
	fv_head = FontVariation.new()
	fv_head.base_font = MONO
	fv_head.variation_opentype = {"wght": 600}
	fv_text = FontVariation.new()
	fv_text.base_font = MONO
	fv_text.variation_opentype = {"wght": 400}
	fv_bold = FontVariation.new()
	fv_bold.base_font = MONO
	fv_bold.variation_opentype = {"wght": 700}


func show_state(st: Dictionary, _vf: int) -> void:
	cur = st
	var anim: String = st.anim
	# korrigiert: dieselbe Zelle wie der große Dachs, an Ort und Stelle
	fix_mini.animation = st.sprite_anim
	fix_mini.frame = st.sprite_frame
	var a: Array = meta.anims[anim].anchor
	fix_mini.offset = Vector2(-mid_x(anim), -a[1])
	fix_mini.position = Vector2(FIX_X, BASE_Y)
	# roh: alle Blattbilder in Reihenfolge mit dem Tempo, das man ohne Prüfung nähme
	var rj: Dictionary = meta.raw[anim]
	var ri := int(floor(int(st.local) * float(rj.fps) / 30.0))
	ri = mini(ri, int(rj.count) - 1) if anim == "jump" else ri % int(rj.count)
	raw_mini.animation = anim
	raw_mini.frame = ri
	raw_mini.offset = Vector2(-float(rj.frame_w) / 2.0, -float(rj.frame_h))
	raw_mini.position = Vector2(RAW_X, BASE_Y)
	cur["raw_frame"] = ri
	queue_redraw()


func mid_x(anim: String) -> float:
	## feste Mitte je Zustand für die Vorschau: Mittel der Fußmitten aller Zellen (beim Laufen bleibt der Kopf fest)
	var sum := 0.0
	var n := 0
	for v in meta.anims[anim].body_x:
		if v != null:
			sum += float(v)
			n += 1
	return sum / max(n, 1)


func text(pos: Vector2, s: String, size: int, col: Color, fv: Font = null) -> void:
	draw_string(fv if fv else fv_text, pos, s, HORIZONTAL_ALIGNMENT_LEFT, -1, size, col)


func text_w(s: String, size: int, fv: Font = null) -> float:
	return (fv if fv else fv_text).get_string_size(s, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x


func _draw() -> void:
	if meta.is_empty():
		return
	var anim: String = cur.anim
	# Grund
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.06, 0.07, 0.11, 0.86)
	sb.set_corner_radius_all(10)
	sb.set_border_width_all(1)
	sb.border_color = Color(0.62, 0.68, 0.82, 0.45)
	draw_style_box(sb, Rect2(0, 0, W, H))
	# Kopfzeile mit Zuständen
	text(Vector2(14, 25), "KI-Sprite-Sheet → AnimatedSprite2D", 13, Color(0.88, 0.91, 1.0), fv_head)
	var x := W - 14.0
	for i in range(STATES.size() - 1, -1, -1):
		var s: String = STATES[i]
		var w := text_w(s, 12, fv_bold) + 14.0
		x -= w
		var r := Rect2(x, 9, w, 21)
		var on := s == anim
		var chip := StyleBoxFlat.new()
		chip.set_corner_radius_all(10)
		chip.bg_color = ACCENT if on else Color(1, 1, 1, 0.0)
		chip.set_border_width_all(0 if on else 1)
		chip.border_color = Color(0.62, 0.68, 0.82, 0.5)
		draw_style_box(chip, r)
		text(Vector2(x + 7, 24), s, 12, Color(0.10, 0.08, 0.06) if on else Color(0.66, 0.70, 0.80), fv_bold)
		x -= 5.0
	# Vorschau des KI-Blatts
	var th: Dictionary = meta.thumbs[anim]
	var tex: Texture2D = thumbs[anim]
	var ox := 14.0
	var oy := 44.0
	text(Vector2(ox, oy - 3), "KI-Blatt (%d Bilder)" % th.rects.size(), 10, Color(0.62, 0.66, 0.76))
	draw_texture(tex, Vector2(ox, oy + 4))
	var src: Array = meta.anims[anim].src[1]
	var cell := int(cur.cell)
	var src_frame: int = int(src[cell]) - 1
	for i in th.rects.size():
		var rr: Array = th.rects[i]
		var rect := Rect2(ox + rr[0], oy + 4 + rr[1], rr[2], rr[3])
		var stv: String = th.status[i]
		var lab := str(i + 1)
		var col := GOOD
		match stv:
			"doppelt":
				draw_rect(rect, Color(0.06, 0.07, 0.11, 0.62))
				lab = "=%d" % (i - 3)
				col = BAD
			"seite":
				draw_rect(rect, Color(0.06, 0.07, 0.11, 0.55))
				draw_line(rect.position + Vector2(4, 8), rect.end - Vector2(4, 8), BAD, 2.0, true)
				draw_line(Vector2(rect.end.x - 4, rect.position.y + 8), Vector2(rect.position.x + 4, rect.end.y - 8), BAD, 2.0, true)
				lab = "Seite"
				col = BAD
			"atem":
				draw_rect(rect, Color(0.06, 0.07, 0.11, 0.55))
				lab = "–"
				col = Color(0.55, 0.58, 0.66)
			"koerper":
				lab = "Körper"
			"lid":
				lab = "Lid"
		var lw := text_w(lab, 10)
		text(Vector2(rect.position.x + rect.size.x / 2 - lw / 2, oy + 4 + 64 + 13), lab, 10, col)
		var shown: bool = i == src_frame or (anim == "idle" and cell >= 3 and i == 0)
		if shown:
			var hb := StyleBoxFlat.new()
			hb.draw_center = false
			hb.set_border_width_all(2)
			hb.border_color = ACCENT
			hb.set_corner_radius_all(3)
			draw_style_box(hb, rect.grow(2))
	# Vergleich roh / korrigiert: Grundlinie, Kopflinie (Seitenansichten), Beschriftung
	var gl := Color(0.62, 0.68, 0.82, 0.55)
	draw_line(Vector2(RAW_X - 58, BASE_Y + 0.5), Vector2(RAW_X + 58, BASE_Y + 0.5), gl, 1.0)
	draw_line(Vector2(FIX_X - 58, BASE_Y + 0.5), Vector2(FIX_X + 58, BASE_Y + 0.5), gl, 1.0)
	if anim in ["walk", "idle"]:
		var rs = meta.raw[anim].snout[0]
		var rx: float = RAW_X + (float(rs[0]) - float(meta.raw[anim].frame_w) / 2.0) * RAW_SCALE
		var fs = meta.anims[anim].snout[0]
		var fx: float = FIX_X + (float(fs[0]) - mid_x(anim)) * FIX_SCALE
		dashed(Vector2(rx, 46), Vector2(rx, BASE_Y - 4), ACCENT)
		dashed(Vector2(fx, 46), Vector2(fx, BASE_Y - 4), ACCENT)
	var l1 := "roh: sprites.py slice"
	var l2 := "korrigiert"
	text(Vector2(RAW_X - text_w(l1, 10) / 2, BASE_Y + 16), l1, 10, BAD)
	text(Vector2(FIX_X - text_w(l2, 10) / 2, BASE_Y + 16), l2, 10, GOOD)
	# Befund und Gegenmittel
	draw_line(Vector2(14, 192), Vector2(W - 14, 192), Color(0.62, 0.68, 0.82, 0.25), 1.0)
	var notes: Array = meta.notes[anim]
	text(Vector2(14, 210), "Befund", 12, BAD, fv_bold)
	text(Vector2(82, 210), notes[0], 12, Color(0.90, 0.92, 0.98))
	text(Vector2(14, 228), "Mittel", 12, GOOD, fv_bold)
	text(Vector2(82, 228), notes[1], 12, Color(0.90, 0.92, 0.98))


func dashed(a: Vector2, b: Vector2, col: Color) -> void:
	var n := int((b - a).length() / 6.0)
	for i in n:
		if i % 2 == 0:
			draw_line(a.lerp(b, float(i) / n), a.lerp(b, float(i + 1) / n), Color(col.r, col.g, col.b, 0.7), 1.0)
