extends Control
## Beschriftung des aktiven Looks (oben links), über allen Filtern und deshalb ungefiltert: Nummer, Name,
## Kennwerte und eine Leiste mit sechs Feldern; das aktive Feld füllt sich während der Sekunde.
## Für Farb-LUT und Paletten-Reduktion zeigt ein zweites Schild das Asset selbst (LUT-Streifen, 16 Farben).
## Werte setzt main.gd: t, look, look_start, palette.

const Main := preload("res://main.gd")
const ORIGIN := Vector2(24, 22)
const W := 372.0
const ACCENT := Color(1.0, 0.74, 0.32)
const INK := Color(0.97, 0.95, 0.9)
const SUB := Color(0.70, 0.75, 0.84)

var t := 0.0
var look := 0
var look_start := 0.0
var palette := PackedVector3Array()
var mono: FontVariation
var mono_bold: FontVariation
var lut_tex: Texture2D


func _ready() -> void:
	var ts := TextServerManager.get_primary_interface()
	var base := load("res://fonts/JetBrainsMono-wght.ttf") as FontFile
	mono = FontVariation.new()
	mono.base_font = base
	mono.variation_opentype = {ts.name_to_tag("wght"): 480}
	mono_bold = FontVariation.new()
	mono_bold.base_font = base
	mono_bold.variation_opentype = {ts.name_to_tag("wght"): 760}
	lut_tex = load("res://textures/lut_kalte_nacht.png") as Texture2D


func _chip(rect: Rect2) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.035, 0.04, 0.06, 0.84)
	sb.set_corner_radius_all(8)
	sb.set_border_width_all(1)
	sb.border_color = Color(1, 1, 1, 0.14)
	sb.anti_aliasing = true
	draw_style_box(sb, rect)


func _draw() -> void:
	var n := Main.LOOKS.size()
	var name_txt := "Ohne Nachbearbeitung"
	var detail := "Rohbild der 3D-Szene"
	if look >= 0:
		name_txt = Main.LOOKS[look]["name"]
		detail = Main.LOOKS[look]["detail"]
	# Einblenden nach dem Wechsel: Name gleitet 10 px herein
	var k := clampf((t - look_start) / 0.16, 0.0, 1.0) if look_start > 0.0 else 1.0
	k = 1.0 - (1.0 - k) * (1.0 - k)
	var r := Rect2(ORIGIN, Vector2(W, 100))
	_chip(r)
	var x := ORIGIN.x + 16.0
	var head := "NACHBEARBEITUNG" if look < 0 else "NACHBEARBEITUNG · LOOK %d/%d" % [look + 1, n]
	draw_string(mono, Vector2(x, ORIGIN.y + 22.0), head, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, SUB)
	draw_string(mono_bold, Vector2(x - 10.0 * (1.0 - k), ORIGIN.y + 50.0), name_txt,
		HORIZONTAL_ALIGNMENT_LEFT, -1, 24, Color(INK, k))
	draw_string(mono, Vector2(x, ORIGIN.y + 70.0), detail, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(SUB, 0.6 + 0.4 * k))
	# Leiste: sechs Felder, aktives Feld füllt sich
	var bw := (W - 32.0 - 5.0 * 6.0) / n
	for i in n:
		var br := Rect2(x + i * (bw + 6.0), ORIGIN.y + 82.0, bw, 5.0)
		draw_rect(br, Color(1, 1, 1, 0.16))
		if i < look:
			draw_rect(br, Color(ACCENT, 0.55))
		elif i == look:
			var p := clampf((t - look_start) / Main.LOOK_TIME, 0.0, 1.0) if look_start > -5.0 else 1.0
			draw_rect(Rect2(br.position, Vector2(bw * p, 5.0)), ACCENT)
	# Asset-Schild für LUT und Palette
	if look >= 0 and Main.LOOKS[look]["world"] == 3 and lut_tex:
		var a := Rect2(ORIGIN + Vector2(0, 108), Vector2(W, 34))
		_chip(a)
		draw_texture_rect(lut_tex, Rect2(a.position + Vector2(16, 9), Vector2(W - 32.0, 16)), false)
	elif look >= 0 and Main.LOOKS[look]["world"] == 5 and palette.size() > 0:
		var a := Rect2(ORIGIN + Vector2(0, 108), Vector2(W, 34))
		_chip(a)
		var sw := (W - 32.0) / palette.size()
		for i in palette.size():
			var c := palette[i]
			draw_rect(Rect2(a.position + Vector2(16.0 + i * sw, 9), Vector2(sw - 2.0, 16)), Color(c.x, c.y, c.z))
