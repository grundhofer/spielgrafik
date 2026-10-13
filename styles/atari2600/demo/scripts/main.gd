extends Node2D
## Hafen von Lornholm auf dem Videochip der zweiten Konsolengeneration (NTSC, 160x192, 128 Farben).
## Dieses Skript spielt das „Kernel“ des Spiels: Es legt für jede der 192 Bildzeilen fest, welche Werte in den
## Registern stehen (Hintergrund- und Playfield-Farbe, 40 Playfield-Blöcke, zwei 8-Bit-Spieler, zwei Missiles,
## Ball, Positionen, Kopien). Es gibt keinen Bildspeicher; shaders/tia.gdshader zeichnet nur aus dieser Tabelle.
## Grafikdaten aus rom/rom.json (scripts/build_rom.py). Zeit über delta aufsummiert, Zufall mit festen Seeds.
##
## Zuordnung der Objekte (je Zeilenbereich wiederverwendet, wie in Bändern geschriebene Kernel):
##   Spieler 0   Rauch (Zeilen 30-69), Dachs (106-127)
##   Spieler 1   Boote, zwei Kopien (90-96), Fässer doppelt breit (118-127)
##   Missile 0   Möwe links (35-39), Glitzern (72-91), Fenster (99-105)
##   Missile 1   Möwe rechts (35-39), Masten, zwei Kopien (76-90), Laterne und Pfahl (97-127)
##   Ball        Sterne (1-21), Paket (123-127)
##   Playfield   Leuchtturm mit Lampe und Strahl, Wolken, Felsnase, Brandung, Häuschen, Kaimauer
## Playfield rechts anders als links: PF0-PF2 werden mitten in der Zeile neu geschrieben (asymmetrisch);
## COLUPF wird auf Wolken-, Häuschen- und Lampenzeilen ebenfalls in der Zeile umgeschrieben.
## Zwei Möwen fliegen in denselben Zeilen: sie teilen sich die Missiles und werden abwechselnd gezeigt
## (Flackern von Bild zu Bild, bei 30 fps sichtbar).

const LINES := 192

# Register-Indizes in der Zeilentabelle
enum {R_BK, R_PF, R_P0C, R_P1C, R_PFR, R_SPLIT, R_PFBITS, R_GRP0, R_GRP1, R_P0X, R_P1X, R_M0X, R_M1X,
	R_BLX, R_NUS0, R_NUS1, R_CTRL, R_FLAGS, NREG}
const F_REFP0 := 1
const F_REFP1 := 2
const F_ENAM0 := 4
const F_ENAM1 := 8
const F_ENABL := 16
const F_HMOVE := 32
const F_TEXT := 64

# Ablauf
const STEP_FRAMES := 3            # Laufbildwechsel alle 3 Bilder (10/s), je Wechsel 2 px Vorschub
const STEP_PX := 2
const TURN_FRAME := 108           # 3,6 s: Dachs dreht sich zur Kamera
const BEAM_FRAMES := 12           # Leuchtfeuer: 6 Zustände zu je 12 Bildern (2,4 s je Umdrehung)
const POSTER_FRAME := 166         # Skriptbild des Posters (capture.py --poster-at 0.92: Bilddatei 165 = Skriptbild 166)
const TEXT_X0 := 8
const TEXT_PITCH := 7
const LOCATION := "Hafen von Lornholm"
const LINE1 := "Die Laterne flackert im Wind."
const LINE2 := "Am Kai wartet ein Paket auf dich."
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]
const PARSER := "> nimm paket"
const TYPE_T0 := 0.3              # Schreibmaschine: Erzähltext
const TYPE_CPS := 24.0
const CHOICE_T := 3.2             # Auswahl erscheint
const CURSOR_T := 4.2             # Auswahlpfeil springt auf »Das Paket ansehen«
const PARSER_T := 4.5             # Eingabezeile wird getippt
const PARSER_CPS := 12.0

var rom: Dictionary
var lay: Dictionary
var spr: Dictionary
var t := 0.0
var frame := 0
var probe := false
var dump_frame := -1              # --dump N PFAD: Zeilentabelle von Bild N als JSON schreiben (Prüfskripte)
var dump_path := ""
var writes_line := PackedInt32Array()

