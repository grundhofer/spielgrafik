extends Node2D
## Spielprogramm der Demo c64-multicolor: liest das Speicherabbild rom/c64.json, baut daraus die Texturen des
## nachgebildeten Videochips (shaders/vic.gdshader) und schreibt jedes Bild wie eine Hauptschleife mit
## Rasterinterrupt: Farbzyklen in Bildschirm- und Farbspeicher, Text in den Bildschirmspeicher, Sprite-Register.
##
## Prüfschalter nach "--": --t0=<s> (Startzeit), --only=badger (nur Sprites des Dachses vor Hellblau),
## --only=bg (ohne Sprites), --probe=<datei> (je Bild Pose, x, Sprites je Zeile als JSON-Zeilen),
## --scarf=<Farbnummer> (Farbe der Schal-Ebene, nur für Vergleichsbilder).

const FPS := 30.0
const TEXT_ROW := 18
const WALK := ["walk1", "walk2", "walk3", "walk4"]
const STEP_PX := 6            # Vorschub je Posenwechsel (aus den Fersen der Kontakt- und Durchgangsbeine)
const POSES := 27             # Posen bis zum Stehen (letzte = Kontakt walk3, steht rechts der Bootskabine)
const WALK_START := 6         # Bild, ab dem der Dachs läuft
const X0 := -24               # Startposition (Bildschirm-x, ganz im Rahmen verborgen)
const FEET_LINE := 141        # Bildzeile der Fußsohlen

# Farbnummern
const BLACK := 0
const WHITE := 1
const RED := 2
const CYAN := 3
const BLUE := 6
const YELLOW := 7
const ORANGE := 8
const BROWN := 9
const LRED := 10
const DGREY := 11
const GREY := 12
const LGREEN := 13
const LBLUE := 14
const LGREY := 15

var rom := {}
var t := 0.0
var t0 := 0.0
var frame := 0
var only := ""
var probe_path := ""
var scarf := -1
var probe_out: FileAccess
var mat: ShaderMaterial
var screen := PackedByteArray()
var color_ram := PackedByteArray()
var cells_img: Image
var cells_tex: ImageTexture
var regs_img: Image
var regs_tex: ImageTexture
var rng := RandomNumberGenerator.new()
var lantern_col := YELLOW
var lantern_hold := 0
var stat_max_line := 0
var stat_max_sprites := 0
var stat_slot_clash := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--only="):
			only = a.substr(7)
		elif a.begins_with("--probe="):
			probe_path = a.substr(8)
		elif a.begins_with("--scarf="):
			scarf = int(a.substr(8))
	rom = JSON.parse_string(FileAccess.get_file_as_string("res://rom/c64.json"))
	rng.seed = 1982
	mat = $Screen.material
	_build_static()
	screen = Marshalls.base64_to_raw(rom["screen"])
	color_ram = Marshalls.base64_to_raw(rom["color"])
	cells_img = Image.create(40, 25, false, Image.FORMAT_RGBA8)
	cells_tex = ImageTexture.create_from_image(cells_img)
	regs_img = Image.create(16, 2, false, Image.FORMAT_RGBAF)
	regs_tex = ImageTexture.create_from_image(regs_img)
	mat.set_shader_parameter("cells_tex", cells_tex)
	mat.set_shader_parameter("sprite_regs", regs_tex)
	mat.set_shader_parameter("mc0", int(rom["mc0"]))
	mat.set_shader_parameter("mc1", int(rom["mc1"]))
	mat.set_shader_parameter("only_sprites", 1 if only == "badger" else 0)
	mat.set_shader_parameter("no_sprites", 1 if only == "bg" else 0)
	mat.set_shader_parameter("key_color", LBLUE)
	if probe_path != "":
		probe_out = FileAccess.open(probe_path, FileAccess.WRITE)
	t = t0
	# Laternen-Zufall bis t0 vorspulen (gleiches Ergebnis wie ein Lauf ab 0)
	for i in range(int(round(t0 * FPS))):
		_lantern_step()
	_tick()


