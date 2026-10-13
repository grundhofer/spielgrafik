extends Node2D
## Spielprogramm der Demo zx-spectrum. Arbeitet wie ein Spectrum-Spiel auf einem Bildschirmspeicher von 6912 Bytes
## (6144 Bitmap in der verschränkten Zeilenfolge, 768 Attribute); shaders/ula.gdshader zeigt ihn wie die Hardware.
## Ablauf: Das Bild lädt wie vom Band (Ladestreifen im Rahmen, Bitmap in Speicherreihenfolge, dann Attribute,
## etwa zehnmal schneller als echt). Danach schreibt die Hauptschleife jedes Bild neu: Wellen (Bitmap im Wasser),
## Glitzern, Laterne, Sterne (nur Attribute), Rauch und Möwen (ohne Attribut, übernehmen die Zellfarbe), Dachs
## (maskiertes Sprite, setzt INK und BRIGHT aller berührten Zellen = Attribut-Clash), Text im 32×24-Raster.
##
## Prüfschalter nach "--": --t0=<s> (Startzeit), --only=badger (nur Dachs vor schwarzem Papier),
## --only=bg (ohne Sprites), --noclash (Dachs ohne Attributwechsel, nur für Vergleiche), --border=<0..7>,
## --probe=<datei> (je Bild eine JSON-Zeile mit Pose und Position).

const FPS := 30.0
const PILOT1_END := 4         # Bildnummern des Ladeablaufs
const HEADER_END := 6
const PILOT2_END := 9
const BITMAP_END := 29        # 6144 Bytes in 20 Bildern
const ATTR_END := 33          # 768 Bytes in 4 Bildern
const GAME0 := 33             # ab hier läuft das Spiel
const FLASH_S := 0.32         # FLASH: INK und PAPER tauschen alle 16 Halbbilder bei 50 Hz

const FEET_Y := 135           # unterste Zeile der Füße (Zellzeile 16)
const SPRITE_H := 40
const WALK_START := GAME0 + 3
const POSE_FRAMES := 3        # 10 Posen/s
const STEP := 6               # Vorschub je Pose (Fersen: Kontakt 12 / 0, Durchgang 6)
const X0 := -24               # Startposition (linker Rand der Figur, ganz außerhalb)
const WALK := ["contact1", "pass1", "contact2", "pass2"]
const N_POSES := 21           # Posen bis zum letzten Kontakt (x = 96, Kopf vor freiem Wasser); danach Stehen
const BAND_INK := [4, 7, 2, 4, 7]   # Grün, Weiß, Rot, Grün, Weiß je 8 Spritezeilen

const TITLE := "Hafen von Lornholm"
const DESC := ["Die Laterne flackert im Wind. Am", "Kai wartet ein Paket auf dich."]
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "nimm paket"
const UDG := "ÄÖÜäöüß"        # Umlaute als benutzerdefinierte Zeichen ab Code 144

var t := 0.0
var t0 := 0.0
var frame := 0
var only := ""
var noclash := false
var border_game := 1          # Rahmen Blau (BORDER 1)
var probe_out: FileAccess
var mat: ShaderMaterial
var base := PackedByteArray()      # geladenes Bildschirmabbild
var scr := PackedByteArray()       # Arbeitsspeicher je Bild
var charset := PackedByteArray()
var sprites := {}
var scene := {}
var bmp_img: Image
var attr_img: Image
var border_img: Image
var bmp_tex: ImageTexture
var attr_tex: ImageTexture
var border_tex: ImageTexture
var border_lines := PackedByteArray()
var rng := RandomNumberGenerator.new()
var water_rows := []               # [y, c0, bits(PackedByteArray), period]
var header_bytes := PackedByteArray()
var lantern_attr := 0
var glint_attr := {}
var star_attr := {}


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--only="):
			only = a.substr(7)
		elif a == "--noclash":
			noclash = true
		elif a.begins_with("--border="):
			border_game = int(a.substr(9))
		elif a.begins_with("--probe="):
			probe_out = FileAccess.open(a.substr(8), FileAccess.WRITE)
	base = FileAccess.get_file_as_bytes("res://rom/harbour.scr")
	charset = FileAccess.get_file_as_bytes("res://rom/charset.bin")
	sprites = JSON.parse_string(FileAccess.get_file_as_string("res://rom/sprites.json"))
	scene = JSON.parse_string(FileAccess.get_file_as_string("res://rom/scene.json"))
	if only == "badger":
		base = PackedByteArray()
		base.resize(6912)
		for i in range(6144, 6912):
			base[i] = 0x07            # Papier Schwarz, INK Weiß
	_prepare_water()
	_prepare_header()
	rng.seed = 1982
	lantern_attr = base[6144 + int(scene["lantern_cell"][1]) * 32 + int(scene["lantern_cell"][0])]
	mat = $Screen.material
	scr = base.duplicate()
	border_lines.resize(240)
	bmp_img = Image.create_from_data(32, 192, false, Image.FORMAT_R8, scr.slice(0, 6144))
	attr_img = Image.create_from_data(32, 24, false, Image.FORMAT_R8, scr.slice(6144, 6912))
	border_img = Image.create_from_data(1, 240, false, Image.FORMAT_R8, border_lines)
	bmp_tex = ImageTexture.create_from_image(bmp_img)
	attr_tex = ImageTexture.create_from_image(attr_img)
	border_tex = ImageTexture.create_from_image(border_img)
	mat.set_shader_parameter("bitmap_tex", bmp_tex)
	mat.set_shader_parameter("attr_tex", attr_tex)
	mat.set_shader_parameter("border_tex", border_tex)
	t = t0
	# Zufallsfolgen vorspulen, damit --t0 dieselben Werte sieht wie ein Lauf von 0
	for i in range(int(round(t0 * FPS)) + 1):
		_tick_random(i)
	_render(int(round(t * FPS)))