var R := PackedInt64Array()       # LINES * NREG, Werte dieser Zeile
var regs := PackedByteArray()
var regs_img: Image
var regs_tex: ImageTexture
var text_px := PackedByteArray()
var text_img: Image
var text_tex: ImageTexture
var text_key := ""
var text_y0 := 136
var beam_offset := 0

var lantern_seq := []             # [Bild, Farbe]
var star_seq := {}                # Stern -> Liste [Bild, an]
var glints := []                  # {y, x, w, seq}
var wind_seq := []                # [Bild, Wind 0/1]
var reflect_seq := []             # je 5 Bilder: Bitmaske der Abendlicht-Zeilen im Meer

# Messwerte (HWSTAT im Log beim Beenden)
var stat := {"frames": 0, "max_writes": 0, "max_writes_line": -1, "lines_over_budget": 0,
	"asym_lines": 0, "reflect_lines": 0, "repeat_lines": 0, "split_lines": 0, "max_colors_line": 0,
	"reposition_visible": 0}
const WRITE_BUDGET := 13          # grobe Schätzung: 76 Takte je Zeile, 5 Takte je Schreibzugriff, Rest Schleife

@onready var screen: ColorRect = $Screen


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	probe = "--sprites-only" in args
	var di := args.find("--dump")
	if di >= 0 and di + 2 < args.size():
		dump_frame = int(args[di + 1])
		dump_path = args[di + 2]
	writes_line.resize(LINES)
	rom = JSON.parse_string(FileAccess.get_file_as_string("res://rom/rom.json"))
	lay = rom["layout"]
	spr = rom["sprites"]
	text_y0 = int(rom["text_y0"])
	R.resize(LINES * NREG)
	regs.resize(LINES * 6 * 4)
	regs_img = Image.create_from_data(LINES, 6, false, Image.FORMAT_RGBA8, regs)
	regs_tex = ImageTexture.create_from_image(regs_img)
	text_px.resize(160 * (LINES - text_y0))
	text_img = Image.create_from_data(160, LINES - text_y0, false, Image.FORMAT_R8, text_px)
	text_tex = ImageTexture.create_from_image(text_img)
	var pal := PackedByteArray()
	for h in rom["palette"]:
		var c := Color.html(h)
		pal.append_array(PackedByteArray([c.r8, c.g8, c.b8, 255]))
	var pal_img := Image.create_from_data(128, 1, false, Image.FORMAT_RGBA8, pal)
	var m := screen.material as ShaderMaterial
	m.set_shader_parameter("regs", regs_tex)
	m.set_shader_parameter("pal", ImageTexture.create_from_image(pal_img))
	m.set_shader_parameter("text", text_tex)
	m.set_shader_parameter("text_y0", text_y0)
	m.set_shader_parameter("probe", probe)
	# Leuchtfeuer so legen, dass das Posterbild mitten im Zustand 0 liegt (langer Strahl nach links)
	beam_offset = posmod(BEAM_FRAMES / 2 - POSTER_FRAME, BEAM_FRAMES * 6)
	_make_sequences()
	_update()


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update()


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE or what == NOTIFICATION_WM_CLOSE_REQUEST:
		if stat["frames"] > 0:
			print("HWSTAT " + JSON.stringify(stat))
			stat["frames"] = 0


func _exit_tree() -> void:
	if stat["frames"] > 0:
		print("HWSTAT " + JSON.stringify(stat))
		stat["frames"] = 0


# ------------------------------------------------------------------ Zufallsfolgen (feste Seeds)

func _hold_seq(seed_v: int, values: Array, min_hold: int, max_hold: int, step: int = 1) -> Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_v
	var out := []
	var f := 0
	var last := -1
	while f < 400:
		var v = values[rng.randi_range(0, values.size() - 1)]
		if values.size() > 1:
			while v == last:
				v = values[rng.randi_range(0, values.size() - 1)]
		out.append([f, v])
		last = v
		f += rng.randi_range(min_hold, max_hold) * step
	return out


func _seq_at(seq: Array, f: int):
	var v = seq[0][1]
	for e in seq:
		if e[0] > f:
			break
		v = e[1]
	return v


