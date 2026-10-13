extends Node2D
## Demo apple2-hires: ein Bild-Interpreter wie in illustrierten Textabenteuern der frühen 80er.
## Schreibt Byte für Byte in einen nachgebildeten Hi-Res-Speicher (40 × 192, Bit 7 = Farbgruppe):
## erst die Linien, dann die Flächen (data/picture.json, aus scripts/build_picture.py), danach Umgebung
## (Leuchtfeuer, Laterne, Sterne, Wasserglitzern) und den Dachs als Sprite; die unteren 4 Textzeilen
## (gemischter Modus) bekommen Zeichen aus dem eigenen Zeichensatz font57 (7×8-Zellen). Der Shader wendet die
## Farbregeln an.
##
## Prüfschalter nach "--": --t0=<s> (Startzeit), --model=fringe|crisp|ideal, --only=badger (Dachs vor Schwarz),
## --probe=<datei> (je Bild: Bildnummer, Pose, x als JSON-Zeile), --text=mono (Textzeilen einfarbig, Abweichung).

const FPS := 30
const LINE_START := 3          # Bild, ab dem Linien gezogen werden
const LINE_END := 30           # 1,0 s
const FILL_END := 66           # 2,2 s: Bild fertig
const STAR_START := 66
const STAR_STEP := 2           # alle 2 Bilder ein Stern
const WALK_START := 90         # 3,0 s: Dachs tritt auf (nach dem Bildaufbau)
const WALK_FRAMES := 2         # 15 Posen/s, je 2 Punkte Vorschub
const X0 := -20                # Startspalte (links außerhalb)
const X_STOP := 44             # Ende des Laufs; steht bei X_STOP - 2 (gerade Spalte: Farben bleiben gleich).
                               # 32 Posen: der letzte Schritt ist walk4 bei x = 42 (fernes Bein steht auf Spalte 52),
                               # die Standpose an derselben Stelle behält dieses Bein und setzt das nahe vorn auf.
const FEET_Y := 158            # Bildzeile unter den Füßen
const TYPE_START := 114        # 3,8 s: Eingabe beginnt
const TYPE_STEP := 3           # 10 Zeichen/s
const CURSOR_HALF := 8         # Cursor blinkt mit 1,9 Hz

const WALK := ["walk1", "walk2", "walk3", "walk4"]
const TEXT := [
	"HAFEN VON LORNHOLM. DIE LATERNE FLACKERT",
	"IM WIND. AM KAI WARTET EIN PAKET AUF",
	"DICH.",
]
const INPUT := "NIMM PAKET"

var pic := PackedByteArray()      # Bildspeicher, wie ihn das Zeichenprogramm bisher geschrieben hat
var scr := PackedByteArray()      # angezeigter Speicher (Bild + Umgebung + Sprite + Text)
var writes := PackedByteArray()
var n_lines := 0
var n_fills := 0
var applied := 0
var anim := {}
var glyphs := {}
var frames := {}
var sp_w := 20
var sp_h := 27
var img: Image
var tex: ImageTexture
var frame := 0
var t := 0.0
var t0 := 0.0
var only := ""
var probe: FileAccess
var lantern_states := PackedInt32Array()
var glint_phase := PackedInt32Array()
var glint_period := PackedInt32Array()