func _process(delta: float) -> void:
	t += delta
	var f := int(round(t * FPS))
	if f == frame:
		return
	_tick_random(f)
	_render(f)


# ---------------------------------------------------------------- Bildschirmspeicher

static func addr(col: int, y: int) -> int:
	return ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | col


func print_at(row: int, col: int, text: String, attr: int) -> void:
	for i in text.length():
		var ch := text[i]
		var code := ch.unicode_at(0)
		var off := 0
		var u := UDG.find(ch)
		if u >= 0:
			off = (96 + u) * 8
		elif code >= 32 and code < 128:
			off = (code - 32) * 8
		var c := col + i
		if c > 31:
			return
		for k in 8:
			scr[addr(c, row * 8 + k)] = charset[off + k]
		scr[6144 + row * 32 + c] = attr


# ---------------------------------------------------------------- Laden vom Band

func _prepare_header() -> void:
	# Kopfblock einer Bytes-Datei: Flag, Typ 3, Name (10), Länge 6912, Start 16384, Parameter 2, Prüfsumme
	var name := "lornholm  "
	header_bytes.append(0x00)
	header_bytes.append(3)
	for i in 10:
		header_bytes.append(name.unicode_at(i))
	for v in [0x00, 0x1B, 0x00, 0x40, 0x00, 0x80]:
		header_bytes.append(v)
	var x := 0
	for v in header_bytes:
		x ^= v
	header_bytes.append(x)


func _stripes_pilot(f: int) -> void:
	# Leitton: Halbwelle 2168 T-Takte, eine Bildzeile 224 T, ein Bild 312 Zeilen -> Streifen wandern
	for line in 240:
		var tt := (f * 312 + line) * 224
		border_lines[line] = 2 if (tt / 2168) % 2 == 0 else 5


func _stripes_data(data: PackedByteArray, start_byte: int, f: int) -> void:
	# Daten: je Bit zwei Halbwellen, 855 T (0) oder 1710 T (1); Farbe wechselt je Halbwelle Blau/Gelb.
	var bit_i := start_byte * 8
	var half := 0
	var col := 1 if f % 2 == 0 else 6
	var pulse_end := 0
	var line := 0
	while line < 240:
		var tt := line * 224
		while tt >= pulse_end:
			var byte_i := (bit_i >> 3) % data.size()
			var bit := (data[byte_i] >> (7 - (bit_i & 7))) & 1
			pulse_end += 1710 if bit == 1 else 855
			col = 6 if col == 1 else 1
			half += 1
			if half % 2 == 0:
				bit_i += 1
		border_lines[line] = col
		line += 1


func _loading(f: int) -> void:
	scr.fill(0)
	for i in range(6144, 6912):
		scr[i] = 0x38                 # PAPER Weiß, INK Schwarz (Bildschirm nach LOAD "")
	if f >= HEADER_END:
		print_at(0, 0, "Bytes: lornholm", 0x38)
	if f < PILOT1_END:
		_stripes_pilot(f)
	elif f < HEADER_END:
		_stripes_data(header_bytes, (f - PILOT1_END) * 9, f)
	elif f < PILOT2_END:
		_stripes_pilot(f)
	elif f < BITMAP_END:
		var n := int((f - PILOT2_END + 1) * 6144 / (BITMAP_END - PILOT2_END))
		for i in n:
			scr[i] = base[i]
		_stripes_data(base, n, f)
	else:
		for i in 6144:
			scr[i] = base[i]
		var n2 := int((f - BITMAP_END + 1) * 768 / (ATTR_END - BITMAP_END))
		for i in n2:
			scr[6144 + i] = base[6144 + i]
		_stripes_data(base, 6144 + n2, f)


# ---------------------------------------------------------------- Umgebung

