extends Node2D
## Videotext-Empfänger: spielt den vorberechneten „Sendestrom“ (data/stream.json) ab und dekodiert die Seite
## jedes Bild neu nach den Level-1-Regeln. Der Shader zeichnet nur, was der Decoder liefert.
##
## Pro Bild: Grundseite + Zeilen-Aktualisierungen (Himmel, Wasser, Dachs) + ein Byte für die Laterne + Kopfzeile
## (Seitennummer, Uhr, rollende Seitennummern bei der Suche) + Flash-Code in der gewählten Auswahlzeile.
## Prüfschalter nach --:  --t0=<s> (vorspulen)  --dump=<datei> (Seitenbytes je Bild schreiben)  --timing

const ROWS := 25
const COLS := 40
const FPS := 30

var stream: Dictionary
var base: Array = []
var sky: Array = []
var water: Array = []
var badger: Array = []
var t := 0.0
var t0 := 0.0
var img: Image
var tex: ImageTexture
var rng := RandomNumberGenerator.new()
var lantern_draws := 0
var lantern_code := 0x13
var dump_file: FileAccess
var timing := false
var time_sum := 0.0
var time_n := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--dump="):
			dump_file = FileAccess.open(a.substr(7), FileAccess.WRITE)
		elif a == "--timing":
			timing = true
	var f := FileAccess.open("res://data/stream.json", FileAccess.READ)
	stream = JSON.parse_string(f.get_as_text())
	base = _rows(stream["base"])
	for s in stream["sky"]["states"]:
		sky.append(_rows(s))
	for s in stream["water"]["states"]:
		water.append(_rows(s))
	for s in stream["badger"]["states"]:
		badger.append(_rows(s))
	rng.seed = int(stream["lantern"]["seed"])
	img = Image.create_empty(COLS, ROWS, false, Image.FORMAT_RGBA8)
	tex = ImageTexture.create_from_image(img)
	$Page.material.set_shader_parameter("cells", tex)


func _rows(hexrows: Array) -> Array:
	var out := []
	for h in hexrows:
		out.append(String(h).hex_decode())
	return out


func _process(delta: float) -> void:
	var t_start := Time.get_ticks_usec()
	var f := int(round((t + t0) * FPS))
	var page := _compose(f)
	_decode(page)
	tex.update(img)
	# Flash wie im SAA5050: Zähler über 64 Halbbilder (50 Hz), die ersten 16 aus = 3:1, Takt 1,28 s
	var fl: Dictionary = stream["flash"]
	var field := int(floor(f * float(fl["field_rate"]) / FPS))
	$Page.material.set_shader_parameter("flash_on", (field % int(fl["fields_per_cycle"])) >= int(fl["fields_off"]))
	if dump_file:
		var line := str(f)
		for row in page:
			line += " " + (row as PackedByteArray).hex_encode()
		dump_file.store_line(line)
	if timing:
		time_sum += (Time.get_ticks_usec() - t_start) / 1000.0
		time_n += 1
	t += delta


func _exit_tree() -> void:
	if timing and time_n > 0:
		print("TIMING Seite zusammensetzen + dekodieren: %.3f ms je Bild (%d Bilder)" % [time_sum / time_n, time_n])


# ------------------------------------------------------------------ Seite für Bild f zusammensetzen
func _compose(f: int) -> Array:
	var page := []
	for r in base:
		page.append((r as PackedByteArray).duplicate())
	var sk: Dictionary = stream["sky"]
	_put(page, sk["rows"], sky[(f / int(sk["frames_per_state"]) + int(sk["phase"])) % sky.size()])
	_put(page, stream["water"]["rows"], water[(f / int(stream["water"]["frames_per_state"])) % water.size()])
	var b: Dictionary = stream["badger"]
	var bi: int
	if f < int(b["idle_start"]):
		bi = int(b["timeline"][f])
	else:
		var k := (f - int(b["idle_start"])) / int(b["idle_frames_per_state"])
		bi = int(b["idle"][k % b["idle"].size()])
	_put(page, b["rows"], badger[bi])
	# Laterne: ein Steuerzeichen (Mosaikfarbe vor dem Glas) wechselt; Zufall mit festem Startwert
	var L: Dictionary = stream["lantern"]
	while lantern_draws <= f / int(L["frames_per_draw"]):
		var v := rng.randf()
		var codes: Array = L["codes"]
		var weights: Array = L["weights"]
		lantern_code = int(codes[codes.size() - 1])
		var acc := 0.0
		for i in codes.size():
			acc += float(weights[i])
			if v < acc:
				lantern_code = int(codes[i])
				break
		lantern_draws += 1
	page[int(L["row"])][int(L["col"])] = lantern_code
	var cf: Dictionary = stream["choice_flash"]
	if f >= int(cf["frame"]):
		page[int(cf["row"])][int(cf["col"])] = 0x08
	page[0] = _header(f)
	return page