func _make_sequences() -> void:
	# Laterne: Farbe wechselt nach 2-6 Bildern zwischen hellem Gelb, Gold und Orange
	lantern_seq = _hold_seq(1977, [0x1E, 0x1C, 0x2C, 0x1E, 0x3C], 2, 6)
	# Sterne: meist an, kurz aus (Funkeln)
	var i := 0
	for s in lay["stars"]:
		star_seq[i] = _hold_seq(100 + i, [1, 1, 1, 0], 3, 12)
		i += 1
	# Glitzern im Meer: kurze Lichtpunkte in den Abendlicht-Zeilen
	var rng := RandomNumberGenerator.new()
	rng.seed = 2600
	for k in 7:
		var y := 72 + k * 3 + rng.randi_range(0, 1)
		glints.append({"y": y, "x": rng.randi_range(20, 92), "w": 2 if k % 2 == 0 else 1,
			"seq": _hold_seq(300 + k, [1, 0, 0], 2, 6, 2), "drift": rng.randi_range(0, 1)})
	# Wind am Schal: Böen in Vielfachen von 5 Bildern (6 Wechsel/s)
	wind_seq = _hold_seq(42, [0, 1], 1, 4, 5)
	# Abendlicht-Zeilen im Meer schimmern (alle 5 Bilder neu)
	rng.seed = 64
	for k in 80:
		reflect_seq.append(rng.randi() & 0xFF)


# ------------------------------------------------------------------ Zeilentabelle

func _sr(y: int, reg: int, v: int) -> void:
	R[y * NREG + reg] = v


func _gr(y: int, reg: int) -> int:
	return R[y * NREG + reg]


func _flag(y: int, f: int) -> void:
	R[y * NREG + R_FLAGS] |= f


func _reset_lines() -> void:
	var scene_h := int(rom["scene_h"])
	for y in LINES:
		for k in NREG:
			R[y * NREG + k] = 0
		if y < scene_h:
			_sr(y, R_BK, int(rom["bk"][y]))
			_sr(y, R_PF, int(rom["pfc"][y]))
			_sr(y, R_PFR, int(rom["pfc_r"][y]))
			_sr(y, R_SPLIT, int(rom["split"][y]))
			var p: Array = rom["pf"][y]
			var bits := 0
			for k in 5:
				bits |= int(p[k]) << (8 * k)
			_sr(y, R_PFBITS, bits)
			_sr(y, R_FLAGS, F_HMOVE)
		else:
			_sr(y, R_SPLIT, 160)
			_sr(y, R_FLAGS, F_TEXT)


func _player(y0: int, rows: Array, x: int, reg_grp: int, reg_col: int, reg_x: int, reg_nus: int, nusiz: int) -> void:
	for i in rows.size():
		var y := y0 + i
		if y < 0 or y >= LINES:
			continue
		_sr(y, reg_grp, int(rows[i][0]))
		_sr(y, reg_col, int(rows[i][1]))
		_sr(y, reg_x, posmod(x, 160))
		_sr(y, reg_nus, nusiz)


func _update() -> void:
	_reset_lines()
	_lighthouse()
	_sea()
	_surf()
	_stars()
	_smoke()
	_gulls()
	_window_and_glints()
	_boats()
	_lantern_and_barrels()
	_parcel()
	_badger()
	_textband()
	_account()
	_upload()
	stat["frames"] += 1
	if frame == dump_frame:
		_dump()


# ------------------------------------------------------------------ Szene

func _lighthouse() -> void:
	# 6 Zustände: 0 Strahl lang links, 1 kurz links, 2 Blitz zur Kamera, 3 kurz rechts, 4-5 dunkel
	var st := int(floor(float(frame + beam_offset) / BEAM_FRAMES)) % 6
	var y0 := int(lay["lamp_lines"][0])
	var y1 := int(lay["lamp_lines"][1])
	var lit := 0x1E
	var col := lit if st <= 3 else 0x12
	for y in range(y0, y1):
		# Lampe hell; der Strahl links davon etwas matter: COLUPF wird in der Zeile bei Pixel 132 umgeschrieben
		_sr(y, R_PF, 0x1C if st <= 3 else col)
		_sr(y, R_PFR, col)
		_sr(y, R_SPLIT, 132)
	var mid := (y0 + y1) / 2   # Zeilen mid-1, mid: Strahlkern
	if st == 0:
		# langer Strahl nach links: Lichtkegel, an der Lampe 2 Zeilen, weiter außen 4 Zeilen hoch
		_pf_range(mid - 1, mid + 1, 12, 33)
		_pf_range(mid - 2, mid - 1, 8, 22)
		_pf_range(mid + 1, mid + 2, 8, 22)
	elif st == 1:
		_pf_range(mid - 1, mid + 1, 27, 33)
		_pf_range(mid - 2, mid - 1, 24, 26)
		_pf_range(mid + 1, mid + 2, 24, 26)
	elif st == 2:
		_pf_range(y0 + 1, y1 - 1, 33, 33)
		_pf_range(y0 + 1, y1 - 1, 36, 36)
		_pf_range(mid - 1, mid + 1, 32, 37)
		for y in range(y0, y1):
			_sr(y, R_PF, lit)
	elif st == 3:
		_pf_range(mid - 1, mid + 1, 36, 39)