func _prepare_water() -> void:
	var by_row := {}
	for cell in scene["water_cells"]:
		var cy := int(cell[1])
		if not by_row.has(cy):
			by_row[cy] = []
		by_row[cy].append(int(cell[0]))
	for cy in by_row:
		var cols: Array = by_row[cy]
		cols.sort()
		var runs := []
		var start: int = cols[0]
		var prev: int = cols[0]
		for c in cols.slice(1):
			if c != prev + 1:
				runs.append([start, prev])
				start = c
			prev = c
		runs.append([start, prev])
		for run in runs:
			for k in 8:
				var y: int = cy * 8 + k
				var bits := PackedByteArray()
				var any := false
				for c in range(run[0], run[1] + 1):
					var v := base[addr(c, y)]
					for b in 8:
						var on := (v >> (7 - b)) & 1
						bits.append(on)
						any = any or on == 1
				if any:
					water_rows.append([y, run[0], bits, [4, 6, 5, 8][y % 4]])


func _water(f: int) -> void:
	for wr in water_rows:
		var y: int = wr[0]
		var c0: int = wr[1]
		var bits: PackedByteArray = wr[2]
		var n := bits.size()
		var off: int = (f / int(wr[3])) % n
		for c in n / 8:
			var v := 0
			for b in 8:
				v = (v << 1) | bits[(c * 8 + b + off) % n]
			scr[addr(c0 + c, y)] = v


func _tick_random(f: int) -> void:
	# Ein fester Satz Zufallswerte je Bild (Seed 1982), auch für --t0 gleich
	if f % 2 == 0:
		var r := rng.randf()
		var ink := 6
		var bright := 1
		if r > 0.62 and r <= 0.86:
			bright = 0
		elif r > 0.86 and r <= 0.94:
			ink = 7
		elif r > 0.94:
			ink = 2
			bright = 0
		lantern_attr = (bright << 6) | (1 << 3) | ink
	if f % 4 == 0:
		for cell in scene["glint_cells"]:
			var r2 := rng.randf()
			var ink2 := 6 if r2 < 0.65 else (7 if r2 < 0.85 else 1)
			glint_attr[cell[0]] = (1 << 3) | ink2
	if f % 6 == 0:
		for cell in scene["star_cells"]:
			var r3 := rng.randf()
			var ink3 := 7 if r3 < 0.7 else (5 if r3 < 0.88 else 1)
			star_attr[cell[0]] = 0x40 | ink3


func _ambient_attrs() -> void:
	scr[6144 + int(scene["lantern_cell"][1]) * 32 + int(scene["lantern_cell"][0])] = lantern_attr
	for cx in glint_attr:
		scr[6144 + 9 * 32 + int(cx)] = glint_attr[cx]
	for cx in star_attr:
		scr[6144 + int(cx)] = star_attr[cx]


# ---------------------------------------------------------------- Sprites

func blit(shape: Dictionary, x: int, y0: int, masked: bool) -> Dictionary:
	## Zeichnet eine 32 px breite Form (Bytezeilen) an Bildschirm-x der Figur (x = linker Rand der Kunst, die in
	## der Form ab Spalte 4 beginnt). Mit Maske: Bildschirm = (Bildschirm AND NOT Maske) OR Daten, sonst OR.
	## Gibt die berührten Zellen (Schlüssel Vector2i) zurück.
	var touched := {}
	var sx := x - int(sprites["offset"])
	var col0 := floori(sx / 8.0)
	var shift := sx - col0 * 8
	var data: Array = shape["data"]
	var mask: Array = shape.get("mask", data) if masked else data
	for r in data.size():
		var y := y0 + r
		if y < 0 or y > 191:
			continue
		var d: Array = data[r]
		var m: Array = mask[r]
		var dv := (int(d[0]) << 24) | (int(d[1]) << 16) | (int(d[2]) << 8) | int(d[3])
		var mv := (int(m[0]) << 24) | (int(m[1]) << 16) | (int(m[2]) << 8) | int(m[3])
		dv = dv << (8 - shift)
		mv = mv << (8 - shift)
		for j in 5:
			var col := col0 + j
			if col < 0 or col > 31:
				continue
			var db := (dv >> (32 - 8 * j)) & 0xFF
			var mb := (mv >> (32 - 8 * j)) & 0xFF
			if mb == 0 and db == 0:
				continue
			var a := addr(col, y)
			if masked:
				scr[a] = (scr[a] & (~mb & 0xFF)) | db
			else:
				scr[a] = scr[a] | db
			touched[Vector2i(col, y >> 3)] = true
	return touched


