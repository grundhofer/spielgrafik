extends Node2D
## Hafen von Lornholm auf einem Handheld mit vier Grüntönen (160x144).
## Dieses Skript spielt die Rolle des Spielprogramms: Es schreibt jedes Bild den Videospeicher (Kacheln,
## Hintergrundkarte, Window-Karte, Sprite-Tabelle OAM, Register je Bildzeile). Gezeichnet wird nur in
## shaders/ppu.gdshader, das die Grafikeinheit nachbildet. Alle Grafikdaten stammen aus rom/rom.json
## (scripts/build_rom.py). Zeit über delta aufsummiert, Zufall mit festem Seed: Aufnahmen sind reproduzierbar.

const SHADES := ["9bbc0f", "8bac0f", "306230", "0f380f"]   # Palette gb, hell -> dunkel

# Ablauf
const WALK_FPS := 15.0            # Laufbilder je Sekunde (in 30 fps: jedes Bild 2x)
const WALK_FRAMES := 40           # danach Halt (letztes Laufbild walk7, Vielfaches von 8: Halt ohne Fußrutschen)
const STAND_X := 74               # linke Rahmenkante des stehenden Dachses (links neben dem Paket am Kai)
const TURN_T := 3.2               # dreht sich zur Kamera (Vorderansicht), danach Blinzeln und Atmen
const WATER_FPS := 6.0            # Wasserkacheln: 8 Zustände
const BEAM_STEP := 0.3            # Leuchtfeuer: 8 Zustände je Umdrehung (2,4 s)
const BEAM_PHASE := 3             # Startzustand (Strahl beim Poster bei 4,7 s lang nach links)
const CLOUD_SPEED := 6.0          # Wolkenzeilen: Pixel je Sekunde (Zeilen-Scroll)
const WIN_Y := 104                # Window (Textbox) ab Zeile 104 von Bild 0 an: 5 Kachelzeilen = 40 px = 28 %
const TEXT_CPS := 20.0            # Schreibmaschinentext: Zeichen je Sekunde
const PAGE1_T := 1.0
const PAGE2_T := 2.9
const MENU_T := 5.0
const LOCATION := "Hafen von Lornholm"
const PAGES := [["Die Laterne", "flackert im Wind."], ["Am Kai wartet ein", "Paket auf dich."]]
# Auswahl: 18 Zeichen je Zeile inkl. Cursor -> höchstens 17 Zeichen je Eintrag; zwei Einträge gekürzt.
# Sichtbar sind 2 Einträge mit Leerzeile dazwischen, ▼ im Rahmen zeigt den dritten (Blättern).
const CHOICES := ["Zum Leuchtturm", "Das Paket ansehen", "Dachs ansprechen"]

var rom: Dictionary
var t := 0.0
var frame := 0

var vram_px := PackedByteArray()      # 128x192, eine Farbnummer je Pixel
var vram_img: Image
var vram_tex: ImageTexture
var vram_dirty := false
var bg_map := PackedByteArray()
var win_map := PackedByteArray()
var win_img: Image
var win_tex: ImageTexture
var oam := PackedByteArray()
var oam_img: Image
var oam_tex: ImageTexture
var lines := PackedByteArray()
var lines_img: Image
var lines_tex: ImageTexture

var anim_state := {}                  # Kanal -> aktueller Zustand
var lantern_seq := []                 # [Startzeit, Zustand] aus festem Seed
var text_shown := {}                  # Pufferkachel -> Zeichen (nur Änderungen kopieren)
var copy_queue := []                  # vorgemerkte Kachelkopien [Platz, Daten]
var text_queue := []                  # dasselbe für Textkacheln (Vorrang)
const COPY_BUDGET := 20               # Kacheln je Bild (30 fps) = 10 je VBlank bei 60 Hz, 160 Byte

# Messwerte für die Prüfung (HWSTAT im Log)
var copies_this_frame := 0
var stat := {"max_tile_copies": 0, "max_queue": 0, "max_sprites_line": 0, "max_sprites": 0, "frames": 0}

@onready var screen: ColorRect = $Screen
var probe := false                    # --sprites-only: nur der Dachs auf leerem Grund (Messung der Füße)