func _pf_range(y0: int, y1: int, c0: int, c1: int) -> void:
	for y in range(y0, y1):
		var bits := _gr(y, R_PFBITS)
		for c in range(c0, c1 + 1):
			bits |= 1 << c
		_sr(y, R_PFBITS, bits)


func _sea() -> void:
	# Abendlicht-Zeilen schimmern (alle 5 Bilder = 6/s), Dünung läuft nach vorn (alle 5 Bilder 1 Zeile)
	var s0 := int(lay["sea"][0])
	var s1 := int(lay["sea"][1])
	var step := frame / 5
	var mask: int = reflect_seq[step % reflect_seq.size()]
	var k := 0
	for y in range(s0, s1):
		var c := _gr(y, R_BK)
		var hue := c >> 4
		if hue >= 2 and hue <= 5:
			# warme Zeile: in etwa einem Drittel der Schritte kurz auf die Meerfarbe darunter
			if (mask >> (k % 8)) & 1 == 1 and (mask >> ((k + 3) % 8)) & 1 == 1:
				_sr(y, R_BK, _gr(y + 1, R_BK) if y + 1 < s1 else c)
			k += 1
		elif y >= 84:
			# Dünung: jede 6. Zeile eine Stufe heller, wandert nach unten
			if posmod(y - step, 6) == 0:
				_sr(y, R_BK, c + 2)


func _surf() -> void:
	# Brandung an der Felskante: weiße Playfield-Blöcke, Muster rückt alle 5 Bilder weiter
	var y0 := int(lay["surf_y"])
	var step := frame / 5
	for y in range(y0, y0 + 2):
		var bits := _gr(y, R_PFBITS)
		for c in range(19, 40):
			var v := posmod(c * 5 + step * (1 if y == y0 else -1) + (y - y0) * 3, 7)
			if v < 3:
				bits |= 1 << c
		_sr(y, R_PFBITS, bits)
		_sr(y, R_PFR, 0x0E)
		_sr(y, R_SPLIT, 54)


func _stars() -> void:
	# Zwei Sätze Sterne im Wechsel von Bild zu Bild (Flackern), jeder Stern funkelt zusätzlich
	var i := 0
	for s in lay["stars"]:
		var y := int(s[0])
		if int(s[2]) == frame % 2 and int(_seq_at(star_seq[i], frame)) == 1:
			_sr(y, R_BLX, int(s[1]))
			_sr(y, R_CTRL, _gr(y, R_CTRL) & ~0x30)   # Ball 1 px
			_flag(y, F_ENABL)
			if _gr(y, R_PFBITS) == 0:
				_sr(y, R_PF, 0x0E)
				_sr(y, R_PFR, 0x0E)
		i += 1


func _smoke() -> void:
	# Spieler 0 zeichnet die Rauchsäule über dem Schornstein: je Zeile ein Strich (höchstens 8 px), die Breite
	# wächst mit der Höhe, Lücken zwischen den Wölkchen wandern nach oben (alle 3 Bilder 1 Zeile = 10/s).
	var sm: Dictionary = lay["smoke"]
	var ytop := int(sm["y_top"])
	var ybot := int(sm["y_bottom"])
	var cx := float(sm["x"])
	var phase := frame / 3
	for y in range(ytop, ybot + 1):
		var h := ybot - y
		# Farbe je Zeile fest (auch ohne Rauch), damit die Möwen in diesen Zeilen ruhig bleiben
		_sr(y, R_P0C, 0x0A if y >= 58 else (0x08 if y >= 46 else 0x06))
		var k := posmod(y + phase, 9)
		if h > 3 and k >= 7:
			continue
		var w := mini(2 + h / 7, 6)
		if h > 3 and (k == 0 or k == 6):
			w = maxi(w - 2, 1)
		var xc := cx - h * 0.3 + (1.0 if posmod(y + phase, 18) < 9 else 0.0)
		var x0 := int(round(xc - w / 2.0))
		var bits := 0
		for i in w:
			bits |= 1 << (7 - i)
		_sr(y, R_GRP0, bits)
		_sr(y, R_P0X, x0)


