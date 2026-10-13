extends Node2D
## Textmodus-Demo: GDScript schreibt jedes Bild Zeichen und Attribute in einen 80×25-Puffer (wie den
## Bildspeicher eines PC im Textmodus); der Shader textmode.gdshader spielt den Zeichengenerator.
## Alle Bewegung entsteht durch Zeichen- und Attributwechsel ganzer Zellen.

const COLS := 80
const ROWS := 25
const FPS := 30.0

# Farben (Index der 16-Farben-Palette)
const BLACK := 0
const BLUE := 1
const GREEN := 2
const CYAN := 3
const RED := 4
const MAGENTA := 5
const BROWN := 6
const LGRAY := 7
const DGRAY := 8
const LBLUE := 9
const LGREEN := 10
const LCYAN := 11
const LRED := 12
const LMAGENTA := 13
const YELLOW := 14
const WHITE := 15
const SPRITE_COLORS := {"k": 0, "b": 1, "g": 2, "c": 3, "r": 4, "m": 5, "n": 6, "l": 7,
	"d": 8, "B": 9, "G": 10, "C": 11, "R": 12, "M": 13, "y": 14, "w": 15}

# Ablauf in Aufnahmebildern (30 je Sekunde)
const WALK_START := 3          # erstes Laufbild
const WALK_HOLD := 3           # Haltezeit je Laufbild: 10 Bilder/s
const WALK_X0 := -6            # Sprite-Spalte beim ersten Laufbild (links außerhalb)
const WALK_X1 := 33            # Haltepunkt
const WALK_PHASE0 := 3         # Laufbild-Index beim ersten Schritt (so endet der Weg auf Bild 2)
const FEET_PY := 39            # Halbzeile der Fußsohle (unterste Bildzeile 19)
const TYPE_START := 6          # Beschreibung tippt ab hier, 2 Zeichen je Bild
const MENU_AT := 40
const MENU_MOVE_AT := 66
const PARSER_START := 96       # "nimm paket": 1 Zeichen je 3 Bilder
const ENTER_AT := 132          # Eingabe: Paket weg, Punkte
const TURN_AT := 135           # Dachs dreht sich zum Spieler
const TIP_AT := 141            # Gruß an die Mütze (bis TIP_AT + 12)
const WINDOW_AT := 138         # Gesprächsfenster geht auf (4 Bilder)
const WIN := Rect2i(30, 1, 20, 10)

var chars := PackedByteArray()
var attrs := PackedByteArray()
var base_chars := PackedByteArray()
var base_attrs := PackedByteArray()
var code_of := {}              # Unicode-Zeichen -> CP437-Code
var scene := {}
var sprites := {}
var sea_cells := []
var sky_set := {}
var vram_img: Image
var vram_tex: ImageTexture
var mat: ShaderMaterial
var t := 0.0
var rng := RandomNumberGenerator.new()
var lantern_state := 0
var lantern_until := 0
var no_badger := false
var isolate := false           # Messlauf: nur der Dachs auf magentafarbener Fläche
var timing := false
var conflicts := 0
var time_us := 0
var frames_done := 0

var C_FULL: int
var C_UPPER: int
var C_LOWER: int
var C_SHADE3: int
var C_SPACE: int


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a == "--no-badger":
			no_badger = true
		elif a == "--timing":
			timing = true
		elif a == "--isolate":
			isolate = true
	rng.seed = 1987
	var cp: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://fonts/cp437.json"))
	var cs: String = cp["chars"]
	for i in cs.length():
		code_of[cs[i]] = i
	C_FULL = code_of["█"]
	C_UPPER = code_of["▀"]
	C_LOWER = code_of["▄"]
	C_SHADE3 = code_of["▓"]
	C_SPACE = code_of[" "]
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://data/scene.json"))
	sprites = JSON.parse_string(FileAccess.get_file_as_string("res://data/sprites.json"))
	base_chars.resize(COLS * ROWS)
	base_attrs.resize(COLS * ROWS)
	base_chars.fill(C_SPACE)
	base_attrs.fill(attr(LGRAY, BLACK))
	var top := int(scene["pic_top"])
	var sc: Array = scene["chars"]
	var sa: Array = scene["attrs"]
	for i in sc.size():
		base_chars[top * COLS + i] = int(sc[i])
		base_attrs[top * COLS + i] = int(sa[i])
	for c in scene["sea"]:
		sea_cells.append(Vector2i(int(c[0]), int(c[1])))
	for c in scene["sky"]:
		sky_set[Vector2i(int(c[0]), int(c[1]))] = true
	# einige Sterne blinken über das Blinkbit des Attributs
	var k := 0
	for st in scene["stars"]:
		if k % 3 == 0:
			var i := int(st[1]) * COLS + int(st[0])
			base_attrs[i] = base_attrs[i] | 128
		k += 1
	# Leuchtfeuer: Lampe blinkt mit dem Blinkbit
	var lamp := Vector2i(int(scene["lamp"][0]), int(scene["lamp"][1]))
	base_attrs[lamp.y * COLS + lamp.x] = attr(YELLOW, BLACK, true)
	draw_static_ui()
	chars = base_chars.duplicate()
	attrs = base_attrs.duplicate()
	vram_img = Image.create_empty(COLS, ROWS, false, Image.FORMAT_RG8)
	vram_tex = ImageTexture.create_from_image(vram_img)
	mat = $Screen.material
	mat.set_shader_parameter("vram", vram_tex)
	render_frame(0)