func _ready() -> void:
	probe = "--sprites-only" in OS.get_cmdline_user_args()
	rom = JSON.parse_string(FileAccess.get_file_as_string("res://rom/rom.json"))
	vram_px.resize(128 * 192)
	for slot in 384:
		_write_tile(slot, rom["vram"][slot])
	vram_img = Image.create_from_data(128, 192, false, Image.FORMAT_R8, vram_px)
	vram_tex = ImageTexture.create_from_image(vram_img)
	bg_map.resize(32 * 32)
	for r in 32:
		for c in 32:
			bg_map[r * 32 + c] = int(rom["bg_map"][r][c])
	var bg_img := Image.create_from_data(32, 32, false, Image.FORMAT_R8, bg_map)
	win_map.resize(32 * 32)
	win_img = Image.create_from_data(32, 32, false, Image.FORMAT_R8, win_map)
	win_tex = ImageTexture.create_from_image(win_img)
	oam.resize(40 * 4)
	oam_img = Image.create_from_data(40, 1, false, Image.FORMAT_RGBA8, oam)
	oam_tex = ImageTexture.create_from_image(oam_img)
	lines.resize(144 * 4)
	lines_img = Image.create_from_data(144, 1, false, Image.FORMAT_RGBA8, lines)
	lines_tex = ImageTexture.create_from_image(lines_img)
	var m := screen.material as ShaderMaterial
	m.set_shader_parameter("vram", vram_tex)
	m.set_shader_parameter("bg_map", ImageTexture.create_from_image(bg_img))
	m.set_shader_parameter("win_map", win_tex)
	m.set_shader_parameter("oam", oam_tex)
	m.set_shader_parameter("lines", lines_tex)
	m.set_shader_parameter("bgp", int(rom["bgp"]))
	m.set_shader_parameter("obp0", int(rom["obp0"]))
	m.set_shader_parameter("obp1", int(rom["obp1"]))
	for i in 4:
		m.set_shader_parameter("shade%d" % i, Color.html(SHADES[i]))
	for ch in rom["anims"]:
		anim_state[ch] = 0
	# Laterne: Haltezeiten 2-6 Bilder, Zustände 0-2, fester Seed
	var rng := RandomNumberGenerator.new()
	rng.seed = 1989
	var tt := 0.0
	var st := 0
	while tt < 30.0:
		lantern_seq.append([tt, st])
		tt += rng.randi_range(2, 6) / 30.0
		st = (st + rng.randi_range(1, 2)) % 3
	_build_window_frame()
	_update()


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update()


# ------------------------------------------------------------------ Videospeicher

func _write_tile(slot: int, hex: String) -> void:
	var b := hex.hex_decode()
	var ox := (slot % 16) * 8
	var oy := (slot / 16) * 8
	for y in 8:
		var lo := b[2 * y]
		var hi := b[2 * y + 1]
		for x in 8:
			var v := ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
			vram_px[(oy + y) * 128 + ox + x] = v
	vram_dirty = true


func _copy_tile(slot: int, hex: String, text := false) -> void:
	# Kachel zum Kopieren vormerken: Im VBlank ist nur Zeit für wenige Kacheln; der Rest folgt im nächsten Bild.
	# Textkacheln haben Vorrang vor den Umgebungsanimationen.
	if text:
		text_queue.append([slot, hex])
	else:
		copy_queue.append([slot, hex])


func _flush_copies() -> void:
	var n := 0
	while n < COPY_BUDGET and (text_queue.size() > 0 or copy_queue.size() > 0):
		var e: Array = text_queue.pop_front() if text_queue.size() > 0 else copy_queue.pop_front()
		_write_tile(int(e[0]), e[1])
		n += 1
	copies_this_frame = n
	stat["max_queue"] = maxi(stat["max_queue"], copy_queue.size() + text_queue.size())


func _bg_slot(id: int) -> int:
	return 256 + id if id < 128 else id


# ------------------------------------------------------------------ Bild für Bild

func _update() -> void:
	copies_this_frame = 0
	_animate_tiles()
	_update_text()
	var sprites := []                  # [x, y, Kachel, Attribute]
	_badger(sprites)
	if not probe:
		_smoke(sprites)
		_gull(sprites)
	_write_oam(sprites)
	_write_lines()
	_flush_copies()
	if vram_dirty:
		vram_img.set_data(128, 192, false, Image.FORMAT_R8, vram_px)
		vram_tex.update(vram_img)
		vram_dirty = false
	stat["max_tile_copies"] = maxi(stat["max_tile_copies"], copies_this_frame)
	stat["frames"] = frame


