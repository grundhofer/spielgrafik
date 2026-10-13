extends Control
## Form 1: klassischer Parser. Reiner Text in Festbreitenschrift, invertierte Statuszeile, Eingabezeile mit
## Blockcursor; das Protokoll scrollt nach oben weg, wenn es voll ist. Kein Bild: der Ort entsteht im Text.

const Typer := preload("res://scripts/typer.gd")

const C_TEXT := Color(0.84, 0.81, 0.74)
const C_TITLE := Color(0.97, 0.94, 0.86)
const C_INPUT := Color(0.93, 0.70, 0.36)
const C_DIM := Color(0.55, 0.53, 0.49)

const FONT_SIZE := 14
const LEFT := 22.0
const TOP := 36.0
const WIDTH := 596.0
const BOTTOM := 350.0

# Bisheriges Protokoll (vor Beginn der Aufnahme)
const HISTORY := [
	["dim", "> geh nach süden"],
	["blank", ""],
	["title", "Hafen von Lornholm"],
	["text", "Ein Steinkai mit kurzem Holzsteg, an dem zwei Fischerboote schaukeln. Auf der Felsnase im Osten blinkt der Leuchtturm, im Westen raucht der Schornstein des Hafenmeisters."],
	["text", "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."],
	["text", "Ein Dachs in grüner Weste stapft den Kai entlang."],
	["blank", ""],
]
# Eingaben: Text, Beginn des Tippens, Antwortzeilen, Punkte und Züge danach
const COMMANDS := [
	{"cmd": "nimm paket", "start": 0.9,
	 "reply": ["Genommen. Das Paket ist schwerer, als es aussieht."], "score": 10, "moves": 13},
	{"cmd": "rede mit dachs", "start": 3.25,
	 "reply": ["„Das ist für den Leuchtturmwärter“, brummt der Dachs. „Bring es hinauf, bevor die Flut kommt.“"],
	 "score": 10, "moves": 14},
]
const ENTER_DELAY := 0.35   # nach dem letzten Zeichen bis Enter
const REPLY_DELAY := 0.12   # Enter bis Antwort

var t := 0.0
var font: Font
var font_bold: Font
var cols := 70
var line_h := 19.0
var pool: Array[Label] = []
var cursor: ColorRect
var times: Array = []        # Tipp-Zeitpläne je Eingabe

@onready var status_left: Label = $Status/Left
@onready var status_right: Label = $Status/Right


func _ready() -> void:
	font = load("res://fonts/IBMPlexMono-Regular.ttf")
	font_bold = load("res://fonts/IBMPlexMono-SemiBold.ttf")
	var adv := font.get_char_size("M".unicode_at(0), FONT_SIZE).x
	cols = int(floor(WIDTH / adv))
	line_h = ceil(font.get_height(FONT_SIZE)) + 2.0
	var rows := int(floor((BOTTOM - TOP) / line_h))
	for i in rows:
		var l := Label.new()
		l.position = Vector2(LEFT, TOP + i * line_h)
		l.size = Vector2(WIDTH, line_h)
		l.add_theme_font_size_override("font_size", FONT_SIZE)
		add_child(l)
		pool.append(l)
	cursor = ColorRect.new()
	cursor.size = Vector2(adv, line_h - 3.0)
	cursor.color = C_INPUT
	add_child(cursor)
	var s := 11
	for c in COMMANDS:
		times.append(Typer.schedule(c.cmd, c.start, 9.0, 0.45, s))
		s += 1
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func wrap_text(text: String) -> PackedStringArray:
	## Zeilenumbruch für Festbreitenschrift: an Leerzeichen, höchstens cols Zeichen je Zeile.
	var out := PackedStringArray()
	var line := ""
	for w in text.split(" "):
		if line == "":
			line = w
		elif line.length() + 1 + w.length() <= cols:
			line += " " + w
		else:
			out.append(line)
			line = w
	out.append(line)
	return out


func _update() -> void:
	var lines: Array = []   # [kind, text]
	for h in HISTORY:
		for w in wrap_text(h[1]):
			lines.append([h[0], w])
	var score := 5
	var moves := 12
	var cursor_line := -1
	var cursor_col := 0
	var typing := false
	for k in COMMANDS.size():
		var c: Dictionary = COMMANDS[k]
		var tm: PackedFloat32Array = times[k]
		var n := Typer.count_at(tm, t)
		var enter := Typer.end_of(tm) + ENTER_DELAY
		var shown: String = "> " + c.cmd.substr(0, n)
		lines.append(["input", shown])
		if t < enter:
			cursor_line = lines.size() - 1
			cursor_col = shown.length()
			typing = n > 0 and n < c.cmd.length()
			break
		if t >= enter + REPLY_DELAY:
			for r in c.reply:
				for w in wrap_text(r):
					lines.append(["text", w])
			lines.append(["blank", ""])
			score = c.score
			moves = c.moves
		if k == COMMANDS.size() - 1 and t >= enter + REPLY_DELAY:
			lines.append(["input", "> "])
			cursor_line = lines.size() - 1
			cursor_col = 2
		elif t < enter + REPLY_DELAY:
			cursor_line = -1
			break
	status_right.text = "Punkte: %d   Züge: %d " % [score, moves]
	# Scrollen: nur die letzten Zeilen, die in den Bereich passen
	var first := maxi(0, lines.size() - pool.size())
	for i in pool.size():
		var l: Label = pool[i]
		var j := first + i
		if j >= lines.size():
			l.text = ""
			continue
		var kind: String = lines[j][0]
		l.text = lines[j][1]
		l.add_theme_font_override("font", font_bold if kind == "title" else font)
		l.add_theme_color_override("font_color",
				C_TITLE if kind == "title" else (C_INPUT if kind == "input" else (C_DIM if kind == "dim" else C_TEXT)))
	# Blockcursor: beim Tippen fest, sonst blinkt er (je 0,5 s an/aus)
	var vis := cursor_line >= first
	if vis and not typing:
		vis = fposmod(t, 1.0) < 0.5
	cursor.visible = vis
	if cursor_line >= first:
		var adv := font.get_char_size("M".unicode_at(0), FONT_SIZE).x
		cursor.position = Vector2(LEFT + cursor_col * adv, TOP + (cursor_line - first) * line_h + 2.0)