func _process(delta: float) -> void:
	t += delta
	var f := int(floor(t * FPS + 0.5))
	var t0 := Time.get_ticks_usec()
	render_frame(f)
	if timing:
		time_us += Time.get_ticks_usec() - t0
		frames_done += 1
		if frames_done == 180:
			print("Rechenzeit je Bild: %.3f ms, Farbkonflikte Figur: %d" % [time_us / 180.0 / 1000.0, conflicts])


func attr(fg: int, bg: int, blink := false) -> int:
	return (fg & 15) | ((bg & 7) << 4) | (128 if blink else 0)


func put(x: int, y: int, ch: String, fg: int, bg := -1, blink := false) -> void:
	if x < 0 or x >= COLS or y < 0 or y >= ROWS:
		return
	var i := y * COLS + x
	chars[i] = code_of.get(ch, C_SPACE)
	var b: int = (attrs[i] >> 4) & 7 if bg < 0 else bg
	attrs[i] = attr(fg, b, blink)


func text(x: int, y: int, s: String, fg: int, bg := -1) -> void:
	for i in s.length():
		put(x + i, y, s[i], fg, bg)


func base_put(x: int, y: int, ch: String, fg: int, bg: int) -> void:
	var i := y * COLS + x
	base_chars[i] = code_of.get(ch, C_SPACE)
	base_attrs[i] = attr(fg, bg)


# --- Halbblöcke --------------------------------------------------------------------------------------------
func halves(i: int) -> Vector2i:
	var c := chars[i]
	var a := attrs[i]
	var fg := a & 15
	var bg := (a >> 4) & 7
	if c == C_FULL or c == C_SHADE3:
		return Vector2i(fg, fg)
	if c == C_UPPER:
		return Vector2i(fg, bg)
	if c == C_LOWER:
		return Vector2i(bg, fg)
	return Vector2i(bg, bg)


func set_px(x: int, py: int, col: int) -> void:
	var y := py >> 1
	if x < 0 or x >= COLS or y < 1 or y > 19:
		return
	var i := y * COLS + x
	var h := halves(i)
	if py & 1 == 0:
		h.x = col
	else:
		h.y = col
	var top := h.x
	var bot := h.y
	if top == bot:
		if top < 8:
			chars[i] = C_SPACE
			attrs[i] = attr(LGRAY, top)
		else:
			chars[i] = C_FULL
			attrs[i] = attr(top, BLACK)
	elif bot < 8:
		chars[i] = C_UPPER
		attrs[i] = attr(top, bot)
	elif top < 8:
		chars[i] = C_LOWER
		attrs[i] = attr(bot, top)
	else:
		# zwei helle Farben gehen nicht: die nicht gesetzte Hälfte wird abgedunkelt
		conflicts += 1
		if py & 1 == 0:
			chars[i] = C_UPPER
			attrs[i] = attr(top, bot - 8)
		else:
			chars[i] = C_LOWER
			attrs[i] = attr(bot, top - 8)


func draw_sprite(rows: Array, x: int, py: int) -> void:
	for j in rows.size():
		var row: String = rows[j]
		for i in row.length():
			var ch := row[i]
			if ch != ".":
				set_px(x + i, py + j, SPRITE_COLORS[ch])