func _animate_tiles() -> void:
	var want := {
		"water": int(floor(t * WATER_FPS)) % 8,
		"beam": (int(floor(t / BEAM_STEP)) + BEAM_PHASE) % 8,
		"stars": int(floor(t * 2.0)) % 2,
		"lantern": _lantern_state(),
	}
	for ch in rom["anims"]:
		var s: int = want.get(ch, 0)
		if s == anim_state[ch]:
			continue
		anim_state[ch] = s
		var a: Dictionary = rom["anims"][ch]
		var slots: Array = a["slots"]
		var frames: Array = a["frames"][s]
		for i in slots.size():
			_copy_tile(int(slots[i]), frames[i])


func _lantern_state() -> int:
	var s := 0
	for e in lantern_seq:
		if e[0] <= t + 0.0001:
			s = e[1]
		else:
			break
	return s


# ------------------------------------------------------------------ Window: Rahmen und Text

func _win_id(name: String) -> int:
	return int(rom["window"]["ids"][name])


func _build_window_frame() -> void:
	for c in 20:
		for r in 5:
			var id := _win_id("blank")
			if r == 0:
				id = _win_id("tl" if c == 0 else ("tr" if c == 19 else "t"))
			elif r == 4:
				id = _win_id("bl" if c == 0 else ("br" if c == 19 else "b"))
			elif c == 0:
				id = _win_id("l")
			elif c == 19:
				id = _win_id("r")
			win_map[r * 32 + c] = id


func _set_text_rows(rows: Array) -> void:
	# rows[k] = Window-Zeile (1..3), die Pufferzeile k (18 Kacheln) zeigt; übrige Zeilen leer
	var first := _win_id("text0")
	win_map[4 * 32 + 17] = _win_id("b")
	for r in [1, 2, 3]:
		for c in 18:
			win_map[r * 32 + 1 + c] = _win_id("blank")
	for k in rows.size():
		for c in 18:
			win_map[int(rows[k]) * 32 + 1 + c] = first + k * 18 + c


func _put_char(slot_index: int, ch: String) -> void:
	if text_shown.get(slot_index, " ") == ch:
		return
	text_shown[slot_index] = ch
	var hex: String = rom["font"].get(ch, rom["font"][" "])
	_copy_tile(_bg_slot(_win_id("text0") + slot_index), hex, true)


func _show_rows(rows: Array) -> void:
	for k in 2:
		var line: String = rows[k] if k < rows.size() else ""
		for c in 18:
			_put_char(k * 18 + c, line[c] if c < line.length() else " ")


func _update_text() -> void:
	if t < PAGE1_T:
		_set_text_rows([2])
		var pad := (18 - LOCATION.length()) / 2
		_show_rows([" ".repeat(pad) + LOCATION])
	elif t < MENU_T:
		_set_text_rows([1, 3])
		var page := 0 if t < PAGE2_T else 1
		var t0 := PAGE1_T if page == 0 else PAGE2_T
		var n := int(floor((t - t0) * TEXT_CPS))
		var a: String = PAGES[page][0]
		var b: String = PAGES[page][1]
		var la := a.substr(0, clampi(n, 0, a.length()))
		var lb := b.substr(0, clampi(n - a.length(), 0, b.length()))
		if n >= a.length() + b.length() + 2 and int(floor(t * 3.0)) % 2 == 0:
			lb = lb.rpad(17) + "▼"           # weiter mit A (blinkt alle 10 Bilder)
		_show_rows([la, lb])
	else:
		_set_text_rows([1, 3])
		var sel := 0 if t < MENU_T + 0.5 else 1
		var rows := []
		for i in 2:
			rows.append(("▶" if i == sel else " ") + CHOICES[i])
		_show_rows(rows)
		win_map[4 * 32 + 17] = _win_id("b_more")   # weitere Einträge darunter
	if text_queue.size() > COPY_BUDGET:
		_set_text_rows([])                # Wechsel: Box leer zeigen, bis alle Textkacheln kopiert sind
	win_img.set_data(32, 32, false, Image.FORMAT_R8, win_map)
	win_tex.update(win_img)


# ------------------------------------------------------------------ Sprites

func _meta(sprites: Array, name: String, x: int, y: int) -> void:
	for p in rom["sprites"][name]:
		sprites.append([x + int(p[0]), y + int(p[1]), int(p[2]), 16 if int(p[3]) == 1 else 0])