func _ready() -> void:
	var model := 1
	var text_mono := 0
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--model="):
			model = ["fringe", "crisp", "ideal"].find(a.substr(8))
		elif a.begins_with("--only="):
			only = a.substr(7)
		elif a.begins_with("--probe="):
			probe = FileAccess.open(a.substr(8), FileAccess.WRITE)
		elif a == "--text=mono":
			text_mono = 1
	var pj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/picture.json"))
	writes = Marshalls.base64_to_raw(pj["writes"])
	n_lines = int(pj["n_line_writes"])
	n_fills = int(pj["n_fill_writes"])
	anim = pj["anim"]
	glyphs = JSON.parse_string(FileAccess.get_file_as_string("res://data/font.json"))["glyphs"]
	var sj: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/sprites.json"))
	sp_w = int(sj["width"])
	sp_h = int(sj["height"])
	frames = sj["frames"]
	pic.resize(40 * 192)
	pic.fill(0)
	# Zufall nur aus festem Seed, als Tabelle je Bild (damit --t0 dieselben Werte trifft)
	var rng := RandomNumberGenerator.new()
	rng.seed = 1979
	for i in 600:
		lantern_states.append(rng.randi_range(0, 3))
	for i in anim["glints"].size():
		glint_phase.append(rng.randi_range(0, 40))
		glint_period.append(rng.randi_range(20, 32))
	img = Image.create(40, 192, false, Image.FORMAT_R8)
	tex = ImageTexture.create_from_image(img)
	var mat: ShaderMaterial = $Screen.material
	mat.set_shader_parameter("mem_tex", tex)
	mat.set_shader_parameter("model", max(model, 0))
	mat.set_shader_parameter("text_mono", text_mono)
	t = t0
	frame = int(round(t0 * FPS))
	_render()


func _process(delta: float) -> void:
	t += delta
	frame = int(round(t * FPS))
	_render()


# ---- Zeichenprogramm --------------------------------------------------------------------------------------

func _target_writes(f: int) -> int:
	if f <= LINE_START:
		return 0
	if f < LINE_END:
		return int(float(n_lines) * float(f - LINE_START) / float(LINE_END - LINE_START))
	if f < FILL_END:
		return n_lines + int(float(n_fills) * float(f - LINE_END) / float(FILL_END - LINE_END))
	return n_lines + n_fills


func _run_program(f: int) -> void:
	var target := _target_writes(f)
	while applied < target:
		var i := applied * 3
		var addr := writes[i] | (writes[i + 1] << 8)
		pic[addr] = writes[i + 2]
		applied += 1


# ---- Bitzugriff -------------------------------------------------------------------------------------------

func _set_bit(x: int, y: int, on: bool) -> void:
	if x < 0 or x > 279 or y < 0 or y > 191:
		return
	var a := y * 40 + x / 7
	var m := 1 << (x % 7)
	scr[a] = (scr[a] | m) if on else (scr[a] & ~m)


func _set_group(x: int, y: int, h: int) -> void:
	if x < 0 or x > 279:
		return
	var a := y * 40 + x / 7
	scr[a] = (scr[a] & 0x7F) | (h << 7)


# ---- Umgebung ---------------------------------------------------------------------------------------------

func _ambient(f: int) -> void:
	if f < FILL_END:
		return
	var k := f - FILL_END
	# Leuchtfeuer: 12 Bilder Blitz (Lampe weiß, zwei Strahlkanten über den Himmel), 18 Bilder glimmend (orange)
	var lit := (k % 30) < 12
	for p in anim["lamp"]:
		var x := int(p[0])
		_set_bit(x, int(p[1]), lit or x % 2 == 1)
		_set_group(x, int(p[1]), 1)
	if lit:
		for p in anim["beam"]:
			_set_bit(int(p[0]), int(p[1]), true)
	# Laterne: alle 3 Bilder ein neuer Zustand aus der Seed-Tabelle (Gelb wie gemalt, Weiß, Orange, Gelb)
	var st := lantern_states[(f / 3) % lantern_states.size()]
	if st == 1:
		for p in anim["lantern"]:
			_set_bit(int(p[0]), int(p[1]), true)
	elif st == 2:
		for p in anim["lantern"]:
			var x := int(p[0])
			_set_bit(x, int(p[1]), x % 2 == 1)
			_set_group(x, int(p[1]), 1)
	# Sterne: erscheinen nacheinander (3 Punkte = weiß mit Säumen), jeder dritte funkelt (1 Punkt = farbig)
	var n_on := mini(anim["stars"].size(), (f - STAR_START) / STAR_STEP + 1)
	for i in n_on:
		var s: Array = anim["stars"][i]
		var twinkle := i % 3 == 2 and ((f + i * 7) / 9) % 3 == 0
		if twinkle:
			_set_bit(int(s[0]) + 1, int(s[1]), true)
		else:
			for d in int(s[2]):
				_set_bit(int(s[0]) + d, int(s[1]), true)
	# Wasserglitzern: kurze weiße Striche, je Stelle eigener Takt (wächst 3 -> 5 -> 3 Punkte)
	for i in anim["glints"].size():
		var g: Array = anim["glints"][i]
		var ph := (f + glint_phase[i]) % glint_period[i]
		if ph < 12:
			var w := 3 if (ph < 3 or ph >= 9) else 5
			var off := 1 if w == 3 else 0
			for d in w:
				_set_bit(int(g[0]) + off + d, int(g[1]), true)