# --- Oberfläche ---------------------------------------------------------------------------------------------
func draw_static_ui() -> void:
	for x in COLS:
		base_put(x, 0, " ", BLACK, LGRAY)
	for y in range(20, 25):
		for x in COLS:
			base_put(x, y, " ", WHITE, BLUE)
	base_put(0, 20, "╔", LCYAN, BLUE)
	base_put(79, 20, "╗", LCYAN, BLUE)
	base_put(0, 24, "╚", LCYAN, BLUE)
	base_put(79, 24, "╝", LCYAN, BLUE)
	for x in range(1, 79):
		base_put(x, 20, "═", LCYAN, BLUE)
		base_put(x, 24, "═", LCYAN, BLUE)
	for y in range(21, 24):
		base_put(0, y, "║", LCYAN, BLUE)
		base_put(79, y, "║", LCYAN, BLUE)


func draw_ui(f: int) -> void:
	var picked := f >= ENTER_AT
	text(1, 0, "Hafen von Lornholm", BLACK)
	var score := "Punkte: %d   Züge: %d" % [5 if picked else 0, 13 if picked else 12]
	text(79 - score.length() - 1, 0, score, BLACK)
	put(23, 0, "│", DGRAY)
	text(25, 0, "Abenddämmerung", DGRAY)
	# Beschreibung (getippt), nach der Eingabe die Antwort
	var line := "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich."
	if picked:
		line = "Du nimmst das Paket. Der Dachs-Kurier tippt an seine Mütze."
		text(2, 21, line.substr(0, clampi((f - ENTER_AT) * 3, 0, line.length())), WHITE)
	else:
		text(2, 21, line.substr(0, clampi((f - TYPE_START) * 2, 0, line.length())), WHITE)
	# Auswahl
	if f >= MENU_AT:
		var choices := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
		var sel := 0 if f < MENU_MOVE_AT else 1
		if picked:
			sel = -1
		var x := 2
		for k in choices.size():
			var on := k == sel
			var bg := CYAN if on else BLUE
			text(x, 22, " %d " % (k + 1), BLACK if on else YELLOW, bg)
			text(x + 3, 22, choices[k] + " ", BLACK if on else LGRAY, bg)
			x += choices[k].length() + 7
	# Parserzeile
	var cmd := "nimm paket"
	var typed := ""
	if f >= PARSER_START and not picked:
		typed = cmd.substr(0, clampi((f - PARSER_START) / 3 + 1, 0, cmd.length()))
	put(2, 23, ">", YELLOW)
	text(4, 23, typed, WHITE)
	mat.set_shader_parameter("cursor", Vector2i(4 + typed.length(), 23))


# --- Umgebung -----------------------------------------------------------------------------------------------
func draw_sea(f: int) -> void:
	var waves: Dictionary = scene["waves"]
	var glow: Dictionary = scene["glow"]
	var gx := int(scene["glow_x"])
	var speeds := {11: 14, 12: 10, 13: 8, 14: 6}
	for c in sea_cells:
		var key := str(c.y)
		var w: Dictionary = waves[key]
		var pat: String = w["pat"]
		var dir := 1 if c.y % 2 == 0 else -1
		var shift := int(f / speeds[c.y]) * dir
		var ch := pat[posmod(c.x + shift, pat.length())]
		put(c.x, c.y, ch, int(w["fg"]), BLUE)
		if glow.has(key):
			var g: Dictionary = glow[key]
			var half := int(g["half"])
			var dx := absi(c.x - gx)
			if dx <= half:
				var gp: String = g["pat"]
				var gc := gp[posmod(c.x * 7 + c.y + int(f / 5), gp.length())]
				if gc != " ":
					put(c.x, c.y, gc, YELLOW if dx < half * 0.6 else LRED, BLUE)