func _build_static() -> void:
	var pal := Image.create(16, 1, false, Image.FORMAT_RGBA8)
	for i in 16:
		pal.set_pixel(i, 0, Color.html(rom["palette"][i]))
	mat.set_shader_parameter("palette_tex", ImageTexture.create_from_image(pal))
	# Bitmap: 8000 Bytes, Zelle für Zelle, 4 Bitpaare je Byte
	var bm := Marshalls.base64_to_raw(rom["bitmap"])
	var px := PackedByteArray()
	px.resize(160 * 200)
	for c in 1000:
		var bx: int = (c % 40) * 4
		var by: int = (c / 40) * 8
		for r in 8:
			var b: int = bm[c * 8 + r]
			for k in 4:
				px[(by + r) * 160 + bx + k] = (b >> (6 - 2 * k)) & 3
	mat.set_shader_parameter("bitmap_tex", ImageTexture.create_from_image(
		Image.create_from_data(160, 200, false, Image.FORMAT_L8, px)))
	# Zeichensatz: 256 Zeichen x 8 Zeilen, Bit 7 = linkes Pixel
	var cs := Marshalls.base64_to_raw(rom["charset"])
	var fp := PackedByteArray()
	fp.resize(8 * 2048)
	for i in 2048:
		for k in 8:
			fp[i * 8 + k] = (cs[i] >> (7 - k)) & 1
	mat.set_shader_parameter("font_tex", ImageTexture.create_from_image(
		Image.create_from_data(8, 2048, false, Image.FORMAT_L8, fp)))
	# Sprite-Formen: 64 Bytes je Form; Multicolor = 12 Bitpaare je Zeile, Hires = 24 Bits
	var sd := Marshalls.base64_to_raw(rom["sprites"])
	var n: int = rom["sprite_mc"].size()
	var sp := PackedByteArray()
	sp.resize(24 * 21 * n)
	for s in n:
		var mc: bool = rom["sprite_mc"][s]
		for y in 21:
			var bits: int = (sd[s * 64 + y * 3] << 16) | (sd[s * 64 + y * 3 + 1] << 8) | sd[s * 64 + y * 3 + 2]
			for x in 24:
				var v: int
				if mc:
					v = (bits >> (22 - 2 * (x / 2))) & 3
				else:
					v = (bits >> (23 - x)) & 1
				sp[(s * 21 + y) * 24 + x] = v
	mat.set_shader_parameter("sprite_tex", ImageTexture.create_from_image(
		Image.create_from_data(24, 21 * n, false, Image.FORMAT_L8, sp)))
	var ras := Image.create(1, 240, false, Image.FORMAT_RGBA8)
	for y in 240:
		var e: Array = rom["raster"][y]
		ras.set_pixel(0, y, Color8(int(e[0]), int(e[1]), int(e[2]), 255))
	mat.set_shader_parameter("raster_tex", ImageTexture.create_from_image(ras))


func _process(delta: float) -> void:
	t += delta
	_lantern_step()
	_tick()


func _exit_tree() -> void:
	print("HWSTAT max_sprites_je_zeile=%d max_sprites_gleichzeitig=%d slot_kollisionen=%d" % [
		stat_max_line, stat_max_sprites, stat_slot_clash])
	if probe_out:
		probe_out.close()


# ---------------------------------------------------------------- Farbzyklen ---------

func _lantern_step() -> void:
	# ein Zufallswert je Bild, fester Seed: deterministisch
	var r := rng.randf()
	if lantern_hold > 0:
		lantern_hold -= 1
		return
	if r < 0.7:
		lantern_col = YELLOW
	elif r < 0.9:
		lantern_col = WHITE
	else:
		lantern_col = LRED
	lantern_hold = 1 + int(r * 1000.0) % 4


func _lamp_phase() -> float:
	return fposmod(t - 1.5, 3.0)


func _set_slot(cell: int, slot: int, col: int) -> void:
	if slot == 3:
		color_ram[cell] = col
	elif slot == 1:
		screen[cell] = (col << 4) | (screen[cell] & 15)
	else:
		screen[cell] = (screen[cell] & 0xF0) | col


func _colour_cycles() -> void:
	var f := int(round(t * FPS))
	var warm := [YELLOW, WHITE, YELLOW, LRED, BLUE, BLUE, LRED, BLUE]
	var cold := [LBLUE, CYAN, WHITE, CYAN, LBLUE, BLUE, BLUE, BLUE]
	var star := [WHITE, WHITE, WHITE, LGREY, WHITE, WHITE, LGREY, -1, LGREY, WHITE, WHITE]
	# Leuchtfeuer: Lampe (Mitte) und Glas (beidseits) als eigene Plätze. Nie aus: Blitz Weiß/Gelb, sonst Lampe
	# Gelb und das Glas im Wechsel Orange (Strahl naht/geht) und Braun (Strahl abgewandt).
	var lp := _lamp_phase()
	var lamp := YELLOW
	var glass := BROWN
	if lp >= 0.25 and lp < 0.85:
		lamp = WHITE
		glass = YELLOW
	elif lp < 1.6 or lp >= 2.5:
		glass = ORANGE
	for e in rom["anim"]:
		var cell: int = e[0]
		var slot: int = e[1]
		var g: int = e[2]
		var cx := cell % 40
		var cy := cell / 40
		var col: int
		match g:
			1, 2:
				var ph := (cx * 5 + cy * 3 + g * 4 + f / 4) % 8
				col = warm[ph] if cy <= 8 else cold[ph]
			3:
				col = lamp
			6:
				col = glass
			4:
				col = lantern_col
			5:
				var sc: int = star[(cx * 7 + cy * 3 + f / 6) % star.size()]
				col = e[3] if sc < 0 else sc
			_:
				continue
		_set_slot(cell, slot, col)


