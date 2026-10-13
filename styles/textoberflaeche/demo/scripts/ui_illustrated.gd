extends Control
## Form 3: Bild oben, Text unten wie in den illustrierten Adventures der 80er. Das Gemälde steht als breites
## Band über dem Text; darunter laufen Ortsbeschreibung und Eingabezeile, ältere Zeilen scrollen nach oben.

const Typer := preload("res://scripts/typer.gd")

const C_TEXT := Color(0.85, 0.82, 0.76)
const C_TITLE := Color(0.86, 0.72, 0.47)
const C_PROMPT := Color(0.62, 0.60, 0.56)
const C_INPUT := Color(0.93, 0.70, 0.36)

const LEFT := 26.0
const BOTTOM := 354.0
const WIDTH := 588.0
const SIZE := 15

const LINES := [
	["title", "Hafen von Lornholm", 0.10],
	["text", "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich.", 0.28],
	["text", "Ein Dachs in grüner Weste stapft heran und bleibt neben der Laterne stehen.", 0.46],
	["blank", "", 0.55],
]
const CMD := "untersuche laterne"
const CMD_T := 3.05
const REPLY := "Eisen und Ruß. Hinter dem Glas tanzt eine kleine, zähe Flamme."

var t := 0.0
var top_y := 244.0         # Textbeginn: unter dem Bildband (Höhe aus scene.json → band_h)
var serif: Font
var italic: Font
var caps: Font
var line_h := 21.0
var pool: Array[RichTextLabel] = []
var cursor: ColorRect
var cmd_times: PackedFloat32Array


func _ready() -> void:
	var cfg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	$Picture/Harbor.position = -Vector2(cfg.crops.illustrated[0], cfg.crops.illustrated[1])
	var band: float = cfg.band_h
	$Picture.size.y = band
	$RuleDark.position.y = band
	$RuleGold.position.y = band + 5.0
	top_y = band + 10.0
	serif = load("res://fonts/Alegreya-wght.ttf")
	italic = load("res://fonts/Alegreya-Italic-wght.ttf")
	var sc := FontVariation.new()
	sc.base_font = load("res://fonts/AlegreyaSC-Medium.ttf")
	sc.spacing_glyph = 1
	caps = sc
	line_h = ceil(serif.get_height(SIZE))
	var rows := int(floor((BOTTOM - top_y) / line_h))
	for i in rows:
		var r := RichTextLabel.new()
		r.bbcode_enabled = true
		r.scroll_active = false
		r.autowrap_mode = TextServer.AUTOWRAP_OFF
		r.position = Vector2(LEFT, top_y + i * line_h)
		r.size = Vector2(WIDTH, line_h + 4.0)
		r.add_theme_font_override("normal_font", serif)
		r.add_theme_font_override("italics_font", italic)
		r.add_theme_font_override("bold_font", caps)
		r.add_theme_font_size_override("normal_font_size", SIZE)
		r.add_theme_font_size_override("italics_font_size", SIZE)
		r.add_theme_font_size_override("bold_font_size", SIZE + 1)
		r.add_theme_color_override("default_color", C_TEXT)
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(r)
		pool.append(r)
	cursor = ColorRect.new()
	cursor.size = Vector2(8, 2)
	cursor.color = C_INPUT
	add_child(cursor)
	cmd_times = Typer.schedule(CMD, CMD_T, 9.0, 0.45, 31)
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func wrap_text(text: String) -> PackedStringArray:
	var out := PackedStringArray()
	var line := ""
	for w in text.split(" "):
		var test := w if line == "" else line + " " + w
		if line != "" and serif.get_string_size(test, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x > WIDTH:
			out.append(line)
			line = w
		else:
			line = test
	out.append(line)
	return out


func hexc(c: Color) -> String:
	return "#" + c.to_html(false)


func _update() -> void:
	var lines: Array = []    # bbcode-Zeilen
	for l in LINES:
		if t < l[2]:
			break
		if l[0] == "title":
			lines.append("[b][color=%s]%s[/color][/b]" % [hexc(C_TITLE), l[1]])
		elif l[0] == "blank":
			lines.append("")
		else:
			for w in wrap_text(l[1]):
				lines.append(w)
	var prompt_vis := t >= 0.62
	var n := Typer.count_at(cmd_times, t)
	var enter := Typer.end_of(cmd_times) + 0.35
	var typed := CMD.substr(0, n)
	var cur_line := -1
	var cur_x := 0.0
	if prompt_vis:
		lines.append("[i][color=%s]Was nun?[/color][/i] [color=%s]%s[/color]" % [hexc(C_PROMPT), hexc(C_INPUT), typed])
		cur_line = lines.size() - 1
		cur_x = (italic.get_string_size("Was nun?", HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x + serif.get_string_size(" ", HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x) \
				+ serif.get_string_size(typed, HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x
		if t >= enter + 0.1:
			for w in wrap_text(REPLY):
				lines.append(w)
			lines.append("[i][color=%s]Was nun?[/color][/i] " % hexc(C_PROMPT))
			cur_line = lines.size() - 1
			cur_x = (italic.get_string_size("Was nun?", HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x + serif.get_string_size(" ", HORIZONTAL_ALIGNMENT_LEFT, -1, SIZE).x)
		elif t >= enter:
			cur_line = -1
	var first := maxi(0, lines.size() - pool.size())
	for i in pool.size():
		var j := first + i
		pool[i].text = lines[j] if j < lines.size() else ""
	var typing := n > 0 and n < CMD.length()
	cursor.visible = cur_line >= first and (typing or fposmod(t, 1.0) < 0.5)
	if cur_line >= first:
		cursor.position = Vector2(LEFT + round(cur_x) + 1.0, top_y + (cur_line - first) * line_h + line_h - 3.0)