func draw_beam(f: int) -> void:
	var lx := int(scene["lamp"][0])
	var ly := int(scene["lamp"][1])
	var ang := TAU * float(f) / 90.0           # eine Umdrehung in 3 s
	var c := cos(ang)
	var s := sin(ang)
	if absf(c) < 0.2:
		if s > 0.0:                             # Strahl zeigt zum Betrachter: Lampe gleißt
			put(lx, ly, "█", WHITE, BLACK)
			put(lx - 1, ly, "▐", YELLOW, BLACK)
			put(lx + 1, ly, "▌", YELLOW, BLACK)
		return
	var dir := -1 if c > 0.0 else 1
	var length := int(round(absf(c) * 40.0))
	for d in range(1, length + 1):
		var x := lx + dir * (d + 1)
		var frac := float(d) / float(length)
		var ch := "═" if frac < 0.3 else ("─" if frac < 0.65 else ("-" if frac < 0.9 else "·"))
		var col := YELLOW if frac < 0.65 else (WHITE if frac < 0.9 else LGRAY)
		if sky_set.has(Vector2i(x, ly)):
			put(x, ly, ch, col)
		# Kegel: dünne Strahlen eine Zeile darüber und darunter
		if d > 3 and frac < 0.85 and (d + (1 if dir > 0 else 0)) % 2 == 0:
			for yy in [ly - 1, ly + 1]:
				if sky_set.has(Vector2i(x, yy)):
					put(x, yy, "-" if frac < 0.5 else "·", YELLOW if frac < 0.5 else BROWN)


func draw_lantern(f: int) -> void:
	var lx := int(scene["lantern"][0])
	var ly := int(scene["lantern"][1])
	if f >= lantern_until:
		lantern_state = rng.randi_range(0, 3)
		lantern_until = f + rng.randi_range(2, 5)
	var states := [["☼", YELLOW], ["☼", BROWN], ["*", YELLOW], ["¤", YELLOW]]
	var st: Array = states[lantern_state]
	put(lx, ly, st[0], st[1], BLACK)
	var dim := lantern_state == 1
	var lit := 5.0 if dim else 6.0
	var edge := lit + 2.0
	var joint: int = code_of["▐"]
	for p in scene["pool"]:
		var i := int(p[1]) * COLS + int(p[0])
		var d := float(p[2])
		if base_chars[i] == joint:
			attrs[i] = attr(LGRAY if d < lit else DGRAY, BLACK)
		elif d < lit:
			chars[i] = C_FULL
			attrs[i] = attr(LGRAY, BLACK)
		elif d < edge:
			chars[i] = C_SHADE3
			attrs[i] = attr(LGRAY, BLACK)
		else:
			chars[i] = C_FULL
			attrs[i] = attr(DGRAY, BLACK)


func draw_smoke(f: int) -> void:
	var cx := int(scene["chimney"][0])
	var cy: int = 1
	var shapes := ["o", "°", "∙", "·", "·"]
	for k in range(6):
		var born := (f - k * 12)
		if born < 0:
			continue
		var age := born % 72
		var x := cx + 2 + age / 4
		var y := cy if (age / 4 + k) % 5 != 0 else cy + 1
		var stage := mini(age / 14, shapes.size() - 1)
		if sky_set.has(Vector2i(x, y)):
			put(x, y, shapes[stage], LGRAY if stage < 2 else DGRAY)


func draw_gull(f: int) -> void:
	# zwei Möwen auf den einfarbigen Himmelszeilen (dort bleibt das Raster ungestört), Flügelschlag alle 4 Bilder
	var wings := ["v", "-", "^", "-"]
	for g in [[64, 5, 0], [78, 2, 20]]:
		var ff := f + int(g[2])
		var x := int(g[0]) - ff / 3
		if x < 0:
			continue
		var ch: String = wings[(ff / 4) % 4]
		var y := int(g[1])
		if sky_set.has(Vector2i(x, y)):
			put(x, y, ch, WHITE)


# --- Dachs --------------------------------------------------------------------------------------------------
func draw_badger(f: int) -> void:
	if no_badger:
		return
	var h := int(sprites["h"])
	var py := FEET_PY - h + 1
	var steps := WALK_X1 - WALK_X0
	var k := (f - WALK_START) / WALK_HOLD
	if f < WALK_START:
		return
	if k <= steps:
		var idx := (WALK_PHASE0 + k) % 8
		draw_sprite(sprites["walk"][idx], WALK_X0 + k, py)
	elif f < TURN_AT:
		var stand: Array = sprites["stand"]
		draw_sprite(stand[(f / 10) % 2], WALK_X1, py)
	else:
		var tip := f >= TIP_AT and f < TIP_AT + 12
		draw_sprite(sprites["front"][1 if tip else 0], WALK_X1, py)