# ---- Dachs ------------------------------------------------------------------------------------------------

func _badger_state(f: int) -> Array:
	## -> [Bildname, x] oder [] (noch nicht da)
	if f < WALK_START:
		return []
	var steps := (f - WALK_START) / WALK_FRAMES
	var max_steps := (X_STOP - X0) / 2
	var tail := "a" if ((f / 4) % 2 == 0) else "b"
	if steps < max_steps:
		return [WALK[steps % 4] + "_" + tail, X0 + 2 * steps]
	tail = "a" if ((f / 6) % 2 == 0) else "b"
	return ["stand_" + tail, X0 + 2 * (max_steps - 1)]


func _draw_sprite(name: String, x0: int, y0: int) -> void:
	var fr: Dictionary = frames[name]
	var rows: Array = fr["rows"]
	var hib: Array = fr["hib"]
	for y in rows.size():
		var yy := y0 + y
		var row: String = rows[y]
		var touched := {}
		for x in row.length():
			var c := row[x]
			if c == ".":
				continue
			var xx := x0 + x
			if xx < 0 or xx > 279:
				continue
			_set_bit(xx, yy, c == "#")
			touched[xx / 7] = true
		for b in touched:
			var a: int = yy * 40 + int(b)
			scr[a] = (scr[a] & 0x7F) | (int(hib[y]) << 7)


# ---- Text (gemischter Modus: Zeilen 160–191) ---------------------------------------------------------------

func _put_char(col: int, row: int, ch: String, inverse: bool) -> void:
	var g: Array = glyphs.get(ch, glyphs[" "])
	for k in 8:
		var v := int(g[k])
		if inverse:
			v = (~v) & 0x7F
		scr[(160 + row * 8 + k) * 40 + col] = v


func _text(f: int) -> void:
	for a in range(160 * 40, 192 * 40):
		scr[a] = 0
	for r in TEXT.size():
		var line: String = TEXT[r]
		for c in line.length():
			_put_char(c, r, line[c], false)
	var typed := 0
	if f >= TYPE_START:
		typed = mini(INPUT.length(), (f - TYPE_START) / TYPE_STEP + 1)
	var prompt := ">" + INPUT.substr(0, typed)
	for c in prompt.length():
		_put_char(c, 3, prompt[c], false)
	if (f / CURSOR_HALF) % 2 == 0:
		_put_char(prompt.length(), 3, " ", true)


# ---- Bild -------------------------------------------------------------------------------------------------

func _render() -> void:
	_run_program(frame)
	scr = pic.duplicate()
	var bs := _badger_state(frame)
	if only == "badger":
		scr.fill(0)
		if bs.size() > 0:
			_draw_sprite(bs[0], bs[1], FEET_Y - sp_h)
	else:
		_ambient(frame)
		if bs.size() > 0:
			_draw_sprite(bs[0], bs[1], FEET_Y - sp_h)
		_text(frame)
	if probe:
		probe.store_line(JSON.stringify({"f": frame, "pose": bs[0] if bs.size() else "", "x": bs[1] if bs.size() else null}))
	img.set_data(40, 192, false, Image.FORMAT_R8, scr)
	tex.update(img)