func badger_state(f: int) -> Array:
	var k := f - WALK_START
	if k < 0:
		return ["", X0]
	var i := k / POSE_FRAMES
	if i < N_POSES:
		return [WALK[i % 4], X0 + STEP * i]
	var xs := X0 + STEP * (N_POSES - 1)
	var s := k - N_POSES * POSE_FRAMES
	var pose := "stand"
	if (s / 9) % 2 == 1:
		pose = "flutter"
	var tt := f / FPS
	if (tt >= 4.40 and tt < 4.53) or (tt >= 5.63 and tt < 5.76):
		pose = "blink"
	return [pose, xs]


func _badger(f: int) -> void:
	var st := badger_state(f)
	var pose: String = st[0]
	if pose == "":
		return
	var x: int = st[1]
	var y0 := FEET_Y - SPRITE_H + 1
	var touched := blit(sprites["badger"][pose], x, y0, true)
	if not noclash:
		for cell in touched:
			var band: int = cell.y - (y0 >> 3)
			var ai: int = 6144 + cell.y * 32 + cell.x
			var paper := (scr[ai] >> 3) & 7
			scr[ai] = 0x40 | (paper << 3) | BAND_INK[clampi(band, 0, 4)]
	if probe_out:
		probe_out.store_line(JSON.stringify({"f": f, "pose": pose, "x": x}))


func _smoke(f: int) -> void:
	var top: Array = scene["chimney_top"]
	var g := f - GAME0 + 60            # Rauch lief schon vor dem Spielstart
	for p in range(0, 4):
		var age := (g % 15) + p * 15   # alle 0,5 s ein neues Wölkchen, 4 gleichzeitig
		var shape := mini(3, age / 15)
		var sh: Dictionary = sprites["smoke"][shape]
		var x := int(top[0]) - 2 + age / 2
		var y := int(top[1]) - int(sh["h"]) + 1 - age / 5
		blit(sh, x, y, false)


func _gulls(f: int) -> void:
	# Zwei Möwen kreisen hin und her (Pendelweg, damit sie nie in die Zellen von Leuchtturm und Schornstein
	# geraten), Flügelschlag mit 6 Bildern/s, Wippen in ganzen Pixeln
	var g := f - GAME0
	var flap: int = [0, 1, 2, 1][(g / 5) % 4]
	blit(sprites["gull"][flap], swing_x(24 + g / 2, 48, 200), 18 + [0, 0, 1, 1][(g / 5) % 4], false)
	var flap2: int = [1, 2, 1, 0][(g / 5 + 1) % 4]
	blit(sprites["gull"][flap2], swing_x(132 + g / 3, 64, 196), 24 + [1, 1, 0, 0][(g / 5) % 4], false)


static func swing_x(s: int, lo: int, hi: int) -> int:
	## s läuft gleichmäßig weiter; Ergebnis pendelt von hi nach lo und zurück (Start bei hi - s).
	var span := hi - lo
	var k := posmod(s, 2 * span)
	return hi - k if k < span else lo + (k - span)


# ---------------------------------------------------------------- Text

func _text(f: int) -> void:
	var tt := f / FPS
	print_at(0, (32 - TITLE.length()) / 2, TITLE, 0x46)
	var shown := int((tt - 1.25) * 40.0)
	var row := 18
	for line in DESC:
		if shown > 0:
			print_at(row, 0, line.substr(0, mini(shown, line.length())), 0x47)
		shown -= line.length() + 1
		row += 1
	for i in CHOICES.size():
		if tt >= 2.95 + i * 0.15:
			print_at(20 + i, 0, str(i + 1), 0x46)
			print_at(20 + i, 2, CHOICES[i], 0x45)
	if tt >= 3.45:
		var typed := clampi(int((tt - 3.85) * 10.0), 0, PARSER.length())
		var s := "> " + PARSER.substr(0, typed)
		print_at(23, 0, s, 0x47)
		print_at(23, s.length(), "L", 0xC7)   # Cursor: FLASH, wie der Eingabecursor des Rechners


# ---------------------------------------------------------------- Bild

func _render(f: int) -> void:
	frame = f
	var tt := f / FPS
	if f < ATTR_END and only == "":
		_loading(f)
	else:
		scr = base.duplicate()
		border_lines.fill(border_game)
		if only != "badger":
			_water(f)
			_ambient_attrs()
		if only == "":
			_smoke(f)
			_gulls(f)
		if only != "bg":
			_badger(f)
		if only == "":
			_text(f)
	bmp_img.set_data(32, 192, false, Image.FORMAT_R8, scr.slice(0, 6144))
	attr_img.set_data(32, 24, false, Image.FORMAT_R8, scr.slice(6144, 6912))
	border_img.set_data(1, 240, false, Image.FORMAT_R8, border_lines)
	bmp_tex.update(bmp_img)
	attr_tex.update(attr_img)
	border_tex.update(border_img)
	mat.set_shader_parameter("flash_phase", int(tt / FLASH_S) % 2 == 1)