func _badger(sprites: Array) -> void:
	var foot_y: int = int(rom["scene"]["feet_y"])
	var y := foot_y - int(rom["badger_foot_row"])
	var step: int = int(rom["walk_step_px"])
	var k := int(floor(t * WALK_FPS))
	if k < WALK_FRAMES:
		var x0 := STAND_X - 2 - step * (WALK_FRAMES - 1)   # letztes Laufbild: fernes Bein steht, Halt ohne Rutschen
		_meta(sprites, "walk%d" % (k % 8), x0 + step * k, y)
		return
	# Halt im Profil, dann zur Kamera drehen; vorn Blinzeln und Atmen (Oberkörper 1 px tiefer), Füße fest
	if t < TURN_T:
		_meta(sprites, "stand", STAND_X, y)
		return
	var ts := t - TURN_T
	var name := "front"
	var ph := fmod(ts, 1.6)
	if ph > 1.0 and ph < 1.4:
		name = "front_breathe"
	if (ts > 0.7 and ts < 0.84) or (ts > 2.1 and ts < 2.24):
		name = "front_blink"
	_meta(sprites, name, STAND_X, y)


func _smoke(sprites: Array) -> void:
	var cx: int = int(rom["scene"]["chimney"][0])
	var cy: int = int(rom["scene"]["chimney"][1])
	var period := 0.6
	var life := 2.1
	var n0 := int(floor((t - life) / period)) + 1
	var n1 := int(floor(t / period))
	for n in range(n0, n1 + 1):
		var age := t - n * period
		if age < 0.0 or age >= life:
			continue
		# Wind 6 px/s (1 px alle 5 Bilder), Steigen 10 px/s (1 px alle 3 Bilder): gleiche Haltezeiten bei 30 fps
		var x := cx - 4 - int(floor(age * 6.0)) + (1 if int(floor(age * 3.0 + n)) % 2 == 0 else 0)
		var yy := cy - 6 - int(floor(age * 10.0))
		var size := 0 if age < 0.8 else (1 if age < 1.5 else 2)
		_meta(sprites, "smoke%d" % size, x, yy)


func _gull(sprites: Array) -> void:
	var x := 168 - int(floor(t * 15.0))          # 15 px/s: 1 px alle 2 Bilder
	var y := 36 + int(round(3.0 * sin(t * 2.2)))
	var f := int(floor(t * 6.0)) % 2
	_meta(sprites, "gull%d" % f, x, y)


func _write_oam(sprites: Array) -> void:
	oam.fill(0)
	var count := 0
	var per_line := PackedInt32Array()
	per_line.resize(144)
	for s in sprites:
		var x: int = s[0]
		var y: int = s[1]
		if x <= -8 or x >= 160 or y <= -16 or y >= 144:
			continue                    # außerhalb: Eintrag frei lassen (Y = 0 versteckt)
		if count >= 40:
			push_warning("mehr als 40 Sprites")
			break
		oam[count * 4 + 0] = y + 16
		oam[count * 4 + 1] = x + 8
		oam[count * 4 + 2] = s[2]
		oam[count * 4 + 3] = s[3]
		for ly in range(maxi(y, 0), mini(y + 16, 144)):
			per_line[ly] += 1
		count += 1
	var mx := 0
	for v in per_line:
		mx = maxi(mx, v)
	stat["max_sprites_line"] = maxi(stat["max_sprites_line"], mx)
	stat["max_sprites"] = maxi(stat["max_sprites"], count)
	oam_img.set_data(40, 1, false, Image.FORMAT_RGBA8, oam)
	oam_tex.update(oam_img)


func _write_lines() -> void:
	var cy0: int = int(rom["scene"]["cloud_y"][0])
	var cy1: int = int(rom["scene"]["cloud_y"][1])
	var scx := int(floor(t * CLOUD_SPEED)) & 255
	var wy := WIN_Y
	var wline := 0
	for ly in 144:
		lines[ly * 4 + 0] = scx if (ly >= cy0 and ly < cy1) else 0
		lines[ly * 4 + 1] = 0
		if ly >= wy and not probe:
			lines[ly * 4 + 2] = wline     # interner Zeilenzähler des Windows
			wline += 1
		else:
			lines[ly * 4 + 2] = 255
		lines[ly * 4 + 3] = 2 if probe else 3   # Bit 0 Hintergrund, Bit 1 Sprites
	lines_img.set_data(144, 1, false, Image.FORMAT_RGBA8, lines)
	lines_tex.update(lines_img)


func _exit_tree() -> void:
	print("HWSTAT ", JSON.stringify(stat))