func draw_parcel(f: int) -> void:
	# Das Paket ist ein Gegenstand, kein Teil des Raumbilds: bis zur Eingabe liegt es am Kai
	if f >= ENTER_AT:
		return
	for u in scene["parcel"]:
		var i := int(u[1]) * COLS + int(u[0])
		chars[i] = int(u[2])
		attrs[i] = int(u[3])


func draw_window(f: int) -> void:
	# Gesprächsfenster mit Bildnis, Rahmen und Schatten wie in Textmodus-Oberflächen; öffnet sich in 4 Bildern
	if f < WINDOW_AT:
		return
	var k := mini(f - WINDOW_AT + 1, 4)
	var w := maxi(2, WIN.size.x * k / 4)
	var h := maxi(2, WIN.size.y * k / 4)
	var x0 := WIN.position.x + (WIN.size.x - w) / 2
	var y0 := WIN.position.y + (WIN.size.y - h) / 2
	# Schatten: zwei Spalten rechts, eine Zeile unten; Zeichen bleiben, Farbe dunkelgrau auf schwarz
	for y in range(y0 + 1, y0 + h + 1):
		for x in [x0 + w, x0 + w + 1]:
			shade(x, y)
	for x in range(x0 + 2, x0 + w + 2):
		shade(x, y0 + h)
	for y in range(y0, y0 + h):
		for x in range(x0, x0 + w):
			put(x, y, " ", LGRAY, BLUE)
	for x in range(x0 + 1, x0 + w - 1):
		put(x, y0, "─", WHITE, BLUE)
		put(x, y0 + h - 1, "─", WHITE, BLUE)
	for y in range(y0 + 1, y0 + h - 1):
		put(x0, y, "│", WHITE, BLUE)
		put(x0 + w - 1, y, "│", WHITE, BLUE)
	put(x0, y0, "┌", WHITE, BLUE)
	put(x0 + w - 1, y0, "┐", WHITE, BLUE)
	put(x0, y0 + h - 1, "└", WHITE, BLUE)
	put(x0 + w - 1, y0 + h - 1, "┘", WHITE, BLUE)
	if k < 4:
		return
	text(x0 + 2, y0, " Dachs-Kurier ", YELLOW, BLUE)
	put(x0 + w - 4, y0, "[", WHITE, BLUE)
	put(x0 + w - 3, y0, "■", LGREEN, BLUE)
	put(x0 + w - 2, y0, "]", WHITE, BLUE)
	var blink := (f - WINDOW_AT) % 45 >= 30 and (f - WINDOW_AT) % 45 < 33
	draw_sprite(sprites["portrait"][1 if blink else 0], x0 + 1, (y0 + 1) * 2)


func shade(x: int, y: int) -> void:
	if x < 0 or x >= COLS or y < 0 or y >= ROWS:
		return
	var i := y * COLS + x
	attrs[i] = attr(DGRAY, BLACK)


# --- Bild ---------------------------------------------------------------------------------------------------
func render_frame(f: int) -> void:
	chars = base_chars.duplicate()
	attrs = base_attrs.duplicate()
	if isolate:
		chars.fill(C_SPACE)
		attrs.fill(attr(LGRAY, MAGENTA))
		draw_badger(f)
		upload(f)
		return
	draw_sea(f)
	draw_beam(f)
	draw_smoke(f)
	draw_gull(f)
	draw_lantern(f)
	draw_parcel(f)
	draw_badger(f)
	draw_window(f)
	draw_ui(f)
	upload(f)


func upload(f: int) -> void:
	var data := PackedByteArray()
	data.resize(COLS * ROWS * 2)
	for i in COLS * ROWS:
		data[i * 2] = chars[i]
		data[i * 2 + 1] = attrs[i]
	vram_img.set_data(COLS, ROWS, false, Image.FORMAT_RG8, data)
	vram_tex.update(vram_img)
	# Blinken wie auf der VGA-Karte: Zeichen ~2 Hz (7 Bilder an, 7 aus), Cursor doppelt so schnell
	mat.set_shader_parameter("blink_on", (f / 7) % 2 == 0)
	mat.set_shader_parameter("cursor_on", (f / 4) % 2 == 0)