func _gulls() -> void:
	# Zwei Möwen in denselben Zeilen: gerade Bilder Möwe A, ungerade Möwe B (Flackern)
	# Form je Zeile: [Versatz, Breite] für Missile 0 (linker Flügel) und Missile 1 (rechter Flügel)
	var up := [[[0, 2], [6, 2]], [[2, 2], [4, 2]], [null, null]]
	var down := [[[3, 2], null], [[1, 2], [5, 2]], [[0, 1], [7, 1]]]
	var which := frame % 2
	var y0: int
	var x: int
	var flap: bool
	if which == 0:
		y0 = 35
		x = int(round(150.0 - t * 18.0))
		flap = (frame / 5) % 2 == 0
	else:
		y0 = 37
		x = int(round(12.0 + t * 14.0))
		flap = ((frame + 2) / 5) % 2 == 0
	var shape: Array = up if flap else down
	for r in 3:
		var y := y0 + r
		var col := _gr(y, R_P0C)       # Farbe der Rauchzeilen (Spieler 0 und Missile 0 teilen sie)
		_sr(y, R_P1C, col)
		if shape[r][0] != null:
			_sr(y, R_M0X, posmod(x + int(shape[r][0][0]), 160))
			_sr(y, R_NUS0, (_gr(y, R_NUS0) & 0x0F) | (_msize(int(shape[r][0][1])) << 4))
			_flag(y, F_ENAM0)
		if shape[r][1] != null:
			_sr(y, R_M1X, posmod(x + int(shape[r][1][0]), 160))
			_sr(y, R_NUS1, (_gr(y, R_NUS1) & 0x0F) | (_msize(int(shape[r][1][1])) << 4))
			_flag(y, F_ENAM1)


func _msize(w: int) -> int:
	return {1: 0, 2: 1, 4: 2, 8: 3}[w]


func _window_and_glints() -> void:
	var w: Dictionary = lay["window"]
	for y in range(int(w["y0"]), int(w["y1"])):
		_sr(y, R_M0X, int(w["x"]))
		_sr(y, R_NUS0, _msize(int(w["w"])) << 4)
		_sr(y, R_P0C, int(w["color"]))
		_flag(y, F_ENAM0)
	for g in glints:
		if int(_seq_at(g["seq"], frame)) == 0:
			continue
		var y: int = g["y"]
		var x: int = int(g["x"]) + (frame / 30) * int(g["drift"])
		_sr(y, R_M0X, x)
		_sr(y, R_NUS0, _msize(int(g["w"])) << 4)
		_sr(y, R_P0C, 0x3E if y < 80 else 0x0C)
		_flag(y, F_ENAM0)


func _boats() -> void:
	# Spieler 1 mit zwei Kopien (32 px Abstand): beide Boote schaukeln zwangsläufig gleich
	var b: Dictionary = lay["boats"]
	var rows: Array = spr["boat"]
	var bob := 1 if (frame / 24) % 2 == 1 else 0
	var top := int(b["water_y"]) - rows.size() + bob
	_player(top, rows, int(b["x"]), R_GRP1, R_P1C, R_P1X, R_NUS1, int(b["nusiz"]))
	for y in range(top - int(b["mast_h"]), top):
		_sr(y, R_M1X, int(b["x"]) + int(b["mast_dx"]))
		_sr(y, R_NUS1, int(b["nusiz"]))
		_sr(y, R_P1C, 0x22)
		_flag(y, F_ENAM1)


func _lantern_and_barrels() -> void:
	var la: Dictionary = lay["lantern"]
	var y0 := int(la["y0"])
	var y1 := int(la["y1"])
	var flame: int = _seq_at(lantern_seq, frame)
	for y in range(y0, y1):
		var cap := y == y0 or y == y1 - 1
		_sr(y, R_M1X, int(la["x"]) + (1 if cap else 0))
		_sr(y, R_NUS1, (1 if cap else 2) << 4)
		_sr(y, R_P1C, 0x02 if cap else flame)
		_flag(y, F_ENAM1)
	# Fässer: Spieler 1 doppelt breit (NUSIZ 5), zwei Fässer in einem Bitmuster
	var br: Dictionary = lay["barrels"]
	var rows: Array = spr["barrel"]
	var top := int(br["y_bottom"]) - rows.size() + 1
	_player(top, rows, int(br["x"]), R_GRP1, R_P1C, R_P1X, R_NUS1, int(br["nusiz"]))
	for y in range(y1, int(la["post_y1"])):
		_sr(y, R_M1X, int(la["post_x"]))
		_sr(y, R_NUS1, _gr(y, R_NUS1) & 0x07)
		if _gr(y, R_GRP1) == 0:
			_sr(y, R_P1C, 0xF2)
		_flag(y, F_ENAM1)


