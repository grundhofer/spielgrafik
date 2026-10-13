extends Control
## Spieloberfläche (Textbox unten rechts) mit ui_text aus data/motif.json.
## Liegt im ScreenVP nach dem Weltbild: Welt-Looks (Film, LUT, Halbton, Palette, Bloom) lassen sie
## unberührt, der Bildschirm-Look CRT wirkt auch auf sie. Neutral gehalten (dunkles Glas, Goldlinie,
## Alegreya), damit sie unter allen Looks lesbar bleibt. Zeit t setzt main.gd (aufsummiertes delta).

const LOCATION := "HAFEN VON LORNHOLM"
const LINE := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const SELECTED := 1

const BOX := Rect2(806, 470, 446, 226)
const PAD := 22.0
const GOLD := Color(0.93, 0.76, 0.46)
const TEXT := Color(0.96, 0.93, 0.87)
const DIM := Color(0.74, 0.74, 0.76)

var t := 0.0
var serif: FontVariation
var serif_bold: FontVariation
var mono: FontVariation
var lines: PackedStringArray


func _ready() -> void:
	var ts := TextServerManager.get_primary_interface()
	var alegreya := load("res://fonts/Alegreya-wght.ttf") as FontFile
	serif = FontVariation.new()
	serif.base_font = alegreya
	serif.variation_opentype = {ts.name_to_tag("wght"): 450}
	serif_bold = FontVariation.new()
	serif_bold.base_font = alegreya
	serif_bold.variation_opentype = {ts.name_to_tag("wght"): 700}
	serif_bold.spacing_glyph = 2
	mono = FontVariation.new()
	mono.base_font = load("res://fonts/JetBrainsMono-wght.ttf") as FontFile
	mono.variation_opentype = {ts.name_to_tag("wght"): 500}
	lines = _wrap(LINE, BOX.size.x - 2.0 * PAD, 21)


func _wrap(text: String, width: float, size: int) -> PackedStringArray:
	var out := PackedStringArray()
	var cur := ""
	for w in text.split(" "):
		var cand := w if cur == "" else cur + " " + w
		if serif.get_string_size(cand, HORIZONTAL_ALIGNMENT_LEFT, -1, size).x > width and cur != "":
			out.append(cur)
			cur = w
		else:
			cur = cand
	out.append(cur)
	return out


func _draw() -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.055, 0.065, 0.10, 0.86)
	sb.set_corner_radius_all(10)
	sb.set_border_width_all(1)
	sb.border_color = Color(GOLD, 0.55)
	sb.shadow_color = Color(0, 0, 0, 0.35)
	sb.shadow_size = 10
	sb.anti_aliasing = true
	draw_style_box(sb, BOX)

	var x := BOX.position.x + PAD
	var y := BOX.position.y + PAD + 13.0
	draw_string(serif_bold, Vector2(x, y), LOCATION, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, GOLD)
	y += 11.0
	draw_line(Vector2(x, y), Vector2(BOX.end.x - PAD, y), Color(GOLD, 0.35), 1.0)
	y += 26.0
	for l in lines:
		draw_string(serif, Vector2(x, y), l, HORIZONTAL_ALIGNMENT_LEFT, -1, 21, TEXT)
		y += 25.0
	y += 8.0
	for i in CHOICES.size():
		var sel := i == SELECTED
		var col := TEXT if sel else DIM
		if sel:
			draw_rect(Rect2(x - 8.0, y - 17.0, BOX.size.x - 2.0 * PAD + 16.0, 24.0), Color(GOLD, 0.13))
			draw_rect(Rect2(x - 8.0, y - 17.0, 3.0, 24.0), GOLD)
		draw_string(mono, Vector2(x + 2.0, y), str(i + 1), HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(GOLD, 0.9 if sel else 0.6))
		draw_string(serif, Vector2(x + 24.0, y), CHOICES[i], HORIZONTAL_ALIGNMENT_LEFT, -1, 19, col)
		y += 26.0
	y += 6.0
	draw_string(mono, Vector2(x, y), PARSER, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(TEXT, 0.92))
	if fmod(t, 1.0) < 0.6:
		var w := mono.get_string_size(PARSER, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
		draw_rect(Rect2(x + w + 3.0, y - 13.0, 8.0, 16.0), Color(GOLD, 0.9))
