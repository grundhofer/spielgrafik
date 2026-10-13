extends Node2D
## Hafen von Lornholm auf einer 8-Bit-Heimkonsole (256x240, sichtbar 256x224).
## Dieses Skript spielt das Spielprogramm: Es beschreibt jedes Bild den Speicher der Bildeinheit
## (Sprite-Tabelle OAM, Namenstabelle für den Text, Register je Bildzeile für Scroll und CHR-Bänke).
## Gezeichnet wird nur in shaders/ppu.gdshader. Alle Grafikdaten stammen aus rom/rom.json
## (scripts/build_rom.py). Zeit über delta aufsummiert, Zufall mit festem Seed: Aufnahmen sind reproduzierbar.
## Prüfschalter nach "--": --t0=<s> (Startzeit), --only=badger (nur der Dachs auf Schwarz), --only=bg (ohne
## Sprites), --probe=<datei>
## (je Bild: Sprites je Zeile, Dachs-Position und Pose als JSON-Zeile).

const WATER_FPS := 7.5            # Wasser: 8 Phasen, Bankwechsel alle 4 Bilder (bei 30 fps)
const WALK_FPS := 10.0            # Laufbilder je Sekunde (je 3 Aufnahmebilder)
const WALK_STEP := 4              # Vorschub je Laufbild in Pixeln (aus der Fußstellung, siehe badger_px.py)
const WALK_POSES := 34            # danach Halt (letztes Bild ist Durchgang a: das nahe Bein steht schon dort)
const BADGER_X0 := 252            # Start halb hinter dem rechten Rand (X > 255 wird nicht gezeigt), läuft nach links
const BADGER_Y := 134             # Oberkante des Dachses (16x24, Füße in Zeile 157 auf dem Gehweg)
const BLINKS := [3.8, 5.2]        # Blinzeln (je 4 Bilder)
const CLOUD_SPEED := 5.0          # Wolkenzeilen 28-47: Pixel je Sekunde (Zeilen-Scroll, 1 px alle 6 Bilder)
const GULL_SPEED := 15.0          # Möwen: Pixel je Sekunde (1 px alle 2 Bilder)
const LAMP_PERIOD := 2.4          # Leuchtfeuer: Blitz alle 2,4 s für 0,5 s
const LAMP_ON := 0.5
const TEXT_T := 0.4               # Schreibmaschine ab 0,4 s
const TEXT_CPS := 30.0            # Zeichen je Sekunde (ein Zeichen alle zwei Bilder bei 60 Hz)
const MENU_T := 3.9               # Auswahl ersetzt den Text
const CURSOR_MOVE_T := 5.1        # Zeiger springt auf "Das Paket ansehen"
const TITLE := "Hafen von Lornholm"
const LINES := ["Die Laterne flackert im Wind.", "Am Kai wartet ein Paket", "auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const BOX_TOP := 21               # Namenstabellenzeilen 21-28: Textfenster (64 px = 28,6 % des Bildes)

var rom: Dictionary
var t := 0.0
var frame := 0
var only_badger := false
var only_bg := false
var probe_file: FileAccess

var chr_tex: ImageTexture
var nt := PackedByteArray()
var nt_img: Image
var nt_tex: ImageTexture
var nt_dirty := true
var oam := PackedByteArray()
var oam_img: Image
var oam_tex: ImageTexture
var lines := PackedByteArray()
var lines_img: Image
var lines_tex: ImageTexture
var oam_n := 0

var font: Dictionary
var title_font: Dictionary         # Glyphen 1 px tiefer (Abstand über dem Titel)
var box: Dictionary
var spr: Dictionary
var banks: Dictionary
var lantern_seq := []             # [Startzeit, Zustand]
var text_state := ""              # zuletzt geschriebener Textzustand (nur Änderungen in die Namenstabelle)
var stat := {"max_sprites_line": 0, "lines_over_8": 0, "max_sprites": 0, "frames": 0, "nt_writes_max": 0}
var nt_writes := 0

@onready var screen: ColorRect = $Screen


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		elif a == "--only=badger":
			only_badger = true
		elif a == "--only=bg":
			only_bg = true
		elif a.begins_with("--probe="):
			probe_file = FileAccess.open(a.substr(8), FileAccess.WRITE)
	rom = JSON.parse_string(FileAccess.get_file_as_string("res://rom/rom.json"))
	font = rom["font"]
	title_font = rom["title_font"]
	box = rom["box"]
	spr = rom["sprites"]
	banks = rom["banks"]
	_build_chr()
	# Namenstabellen 0 und 1 nebeneinander (senkrechte Spiegelung): 1 ist eine Kopie von 0
	nt.resize(64 * 30)
	for r in 30:
		for c in 32:
			var v := int(rom["nametable"][r][c])
			nt[r * 64 + c] = v
			nt[r * 64 + 32 + c] = v
	nt_img = Image.create_from_data(64, 30, false, Image.FORMAT_R8, nt)
	nt_tex = ImageTexture.create_from_image(nt_img)
	# Attributtabelle: 64 gepackte Bytes je Namenstabelle -> Palette je 16x16-Block
	var at := PackedByteArray()
	at.resize(32 * 15)
	for by in 15:
		for bx in 16:
			var b := int(rom["attributes"][(by >> 1) * 8 + (bx >> 1)])
			var shift := ((by & 1) * 2 + (bx & 1)) * 2
			var p := (b >> shift) & 3
			at[by * 32 + bx] = p
			at[by * 32 + 16 + bx] = p
	var at_img := Image.create_from_data(32, 15, false, Image.FORMAT_R8, at)
	var pal := PackedByteArray()
	for v in rom["palette"]:
		pal.append(int(v))
	if only_badger:
		pal[0] = 0x21                 # Messmodus: Hellblau als Grundfarbe, damit schwarze Konturen zählen
	var pal_img := Image.create_from_data(32, 1, false, Image.FORMAT_R8, pal)
	var sys := PackedByteArray()
	for h in rom["syspal"]:
		var c := Color.html(h)
		sys.append(int(round(c.r * 255.0)))
		sys.append(int(round(c.g * 255.0)))
		sys.append(int(round(c.b * 255.0)))
	var sys_img := Image.create_from_data(64, 1, false, Image.FORMAT_RGB8, sys)
	oam.resize(64 * 4)
	oam_img = Image.create_from_data(64, 1, false, Image.FORMAT_RGBA8, oam)
	oam_tex = ImageTexture.create_from_image(oam_img)
	lines.resize(224 * 3 * 4)
	lines_img = Image.create_from_data(224, 3, false, Image.FORMAT_RGBA8, lines)
	lines_tex = ImageTexture.create_from_image(lines_img)
	var m := screen.material as ShaderMaterial
	m.set_shader_parameter("chr", chr_tex)
	m.set_shader_parameter("nt", nt_tex)
	m.set_shader_parameter("attr", ImageTexture.create_from_image(at_img))
	m.set_shader_parameter("pal", ImageTexture.create_from_image(pal_img))
	m.set_shader_parameter("syspal", ImageTexture.create_from_image(sys_img))
	m.set_shader_parameter("oam", oam_tex)
	m.set_shader_parameter("lines", lines_tex)
	# Laterne: Haltezeiten 2-6 Bilder, Zustände hi/mid/lo, fester Seed
	var rng := RandomNumberGenerator.new()
	rng.seed = 1986
	var tt := -1.0
	var states := ["hi", "mid", "lo"]
	var st := 0
	while tt < 120.0:
		lantern_seq.append([tt, states[st]])
		tt += rng.randi_range(2, 6) / 30.0
		st = (st + rng.randi_range(1, 2)) % 3
		if rng.randf() < 0.45:
			st = 0                    # meist hell
	_draw_box_frame()
	_update()


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update()


func _exit_tree() -> void:
	print("HWSTAT ", JSON.stringify(stat))
	if probe_file:
		probe_file.close()


# ------------------------------------------------------------------ Musterspeicher

func _build_chr() -> void:
	var nb: int = rom["chr"].size()
	var px := PackedByteArray()
	px.resize(128 * nb * 32)
	for b in nb:
		var raw: PackedByteArray = String(rom["chr"][b]).hex_decode()
		for i in 64:
			var g := b * 64 + i
			var ox := (g % 16) * 8
			var oy := (g / 16) * 8
			for y in 8:
				var lo := raw[i * 16 + y]
				var hi := raw[i * 16 + 8 + y]
				for x in 8:
					px[(oy + y) * 128 + ox + x] = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
	chr_tex = ImageTexture.create_from_image(Image.create_from_data(128, nb * 32, false, Image.FORMAT_R8, px))


# ------------------------------------------------------------------ Namenstabelle (Textfenster)

func _nt_set(row: int, col: int, tile: int) -> void:
	if nt[row * 64 + col] != tile:
		nt[row * 64 + col] = tile
		nt[row * 64 + 32 + col] = tile
		nt_dirty = true
		nt_writes += 1


func _glyph(ch: String) -> int:
	return int(font.get(ch, font[" "]))


func _write(row: int, col: int, s: String) -> void:
	for i in s.length():
		_nt_set(row, col + i, _glyph(s[i]))


func _draw_box_frame() -> void:
	var r0 := BOX_TOP
	var r1 := BOX_TOP + 7
	for c in 32:
		_nt_set(r0, c, int(box["h_top"]))
		_nt_set(r1, c, int(box["h_bot"]))
	for r in range(r0 + 1, r1):
		_nt_set(r, 0, int(box["v_l"]))
		_nt_set(r, 31, int(box["v_r"]))
		for c in range(1, 31):
			_nt_set(r, c, _glyph(" "))
	_nt_set(r0, 0, int(box["tl"]))
	_nt_set(r0, 31, int(box["tr"]))
	_nt_set(r1, 0, int(box["bl"]))
	_nt_set(r1, 31, int(box["br"]))
	# Ortsname im oberen Rahmen
	_nt_set(r0, 2, int(box["t_l"]))
	_nt_set(r0, 3, _glyph(" "))
	for i in TITLE.length():
		_nt_set(r0, 4 + i, int(title_font.get(TITLE[i], _glyph(TITLE[i]))))
	_nt_set(r0, 4 + TITLE.length(), _glyph(" "))
	_nt_set(r0, 5 + TITLE.length(), int(box["t_r"]))


func _update_text() -> void:
	# Zustand bestimmen, nur bei Änderung schreiben (wie ein Spiel, das im VBlank wenige Bytes kopiert)
	var state := ""
	if t >= MENU_T:
		var sel := 1 if t >= CURSOR_MOVE_T else 0
		state = "menu%d" % sel
	else:
		var n := int(floor(max(0.0, t - TEXT_T) * TEXT_CPS + 0.001))
		var blink_on := (frame / 8) % 2 == 0
		state = "text%d_%s" % [n, blink_on]
	if state == text_state:
		return
	text_state = state
	for r in range(BOX_TOP + 1, BOX_TOP + 7):
		for c in range(1, 31):
			_nt_set(r, c, _glyph(" "))
	if state.begins_with("menu"):
		var sel := int(state.substr(4))
		for i in CHOICES.size():
			var row := BOX_TOP + 2 + 2 * i
			_nt_set(row, 2, _glyph("▶") if i == sel else _glyph(" "))
			_write(row, 4, CHOICES[i])
		return
	var n := int(floor(max(0.0, t - TEXT_T) * TEXT_CPS + 0.001))
	var left := n
	var done := true
	for i in LINES.size():
		var s: String = LINES[i]
		var k: int = min(left, s.length())
		_write(BOX_TOP + 2 + 2 * i, 2, s.substr(0, k))
		left -= k
		if k < s.length():
			done = false
			break
	if done and (frame / 8) % 2 == 0:
		_nt_set(BOX_TOP + 6, 30, _glyph("▼"))


# ------------------------------------------------------------------ Sprites (OAM)

func _steps(rate: float) -> int:
	# Ganze Schritte seit Start bei 'rate' je Sekunde; der kleine Zuschlag gleicht Rundungsfehler der
	# aufsummierten delta-Werte aus, damit Haltezeiten gleich bleiben (z. B. genau 6 Bilder bei 5/s)
	return int(floor(t * rate + 0.001))


func _oam_clear() -> void:
	for i in 64:
		oam[i * 4] = 0xEF                # Y >= 239: unsichtbar
		oam[i * 4 + 1] = 0
		oam[i * 4 + 2] = 0
		oam[i * 4 + 3] = 0
	oam_n = 0


func _oam_add(x: int, y: int, tile: int, attr: int) -> void:
	if oam_n >= 64 or x < 0 or x > 255 or y < -15 or y > 238:
		return
	oam[oam_n * 4] = clampi(y - 1, 0, 255)   # Sprites erscheinen eine Zeile unter ihrem Y-Wert
	oam[oam_n * 4 + 1] = tile
	oam[oam_n * 4 + 2] = attr
	oam[oam_n * 4 + 3] = x
	oam_n += 1


func _meta(list: Array, x: int, y: int, width: int = 16, flip: bool = false) -> void:
	for e in list:
		var dx := int(e[0])
		var dy := int(e[1])
		var sx := x + (width - dx - 8 if flip else dx)
		_oam_add(sx, y + dy, int(e[2]), int(e[3]) | (0x40 if flip else 0))


func _badger_pose() -> Array:
	# Rückgabe [Pose, x]
	var i := _steps(WALK_FPS)
	if i < WALK_POSES:
		var names := ["contact_a", "pass_a", "contact_b", "pass_b"]
		return [names[i % 4], BADGER_X0 - WALK_STEP * i]
	var x := BADGER_X0 - WALK_STEP * (WALK_POSES - 1)
	for b in BLINKS:
		if t >= b and t < b + 4.0 / 30.0:
			return ["stand_blink", x]
	return ["stand", x]


func _lamp_on() -> bool:
	# Blitz bei 1,2 / 3,6 / 6,0 s … für 0,5 s (Zuschlag gegen Rundungsfehler, siehe _steps)
	return fmod(t + 1.2 + 0.001, LAMP_PERIOD) < LAMP_ON


func _lantern_state() -> String:
	var s := "hi"
	for e in lantern_seq:
		if float(e[0]) <= t:
			s = e[1]
		else:
			break
	return s


func _build_oam() -> Array:
	_oam_clear()
	var pose := _badger_pose()
	_meta(spr["badger"][pose[0]], int(pose[1]), BADGER_Y, 16, true)
	if only_badger:
		return pose
	# Paket am Kai (Zeilen 8-15 des Sprites), links vom Halteplatz des Dachses
	_oam_add(98, 143, int(spr["parcel"]), 2)
	# Leuchtfeuer mit kurzen Strahlen
	var lamp_on := _lamp_on()
	var lp: Array = spr["lamp_pos"]
	_meta(spr["lamp_on"] if lamp_on else spr["lamp_off"], int(lp[0]), int(lp[1]), 8)
	if lamp_on:
		_oam_add(int(lp[0]) - 8, int(lp[1]), int(spr["lamp_ray"]), 2)
		_oam_add(int(lp[0]) + 8, int(lp[1]), int(spr["lamp_ray"]), 2)
	var lh: Array = spr["lighthouse_pos"]
	_meta(spr["lighthouse"], int(lh[0]), int(lh[1]))
	var wp: Array = spr["window_pos"]
	_meta(spr["window"]["bright"], int(wp[0]), int(wp[1]))
	var lnp: Array = spr["lantern_pos"]
	_meta(spr["lantern"][_lantern_state()], int(lnp[0]), int(lnp[1]), 8)
	# Möwen über dem Wasser (Zeilen 70-90), Flügelschlag 6 Bilder/s
	for g in 2:
		var gx := (_steps(GULL_SPEED) + g * 120 + 40) % 300 - 20
		var gy := 74 + g * 9 + int(round(sin(t * 2.0 + g) * 2.0))
		var flap := "up" if (int(floor(t * 6.0)) + g) % 2 == 0 else "down"
		if gx >= 0 and gx <= 248:
			_oam_add(gx, gy, int(spr["gull"][flap]), 3)
	# Rauch: alle 0,8 s ein Wölkchen am Schornstein, steigt 10 px/s, treibt nach rechts, wächst
	var k0 := int(floor((t + 4.0) / 0.8))
	for k in range(k0, k0 - 4, -1):
		var born := k * 0.8 - 4.0
		var age := t - born
		if age < 0.0 or age >= 3.0:
			continue
		var size := "s" if age < 0.9 else ("m" if age < 1.9 else "l")
		var sx := 9 + int(round(age * 3.0 + sin(age * 2.5) * 1.5))
		var sy := 46 - int(round(age * 10.0))
		_oam_add(sx, sy, int(spr["smoke"][size]), 3)
	return pose


# ------------------------------------------------------------------ Zeilenregister

func _build_lines() -> void:
	var phase := _steps(WATER_FPS) % int(banks["water_phases"])
	var cloud := _steps(CLOUD_SPEED) % 512
	var flags := 2 if only_badger else (1 if only_bg else 3)
	var bx: int = banks["x"]
	var wa: int = int(banks["water_anim"]) + 2 * phase
	var ws: int = banks["water_static"]
	var fo: int = banks["font"]
	var ti: int = banks["title"]
	var sp: int = banks["sprites"]
	for ly in 224:
		var line := ly + 8
		var sx := cloud if (line >= 28 and line <= 47) else 0
		var o := ly * 4
		lines[o] = sx & 255
		lines[o + 1] = (sx >> 8) & 1
		lines[o + 2] = 0
		lines[o + 3] = flags
		var b: Array
		if line < 64 or (line >= 128 and line < BOX_TOP * 8):
			b = [bx, bx + 1, bx + 2, bx + 3]
		elif line < 128:
			b = [wa, wa + 1, ws, ws + 1]
		else:
			b = [fo, fo + 1, ti, ti + 1]
		o = (224 + ly) * 4
		for i in 4:
			lines[o + i] = b[i]
		o = (448 + ly) * 4
		for i in 4:
			lines[o + i] = sp + i


# ------------------------------------------------------------------ Bild

func _update() -> void:
	nt_writes = 0
	_update_text()
	var pose := _build_oam()
	_build_lines()
	# Hardwaregrenze messen: Sprites je Zeile (die PPU zeigt nur die ersten 8)
	var per_line := PackedInt32Array()
	per_line.resize(240)
	for i in oam_n:
		var top := int(oam[i * 4]) + 1
		for y in range(top, min(top + 16, 240)):
			per_line[y] += 1
	var mx := 0
	for y in range(8, 232):
		mx = max(mx, per_line[y])
		if per_line[y] > 8:
			stat["lines_over_8"] += 1
	stat["max_sprites_line"] = max(int(stat["max_sprites_line"]), mx)
	stat["max_sprites"] = max(int(stat["max_sprites"]), oam_n)
	stat["nt_writes_max"] = max(int(stat["nt_writes_max"]), nt_writes)
	stat["frames"] += 1
	if probe_file:
		probe_file.store_line(JSON.stringify({"f": frame, "t": snappedf(t, 0.0001), "pose": pose[0],
			"x": pose[1], "max_line": mx, "oam": oam_n, "cloud": _steps(CLOUD_SPEED), "gull": _steps(GULL_SPEED),
			"water": _steps(WATER_FPS), "lamp": _lamp_on()}))
	oam_img.set_data(64, 1, false, Image.FORMAT_RGBA8, oam)
	oam_tex.update(oam_img)
	lines_img.set_data(224, 3, false, Image.FORMAT_RGBA8, lines)
	lines_tex.update(lines_img)
	if nt_dirty:
		nt_img.set_data(64, 30, false, Image.FORMAT_R8, nt)
		nt_tex.update(nt_img)
		nt_dirty = false