func _parcel() -> void:
	var pa: Dictionary = lay["parcel"]
	for y in range(int(pa["y0"]), int(pa["y1"])):
		_sr(y, R_BLX, int(pa["x"]))
		_sr(y, R_CTRL, (_gr(y, R_CTRL) & ~0x30) | (_msize(int(pa["w"])) << 4))
		_sr(y, R_PF, int(pa["color"]))
		_sr(y, R_PFR, int(pa["color"]))
		_flag(y, F_ENABL)


func badger_state() -> Array:
	## [Bild-Name, x]: läuft ab x = 0 (hinter dem HMOVE-Balken) nach rechts, hält bei stop_x, dreht sich um.
	var stop_x := int(lay["badger_stop_x"])
	var steps_total := stop_x / STEP_PX
	var steps := mini(frame / STEP_FRAMES, steps_total)
	var x := steps * STEP_PX
	var name := "badger_A" if steps % 2 == 0 else "badger_B"
	if frame >= TURN_FRAME:
		var wind: int = _seq_at(wind_seq, frame)
		name = "badger_front_wind" if wind == 1 else "badger_front"
		if ((frame - TURN_FRAME) / 15) % 2 == 1:     # Atmen: alle 0,5 s Oberkörper eine Zeile tiefer
			name += "_breath"
	return [name, x]


func _badger() -> void:
	var st := badger_state()
	var rows: Array = spr[st[0]]
	var top := int(lay["feet_y"]) - rows.size() + 1
	_player(top, rows, int(st[1]), R_GRP0, R_P0C, R_P0X, R_NUS0, 0)


# ------------------------------------------------------------------ Textband

func _text_lines() -> Array:
	## [[Text, Farbe]] je Textzeile; Farbe als Liste je Glyphenzeile (Farbverlauf wie bei Punktanzeigen)
	var out := []
	out.append([LOCATION.to_upper(), [0x1C, 0x1E, 0x1E, 0x1C, 0x1A, 0x18]])
	var n := int(max(0.0, (t - TYPE_T0) * TYPE_CPS))
	var l1 := LINE1.to_upper()
	var l2 := LINE2.to_upper()
	var white := [0x0E, 0x0E, 0x0E, 0x0C, 0x0C, 0x0A]
	out.append([l1.substr(0, mini(n, l1.length())), white])
	out.append([l2.substr(0, clampi(n - l1.length(), 0, l2.length())), white])
	var cursor := 0 if t < CURSOR_T else 1
	for i in 3:
		var shown := t >= CHOICE_T + i * 0.15
		var sel := shown and i == cursor
		var s: String = ("* " if sel else "  ") + str(i + 1) + " " + CHOICES[i].to_upper() if shown else ""
		out.append([s, [0x3E, 0x3E, 0x3C, 0x3C, 0x3A, 0x38] if sel else [0x9E, 0x9C, 0x9C, 0x9A, 0x98, 0x98]])
	var p := ""
	if t >= PARSER_T:
		var m := int((t - PARSER_T) * PARSER_CPS)
		p = PARSER.to_upper().substr(0, mini(m, PARSER.length()))
		if (frame / 10) % 2 == 0:
			p += "_"
	out.append([p, white])
	return out


func _textband() -> void:
	var lines := _text_lines()
	var key := ""
	for l in lines:
		key += l[0] + "|"
	if key != text_key:
		text_key = key
		text_px.fill(0)
		for k in lines.size():
			_draw_text(lines[k][0], TEXT_X0, 2 + TEXT_PITCH * k)
		text_img.set_data(160, LINES - text_y0, false, Image.FORMAT_R8, text_px)
		text_tex.update(text_img)
	for k in lines.size():
		var cols: Array = lines[k][1]
		for r in 6:
			var y := text_y0 + 2 + TEXT_PITCH * k + r
			if y < LINES:
				_sr(y, R_PF, int(cols[r]))
				_sr(y, R_PFR, int(cols[r]))