func _put(page: Array, rows: Array, data: Array) -> void:
	for i in rows.size():
		page[int(rows[i])] = (data[i] as PackedByteArray).duplicate()


func _text(s: String) -> PackedByteArray:
	return s.to_ascii_buffer()


func _header(f: int) -> PackedByteArray:
	var h: Dictionary = stream["header"]
	var typed := "P100"
	for e in h["typed"]:
		if f >= int(e[0]):
			typed = String(e[1])
	var pg := 100
	if f >= int(h["roll_start"]):
		# Seiten des Magazins 1 laufen im Kreis (100–199); Seite 202 kommt in dieser Demo nie an
		pg = 100 + (1 + (f - int(h["roll_start"])) / int(h["roll_frames"])) % 100
	var secs := int(h["clock"][0]) * 3600 + int(h["clock"][1]) * 60 + int(h["clock"][2]) + int(floor(float(f) / FPS))
	var clock := "%02d:%02d:%02d" % [(secs / 3600) % 24, (secs / 60) % 60, secs % 60]
	var row := _text(typed.rpad(8))
	row.append(0x03)
	row.append_array(_text(String(h["service"])))
	row.append(0x07)
	row.append_array(_text("%d %s" % [pg, String(h["date"])]))
	row.append(0x03)
	row.append_array(_text(clock))
	row.resize(COLS)
	return row


# ------------------------------------------------------------------ Decoder (Level 1, wie ttxlib.py)
func _decode(page: Array) -> void:
	var data := PackedByteArray()
	data.resize(COLS * ROWS * 4)
	var r := 0
	while r < ROWS:
		var res := _decode_row(page[r])
		var cells: PackedByteArray = res[0]
		for i in COLS * 4:
			data[r * COLS * 4 + i] = cells[i]
		if res[1] and r >= 1 and r < ROWS - 1:
			# Zeile darunter zeigt die unteren Hälften; Zeichen normaler Höhe werden dort leer
			for c in COLS:
				var o := (r + 1) * COLS * 4 + c * 4
				var flags := cells[c * 4 + 2]
				if (flags >> 4) & 3 == 1:
					data[o] = cells[c * 4]
					data[o + 1] = cells[c * 4 + 1]
					data[o + 2] = (flags & 0x0F) | (2 << 4)
				else:
					data[o] = 0
					data[o + 1] = cells[c * 4 + 1]
					data[o + 2] = flags & 0x08
				data[o + 3] = 255
			r += 2
		else:
			r += 1
	img.set_data(COLS, ROWS, false, Image.FORMAT_RGBA8, data)


func _decode_row(row: PackedByteArray) -> Array:
	var out := PackedByteArray()
	out.resize(COLS * 4)
	var fg := 7
	var bg := 0
	var mosaic := false
	var sep := false
	var hold := false
	var flash := false
	var dh := false
	var held := 0
	var held_sep := false
	var has_dh := false
	for c in COLS:
		var b := row[c] & 0x7F if c < row.size() else 0x20
		var kind := 0
		var code := 0
		var csep := false
		if b < 0x20:
			# Set-At
			match b:
				0x09: flash = false
				0x0C:
					if dh:
						held = 0
						held_sep = false
					dh = false
				0x19: sep = false
				0x1A: sep = true
				0x1C: bg = 0
				0x1D: bg = fg
				0x1E: hold = true
			if hold and mosaic:
				kind = 2
				code = held
				csep = held_sep
			_cell(out, c, kind, code, csep, fg, bg, flash, dh)
			# Set-After
			if b >= 0x01 and b <= 0x07:
				if mosaic:
					held = 0
					held_sep = false
				fg = b
				mosaic = false
			elif b == 0x08:
				flash = true
			elif b == 0x0D:
				if not dh:
					held = 0
					held_sep = false
				dh = true
				has_dh = true
			elif b >= 0x11 and b <= 0x17:
				if not mosaic:
					held = 0
					held_sep = false
				fg = b - 0x10
				mosaic = true
			elif b == 0x1F:
				hold = false
		elif mosaic and (b & 0x20) != 0:
			var p := (b & 0x1F) | ((b & 0x40) >> 1)
			_cell(out, c, 2, p, sep, fg, bg, flash, dh)
			held = p
			held_sep = sep
		else:
			_cell(out, c, 1, b, false, fg, bg, flash, dh)
	return [out, has_dh]


func _cell(out: PackedByteArray, c: int, kind: int, code: int, csep: bool, fg: int, bg: int, fl: bool, dh: bool) -> void:
	out[c * 4] = code
	out[c * 4 + 1] = fg | (bg << 3)
	out[c * 4 + 2] = kind | (4 if csep else 0) | (8 if fl else 0) | ((1 if dh else 0) << 4)
	out[c * 4 + 3] = 255