# ---------------------------------------------------------------- Text ---------------

func _code(ch: String) -> int:
	return int(rom["codes"].get(ch, 32))


func _put(row: int, col: int, s: String, c: int, reverse := false) -> void:
	for i in s.length():
		if col + i >= 40:
			break
		var cell := row * 40 + col + i
		screen[cell] = _code(s[i]) + (128 if reverse else 0)
		color_ram[cell] = c


func _text() -> void:
	var ui: Dictionary = rom["ui"]
	for cell in range(TEXT_ROW * 40, 1000):
		screen[cell] = 32
		color_ram[cell] = WHITE
	# Ortszeile auf dem Rasterbalken (schwarz, siehe build_rom.py)
	_put(TEXT_ROW, 1, ui["location"], YELLOW)
	# Beschreibung: Schreibmaschine, 30 Zeichen/s ab 0,3 s, Cursorblock an der Schreibstelle
	var lines := ["Die Laterne flackert im Wind. Am Kai", "wartet ein Paket auf dich."]
	assert(" ".join(lines) == ui["line"])
	var n := int(max(0.0, t - 0.3) * 30.0)
	var row := TEXT_ROW + 1
	var cursor := Vector2i(-1, -1)
	for l: String in lines:
		var shown: String = l.substr(0, max(0, n))
		_put(row, 1, shown, WHITE)
		if n >= 0 and n < l.length():
			cursor = Vector2i(row, 1 + shown.length())
		n -= l.length() + 1
		row += 1
	var done: float = 0.3 + (lines[0].length() + lines[1].length() + 1) / 30.0
	# Auswahl erscheint zeilenweise
	var choices: Array = ui["choices"]
	for i in choices.size():
		if t >= done + 0.25 + 0.15 * i:
			_put(TEXT_ROW + 3 + i, 1, str(i + 1), YELLOW)
			_put(TEXT_ROW + 3 + i, 3, choices[i], LGREEN if i == 1 and t >= 5.0 else CYAN)
	# Eingabezeile
	var pstart: float = done + 1.0
	if t >= pstart:
		var prompt: String = ui["parser_prompt"]
		var k := int(clamp((t - pstart - 0.2) * 12.0, 0.0, prompt.length() - 2.0)) + 2
		_put(24, 1, prompt.substr(0, k), WHITE)
		if k >= prompt.length():
			if fmod(t - pstart, 0.8) < 0.4:
				cursor = Vector2i(24, 1 + k)
		else:
			cursor = Vector2i(24, 1 + k)
	if cursor.x >= 0:
		_put(cursor.x, cursor.y, " ", LBLUE, true)


# ---------------------------------------------------------------- Sprites ------------

func _badger_frame() -> Array:
	## Rückgabe [Bildname, Bildschirm-x]
	var f := int(round(t * FPS))
	var i := (f - WALK_START) / 3
	if f < WALK_START:
		return ["walk1", X0]
	if i < POSES:
		return [WALK[i % 4], X0 + STEP_PX * i]
	var x := X0 + STEP_PX * (POSES - 1) + 1
	var blink := (t >= 3.4 and t < 3.55) or (t >= 5.2 and t < 5.35)
	return ["blink" if blink else "stand", x]