func _draw_text(s: String, x0: int, y0: int) -> void:
	var font: Dictionary = rom["font"]
	var x := x0
	for ch in s:
		var g: Dictionary = font.get(ch, font["?"])
		var w := int(g["w"])
		var rows: Array = g["rows"]
		for r in 6:
			var bits := int(rows[r])
			for b in w:
				if (bits >> (w - 1 - b)) & 1 == 1 and x + b < 160:
					var yy := y0 + r
					if yy < LINES - text_y0:
						text_px[yy * 160 + x + b] = 255
		x += w + 1


# ------------------------------------------------------------------ Prüfung und Übergabe an den Shader

func _pf_regs(bits: int) -> Array:
	## Linke Hälfte (Blöcke 0-19) und rechte Hälfte (20-39) als PF0/PF1/PF2-Werte
	var l := [bits & 0xF, (bits >> 4) & 0xFF, (bits >> 12) & 0xFF]
	var r := [(bits >> 20) & 0xF, (bits >> 24) & 0xFF, (bits >> 32) & 0xFF]
	return [l, r]


func _mirror20(bits: int) -> int:
	var m := 0
	for i in 20:
		if (bits >> i) & 1 == 1:
			m |= 1 << (19 - i)
	return m


func _account() -> void:
	## Grobe Kernel-Rechnung je Zeile: Wie viele Register muss das Programm schreiben?
	## Register, die in einer Zeile nicht sichtbar wirken (Farbe oder Position eines unsichtbaren Objekts), gelten
	## als unverändert. Ein Sprung um mehr als 7 Pixel braucht RESxx in einer Vorzeile, in der das Objekt nicht
	## sichtbar ist; er wird dieser Vorzeile angerechnet. Asymmetrisches Playfield: je abweichendem Register zwei
	## Zugriffe (linker Wert vor, rechter Wert in der Zeilenmitte).
	var eff := PackedInt64Array()
	eff.resize(NREG)
	var pf_prev := [0, 0, 0]
	var dx_prev := [0, 0, 0, 0, 0]
	var scene_h := int(rom["scene_h"])
	for y in LINES:
		writes_line[y] = 0
	for y in scene_h:
		var w := 0
		var bits := _gr(y, R_PFBITS)
		var left := bits & 0xFFFFF
		var right := (bits >> 20) & 0xFFFFF
		var regsLR := _pf_regs(bits)
		var asym := false
		if right == left:
			stat["repeat_lines"] += 1
		elif right == _mirror20(left):
			stat["reflect_lines"] += 1
		else:
			asym = true
			stat["asym_lines"] += 1
		for k in 3:
			var lv: int = regsLR[0][k]
			var rv: int = regsLR[1][k]
			if asym and lv != rv:
				w += 2
				pf_prev[k] = rv
			else:
				if lv != pf_prev[k]:
					w += 1
				pf_prev[k] = lv
		var flags := _gr(y, R_FLAGS)
		var en0 := (flags & F_ENAM0) != 0
		var en1 := (flags & F_ENAM1) != 0
		var enb := (flags & F_ENABL) != 0
		var g0 := _gr(y, R_GRP0) != 0
		var g1 := _gr(y, R_GRP1) != 0
		var pf_vis := bits != 0 or enb
		var p0_vis := g0 or en0
		var p1_vis := g1 or en1
		var split_px := _gr(y, R_SPLIT)
		var right_pf := pf_vis and split_px < 160 and _gr(y, R_PFR) != _gr(y, R_PF)
		# sichtbare Register (übrige behalten den Wert der Vorzeile)
		var cur := {R_BK: true, R_PF: pf_vis, R_P0C: p0_vis, R_P1C: p1_vis, R_GRP0: true, R_GRP1: true,
			R_NUS0: p0_vis, R_NUS1: p1_vis, R_CTRL: enb}
		for reg in cur:
			if cur[reg] and _gr(y, reg) != eff[reg]:
				w += 1
				eff[reg] = _gr(y, reg)
		if right_pf:
			w += 1
			stat["split_lines"] += 1
		var en_bits := flags & (F_ENAM0 | F_ENAM1 | F_ENABL)
		var en_prev := eff[R_FLAGS] & (F_ENAM0 | F_ENAM1 | F_ENABL)
		for f in [F_ENAM0, F_ENAM1, F_ENABL]:
			if (en_bits & f) != (en_prev & f):
				w += 1
		eff[R_FLAGS] = flags
		# Positionen
		var vis := [g0, g1, en0, en1, enb]
		var regsx := [R_P0X, R_P1X, R_M0X, R_M1X, R_BLX]
		for k in 5:
			if not vis[k]:
				continue
			var dx := posmod(_gr(y, regsx[k]) - eff[regsx[k]] + 80, 160) - 80
			if abs(dx) > 7:
				# Grobes Umsetzen (RESxx) in der Vorzeile; das Objekt darf dort nicht sichtbar gewesen sein
				if y > 0:
					writes_line[y - 1] += 2
				if _was_visible(y - 1, k):
					stat["reposition_visible"] += 1
				dx_prev[k] = 0
			elif dx != dx_prev[k]:
				w += 1
				dx_prev[k] = dx
			eff[regsx[k]] = _gr(y, regsx[k])
		writes_line[y] += w
	for y in scene_h:
		var w2 := writes_line[y]
		if w2 > stat["max_writes"]:
			stat["max_writes"] = w2
			stat["max_writes_line"] = y
		if w2 > WRITE_BUDGET:
			stat["lines_over_budget"] += 1
		var flags := _gr(y, R_FLAGS)
		var cols := {}
		cols[_gr(y, R_BK)] = 1
		if _gr(y, R_PFBITS) != 0 or (flags & F_ENABL) != 0:
			cols[_gr(y, R_PF)] = 1
			if _gr(y, R_SPLIT) < 160:
				cols[_gr(y, R_PFR)] = 1
		if _gr(y, R_GRP0) != 0 or (flags & F_ENAM0) != 0:
			cols[_gr(y, R_P0C)] = 1
		if _gr(y, R_GRP1) != 0 or (flags & F_ENAM1) != 0:
			cols[_gr(y, R_P1C)] = 1
		stat["max_colors_line"] = maxi(stat["max_colors_line"], cols.size())


