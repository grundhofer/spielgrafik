extends Control
## Form 2: Auswahlliste mit Schreibmaschinen-Effekt. Links ein hoher Bildstreifen aus dem Gemälde, rechts eine
## Papierseite: der Text erscheint Zeichen für Zeichen (mit Pausen an Satzzeichen), dann gleiten die
## Antworten herein, eine wird angewählt, und die Geschichte tippt weiter.

const Typer := preload("res://scripts/typer.gd")

const INK := Color(0.17, 0.145, 0.125)
const RUST := Color(0.58, 0.27, 0.16)
const RULE := Color(0.74, 0.66, 0.50)
const HILITE := Color(0.87, 0.80, 0.66)

const X0 := 264.0
const COL_W := 350.0
const BODY_Y := 62.0
const CHOICE_Y := 140.0
const CHOICE_H := 30.0
const NEXT_Y := 240.0

const BODY := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const NEXT := "Braunes Packpapier, fest verschnürt. Auf dem Anhänger steht in krakeliger Schrift: „Leuchtturm“."

const BODY_T := 0.30
const CPS := 30.0
const CHOICE_T0 := 0.25      # nach Ende des Textes
const CHOICE_DT := 0.16
const HOVER_T := 3.55
const PICK_T := 4.35
const NEXT_T := 4.75

var t := 0.0
var serif: Font
var serif_sc: Font
var body: RichTextLabel
var body_caret: RichTextLabel
var next: RichTextLabel
var next_caret: RichTextLabel
var body_times: PackedFloat32Array
var next_times: PackedFloat32Array
var rows: Array[Dictionary] = []


func _ready() -> void:
	var cfg: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	$Picture/Harbor.position = -Vector2(cfg.crops.choice[0], cfg.crops.choice[1])
	serif = load("res://fonts/Alegreya-wght.ttf")
	var sc := FontVariation.new()
	sc.base_font = load("res://fonts/AlegreyaSC-Medium.ttf")
	sc.spacing_glyph = 1
	serif_sc = sc
	body_times = Typer.schedule(BODY, BODY_T, CPS, 0.35, 21)
	var choice_t := Typer.end_of(body_times) + CHOICE_T0
	body = _rtl(Vector2(X0, BODY_Y), 18)
	body_caret = _rtl(Vector2(X0, BODY_Y), 18)
	next = _rtl(Vector2(X0, NEXT_Y), 18)
	next_caret = _rtl(Vector2(X0, NEXT_Y), 18)
	next_times = Typer.schedule(NEXT, NEXT_T, CPS, 0.35, 22)
	for i in CHOICES.size():
		var row := Control.new()
		row.position = Vector2(X0 - 10.0, CHOICE_Y + i * CHOICE_H)
		row.size = Vector2(COL_W + 14.0, CHOICE_H)
		add_child(row)
		var hl := Panel.new()
		var sb := StyleBoxFlat.new()
		sb.bg_color = HILITE
		sb.corner_radius_top_left = 3
		sb.corner_radius_top_right = 3
		sb.corner_radius_bottom_left = 3
		sb.corner_radius_bottom_right = 3
		sb.border_width_left = 3
		sb.border_color = RUST
		hl.add_theme_stylebox_override("panel", sb)
		hl.size = Vector2(COL_W + 14.0, CHOICE_H - 2.0)
		hl.position = Vector2(0, 0)
		row.add_child(hl)
		var num := Label.new()
		num.text = "%d" % (i + 1)
		num.add_theme_font_override("font", serif_sc)
		num.add_theme_font_size_override("font_size", 17)
		num.add_theme_color_override("font_color", RUST)
		num.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		num.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		num.position = Vector2(8, 0)
		num.size = Vector2(14, CHOICE_H - 2.0)
		row.add_child(num)
		var lab := Label.new()
		lab.text = CHOICES[i]
		lab.add_theme_font_override("font", serif)
		lab.add_theme_font_size_override("font_size", 17)
		lab.add_theme_color_override("font_color", INK)
		lab.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lab.position = Vector2(32, 0)
		lab.size = Vector2(COL_W - 24.0, CHOICE_H - 2.0)
		row.add_child(lab)
		rows.append({"row": row, "hl": hl, "t": choice_t + i * CHOICE_DT})
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func _rtl(pos: Vector2, size: int) -> RichTextLabel:
	var r := RichTextLabel.new()
	r.bbcode_enabled = true
	r.fit_content = true
	r.scroll_active = false
	r.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	r.position = pos
	r.size = Vector2(COL_W, 10)
	r.add_theme_font_override("normal_font", serif)
	r.add_theme_font_size_override("normal_font_size", size)
	r.add_theme_color_override("default_color", INK)
	r.add_theme_constant_override("line_separation", 3)
	r.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(r)
	return r


func _typed(label: RichTextLabel, caret: RichTextLabel, text: String, times: PackedFloat32Array) -> void:
	## Text: ganzer Satz mit visible_characters (Zeilenumbrüche stehen von Anfang an fest).
	## Schreibmarke: derselbe Satz, unsichtbar bis auf einen Strich hinter dem letzten getippten Zeichen.
	var n := Typer.count_at(times, t)
	label.text = text
	label.visible_characters = n
	var done := n >= text.length()
	var blink := fposmod(t, 0.8) < 0.45
	if n == 0 or (done and (t > Typer.end_of(times) + 0.9 or not blink)):
		caret.text = ""
		return
	var mark := "[color=#94452a]|[/color]"
	caret.text = "[color=#00000000]%s[/color]%s[color=#00000000]%s[/color]" % [text.substr(0, n), mark, text.substr(n)]


func _update() -> void:
	_typed(body, body_caret, BODY, body_times)
	if t >= NEXT_T:
		_typed(next, next_caret, NEXT, next_times)
	else:
		next.text = ""
		next_caret.text = ""
	for i in rows.size():
		var r: Dictionary = rows[i]
		var u := clampf((t - r.t) / 0.22, 0.0, 1.0)
		var e := 1.0 - pow(1.0 - u, 3.0)
		var row: Control = r.row
		row.modulate.a = e
		row.position.x = X0 - 10.0 + round(10.0 * (1.0 - e))
		var hl: Panel = r.hl
		var h := 0.0
		if i == 1:
			h = clampf((t - HOVER_T) / 0.15, 0.0, 1.0)
		hl.modulate.a = h
		# Auswahl: kurzes Eindrücken, danach treten die anderen Antworten zurück
		if t >= PICK_T:
			var p := clampf((t - PICK_T) / 0.3, 0.0, 1.0)
			if i == 1:
				var press := 1.0 - clampf(absf(t - PICK_T - 0.06) / 0.08, 0.0, 1.0)
				hl.self_modulate = Color(1, 1, 1).lerp(Color(0.86, 0.78, 0.62), press)
			else:
				row.modulate.a = lerpf(1.0, 0.35, p)