func _sprites() -> Array:
	## Liste [slot, x, y (Chip-Koordinaten), Form, Farbe, mc, xexp, yexp, prio]
	var out := []
	var bf := _badger_frame()
	var bx: int = bf[1] + 24
	var by: int = FEET_LINE - 41 + 50
	var slot_of := {"K": 0, "R": 1, "P": 2, "M": 3}
	for p in rom["badger"][bf[0]]:
		var layer: String = p["layer"]
		var col := int(p["color"])
		if layer[0] == "R" and scarf >= 0:
			col = scarf
		out.append([slot_of[layer[0]], bx, by + int(p["dy"]), int(p["shape"]), col,
			bool(p["mc"]), false, false, false])
	if only == "badger":
		return out
	# Leuchtfeuer-Strahl (gedehnte Hires-Sprites, gelb)
	var lp := _lamp_phase()
	if lp < 1.1:
		var full := lp >= 0.25 and lp < 0.85
		out.append([5, 254 + 24, 45, int(rom["beam"][1]), YELLOW, false, true, false, false])
		if full:
			out.append([4, 206 + 24, 45, int(rom["beam"][0]), YELLOW, false, true, false, false])
	# Möwen (Hires, weiß), Flügelschlag in Schüben. Positionen aus der ganzzahligen Bildnummer: 30 px/s
	# (1 px je Bild) und 15 px/s (1 px alle 2 Bilder), Wippen in ganzen Pixeln, Wechsel alle 6 Bilder.
	var f := int(round(t * FPS))
	var flap := ["up", "mid", "down", "mid"]
	var wob := [0, 1, 2, 2, 2, 1, 0, -1, -2, -2, -2, -1]
	# Umlauf über 380 px (von Rand zu Rand), damit die Szene beliebig lange läuft
	var gulls := [[350 - posmod(88 + f, 380), 30, 0.0],
		[-30 + posmod(66 + f / 2, 380), 46 + int(wob[(f / 6) % wob.size()]), 1.3]]
	for gi in gulls.size():
		var g: Array = gulls[gi]
		var gt: float = t + g[2]
		var shape := "mid"
		if fmod(gt, 2.4) < 1.2:
			shape = flap[int(gt * 6.0) % 4]
		out.append([4 + gi, int(g[0]) + 24, int(g[1]) + 50, int(rom["gull"][shape]), WHITE,
			false, false, false, false])
	# Rauch: alle 18 Bilder (0,6 s) ein Wölkchen, lebt 72 Bilder, also 4 gleichzeitig. Klein direkt über dem
	# Schornstein (oberste Mauerzeile 10), wächst beim Wegtreiben; schräg im Wind: 15 px/s nach rechts, 2,5 px/s
	# nach oben. Hardware-Nummern 6, 7, 2, 3: 2 und 3 trägt weiter unten der Dachs (Multiplexing, keine Überlappung).
	var smoke_slots := [6, 7, 2, 3]
	var k0 := int(floor((f - 3 - 71) / 18.0))
	for k in range(k0, k0 + 5):
		var age := f - (3 + 18 * k)
		if age < 0 or age >= 72:
			continue
		var shp := "s1"
		var h := 2
		var c := LGREY
		if age >= 54:
			shp = "s4"
			h = 4
			c = GREY
		elif age >= 30:
			shp = "s3"
			h = 4
			c = GREY
		elif age >= 12:
			shp = "s2"
			h = 3
		var x := 30 + age / 2
		var y := 9 - age / 12 - (h - 1)
		out.append([smoke_slots[posmod(k, 4)], x + 24, y + 50, int(rom["smoke"][shp]), c, true, false, false, false])
	return out


func _upload_sprites(list: Array) -> void:
	list.sort_custom(func(a, b): return a[0] < b[0] or (a[0] == b[0] and a[2] < b[2]))
	# Multiplexer-Prüfung: je Hardware-Nummer keine Überlappung in y, höchstens 8 je Zeile
	var lines := {}
	for s in list:
		var h := 42 if s[7] else 21
		for y in range(s[2], s[2] + h):
			var key := y * 8 + int(s[0])
			if lines.has(key):
				stat_slot_clash += 1
			lines[key] = true
	var per_line := {}
	for key in lines:
		per_line[key / 8] = per_line.get(key / 8, 0) + 1
	for y in per_line:
		stat_max_line = max(stat_max_line, per_line[y])
	stat_max_sprites = max(stat_max_sprites, list.size())
	for i in 16:
		if i < list.size():
			var s: Array = list[i]
			regs_img.set_pixel(i, 0, Color(s[1], s[2], s[3], s[4]))
			regs_img.set_pixel(i, 1, Color(1.0 if s[5] else 0.0, 1.0 if s[6] else 0.0,
				1.0 if s[7] else 0.0, 1.0 if s[8] else 0.0))
		else:
			regs_img.set_pixel(i, 0, Color(0, 0, 0, 0))
			regs_img.set_pixel(i, 1, Color(0, 0, 0, 0))
	regs_tex.update(regs_img)
	mat.set_shader_parameter("sprite_count", min(16, list.size()))
	if probe_out and frame > 0:
		var bf := _badger_frame()
		probe_out.store_line(JSON.stringify({"f": frame, "t": snappedf(t, 0.001), "pose": bf[0], "x": bf[1],
			"sprites": list.size(), "max_line": per_line.values().max() if per_line.size() else 0}))


func _tick() -> void:
	_colour_cycles()
	_text()
	_upload_sprites(_sprites())
	for cell in 1000:
		cells_img.set_pixel(cell % 40, cell / 40, Color8(screen[cell], color_ram[cell], 0, 255))
	cells_tex.update(cells_img)
	frame += 1