func _was_visible(y: int, k: int) -> bool:
	if y < 0:
		return false
	var fl := _gr(y, R_FLAGS)
	match k:
		0: return _gr(y, R_GRP0) != 0
		1: return _gr(y, R_GRP1) != 0
		2: return (fl & F_ENAM0) != 0
		3: return (fl & F_ENAM1) != 0
		4: return (fl & F_ENABL) != 0
	return false


func _dump() -> void:
	var names := ["colubk", "colupf", "colup0", "colup1", "colupf_r", "split", "pf", "grp0", "grp1", "p0x",
		"p1x", "m0x", "m1x", "blx", "nusiz0", "nusiz1", "ctrlpf", "flags"]
	var out := []
	for y in LINES:
		var d := {"writes": writes_line[y]}
		for k in NREG:
			d[names[k]] = _gr(y, k)
		out.append(d)
	var f := FileAccess.open(dump_path, FileAccess.WRITE)
	f.store_string(JSON.stringify({"frame": frame, "lines": out, "text_px": Array(text_px)}))
	f.close()


func _upload() -> void:
	for y in LINES:
		var base := y * 4
		var stride := LINES * 4
		var bits := _gr(y, R_PFBITS)
		var row := [
			[_gr(y, R_BK), _gr(y, R_PF), _gr(y, R_P0C), _gr(y, R_P1C)],
			[bits & 0xFF, (bits >> 8) & 0xFF, (bits >> 16) & 0xFF, (bits >> 24) & 0xFF],
			[(bits >> 32) & 0xFF, _gr(y, R_GRP0), _gr(y, R_GRP1), _gr(y, R_FLAGS)],
			[_gr(y, R_P0X), _gr(y, R_P1X), _gr(y, R_M0X), _gr(y, R_M1X)],
			[_gr(y, R_BLX), _gr(y, R_NUS0), _gr(y, R_NUS1), _gr(y, R_CTRL)],
			[_gr(y, R_PFR), _gr(y, R_SPLIT), 0, 0],
		]
		for r in 6:
			for c in 4:
				regs[r * stride + base + c] = int(row[r][c]) & 0xFF
	regs_img.set_data(LINES, 6, false, Image.FORMAT_RGBA8, regs)
	regs_tex.update(regs_img)
