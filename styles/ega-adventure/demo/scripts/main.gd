extends Node2D
## Hafen von Lornholm im Stil eines EGA-Parser-Adventures (1984–1988).
##
## Das Bild ist keine Bitmap, sondern eine Liste von Zeichenbefehlen (Linienzüge, Punkte, Flutfüllungen)
## auf zwei Ebenen: sichtbar (16 EGA-Farben) und Priorität. Zu Beginn wird die Liste sichtbar abgearbeitet,
## wie auf einem langsamen PC. Danach kommen die Views (Dachs, Paket, Möwe, Rauch, Lichter) dazu; jedes
## View-Pixel wird nur gesetzt, wenn die Priorität des Views mindestens so hoch ist wie die der Prioritätsebene
## an dieser Stelle (so geht der Dachs hinter Fässern und Laternenpfahl vorbei).
## Alles auf 160×168 Doppelpixeln; ein Shader setzt Indizes in EGA- oder CGA-Farben um.
## Zeit über delta aufsummiert, Zufall nur mit festem Seed: die Aufnahme ist reproduzierbar.

const PW := 160
const PH := 168
const BUILD_RATE := 560          # Pixel je Bild (30 fps) beim Bildaufbau
const LINE_COST := 8             # Grundkosten je Linien-/Punktbefehl, damit Linien nacheinander erscheinen

const WALK_T := 1.80             # Dachs betritt das Bild
const WALK_FPS := 10.0
const WALK_CELS := 30            # Laufbilder 0..29; Bild 29 ist Zyklusbild 5, danach Stehen
const START_X := 147
const TURN_T := 5.10             # dreht sich zum Spieler
const MSG_T0 := 2.30
const MSG_T1 := 5.10
const TYPE_T := 3.80
const ENTER_T := 5.10
const CGA_T := 5.40
const COMMAND := "nimm paket"

var t := 0.0
var fno := 0                     # Bildzähler (30 fps): Haltezeiten der Einzelbilder ganzzahlig, ohne Rundungsfehler
var cmds: Array = []
var layout: Dictionary = {}
var views: Dictionary = {}
var chars: Dictionary = {}

# Bildpuffer
var vis := PackedByteArray()
var pri := PackedByteArray()
var frame := PackedByteArray()
var img: Image
var tex: ImageTexture

# Zustand des Zeichenbefehl-Interpreters
var ci := 0
var vcol := -1
var pcol := -1
var pend := PackedInt32Array()
var pend_i := 0
var seeds := PackedInt32Array()
var seed_i := 0
var q := PackedInt32Array()
var q_i := 0
var fill_on_vis := true
var fill_target := 15
var built := false
var built_t := -1.0

# Views
var walk_cels: Array = []
var stand_cels: Array = []
var front_cels: Array = []
var amb: Dictionary = {}
var bw := 10
var bh := 30
var advance: Array = []
var walk_y := 146

# Zustand für Oberfläche (ui.gd liest)
var typed := ""
var msg_visible := false
var score := 0
var cga := false
var parcel_taken := false
var badger_x := START_X
var start_x := START_X           # Startspalte des Dachses (layout.start_x, sonst START_X)
var build_rate := BUILD_RATE     # Bildaufbau-Tempo (build_rate aus der Bilddatei, sonst BUILD_RATE)
var badger_info := ""            # für Messungen (--probe)

var rng := RandomNumberGenerator.new()
var flick := PackedFloat32Array()
var glints: Array = []
var water := 1                   # Farbe der offenen Wasserfläche (Glitzern nur dort)
var timing := false              # nur für Messungen: --timing gibt die Rechenzeit je Bild aus
var us_build := PackedInt32Array()
var us_play := PackedInt32Array()
var no_badger := false           # nur für Messungen: scripts/probe_badger.py vergleicht mit und ohne Dachs

@onready var pic: Sprite2D = $Picture
@onready var ui: Node2D = $UI


func _ready() -> void:
	# Welches Bild läuft, steht in art/scene.json ({"picture": "harbor.pic.json"}); ohne Datei das Handbild.
	var pic_path := "res://art/harbor.pic.json"
	if FileAccess.file_exists("res://art/scene.json"):
		var scene: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
		pic_path = "res://art/" + String(scene.get("picture", "harbor.pic.json"))
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(pic_path))
	cmds = data["commands"]
	layout = data["layout"]
	build_rate = int(data.get("build_rate", BUILD_RATE))
	# nur für Vergleiche: --pic=<Datei> spielt eine andere Befehlsliste ab (z. B. automatisch umgewandelt);
	# bringt die Datei eine eigene Lage mit (scripts/process_raw.py), gilt diese
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--pic="):
			var alt: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(a.substr(6)))
			cmds = alt["commands"]
			if alt.has("layout"):
				layout = alt["layout"]
			build_rate = int(alt.get("build_rate", build_rate))
	walk_y = int(layout["walk_y"])
	start_x = int(layout.get("start_x", START_X))
	badger_x = start_x
	views = JSON.parse_string(FileAccess.get_file_as_string("res://art/views.json"))
	chars = views["chars"]
	var b: Dictionary = views["badger"]
	bw = int(b["w"])
	bh = int(b["h"])
	for f in b["walk"]["frames"]:
		walk_cels.append(_cel(f))
	for f in b["stand"]["frames"]:
		stand_cels.append(_cel(f))
	for f in b["front"]["frames"]:
		front_cels.append(_cel(f))
	advance = b["walk"]["advance"]
	for k in views["ambient"]:
		var cl: Array = []
		for f in views["ambient"][k]["frames"]:
			cl.append(_cel(f))
		amb[k] = cl
	vis.resize(PW * PH)
	vis.fill(15)
	pri.resize(PW * PH)
	pri.fill(4)
	img = Image.create_from_data(PW, PH, false, Image.FORMAT_R8, vis)
	tex = ImageTexture.create_from_image(img)
	pic.texture = tex
	no_badger = OS.get_cmdline_user_args().has("--no-badger")
	timing = OS.get_cmdline_user_args().has("--timing")
	rng.seed = 1986
	for i in 256:
		flick.append(rng.randf())
	# Wasserglitzern: feste Stellen auf offener Wasserfläche, je eigene Phase
	var spots: Array = layout.get("glints", [[14, 80, 3], [30, 88, 2], [70, 78, 3], [88, 84, 2], [24, 100, 3],
			[76, 92, 2], [118, 110, 3], [140, 104, 2], [8, 112, 2], [96, 110, 3], [62, 109, 2], [150, 110, 2]])
	water = int(layout.get("water", 1))
	for s in spots:
		glints.append({"x": s[0], "y": s[1], "len": s[2], "period": rng.randf_range(1.1, 1.9),
				"phase": rng.randf()})
	_pic_step(build_rate)
	_compose()


func _process(delta: float) -> void:
	var t0 := Time.get_ticks_usec()
	var was_built := built
	t += delta
	fno += 1
	if not built:
		_pic_step(build_rate)
		if built:
			built_t = t
			_dump_picture()
	_timeline()
	_compose()
	ui.queue_redraw()
	if timing:
		(us_play if was_built else us_build).append(Time.get_ticks_usec() - t0)
		if fno == 179:
			for pair in [["Aufbau", us_build], ["danach", us_play]]:
				var arr: PackedInt32Array = pair[1]
				var sum := 0
				var mx := 0
				for v in arr:
					sum += v
					mx = maxi(mx, v)
				print("%s: %d Bilder, Mittel %.2f ms, höchstens %.2f ms" % [pair[0], arr.size(),
						sum / 1000.0 / maxf(1, arr.size()), mx / 1000.0])


# ---------------------------------------------------------------- Zeichenbefehle

func _dump_picture() -> void:
	## nur für Messungen: --dump-pic=<Datei> schreibt sichtbare und Prioritätsebene nach dem Aufbau
	## (scripts/check_pic.py vergleicht sie mit der Python-Wiedergabe)
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--dump-pic="):
			var f := FileAccess.open(a.substr(11), FileAccess.WRITE)
			f.store_buffer(vis)
			f.store_buffer(pri)
			f.close()
			print("Bild fertig nach %.3f s (Bild %d), Befehle %d" % [t, fno, cmds.size()])

func _plot(x: int, y: int) -> void:
	if x < 0 or x >= PW or y < 0 or y >= PH:
		return
	var i := y * PW + x
	if vcol >= 0:
		vis[i] = vcol
	if pcol >= 0:
		pri[i] = pcol


func _line_points(x1: int, y1: int, x2: int, y2: int, out: PackedInt32Array, skip_first: bool) -> void:
	## gleicher Algorithmus wie scripts/agipic.py (line_points)
	var pts := PackedInt32Array()
	if x1 == x2:
		var s := 1 if y2 >= y1 else -1
		var y := y1
		while true:
			pts.append(x1)
			pts.append(y)
			if y == y2:
				break
			y += s
	elif y1 == y2:
		var s := 1 if x2 >= x1 else -1
		var x := x1
		while true:
			pts.append(x)
			pts.append(y1)
			if x == x2:
				break
			x += s
	else:
		var dy := absi(y2 - y1)
		var sy := 1 if y2 >= y1 else -1
		var dx := absi(x2 - x1)
		var sx := 1 if x2 >= x1 else -1
		var i := 0
		var det := 0
		var ex := 0
		var ey := 0
		if dy > dx:
			i = dy
			det = dy
			ey = dy / 2
			ex = 0
		else:
			i = dx
			det = dx
			ex = dx / 2
			ey = 0
		var x := x1
		var y := y1
		pts.append(x)
		pts.append(y)
		while i > 0:
			ey += dy
			if ey >= det:
				ey -= det
				y += sy
			ex += dx
			if ex >= det:
				ex -= det
				x += sx
			pts.append(x)
			pts.append(y)
			i -= 1
	var start := 2 if skip_first else 0
	for k in range(start, pts.size()):
		out.append(pts[k])


func _pic_step(budget: int) -> void:
	while budget > 0 and not built:
		if pend_i < pend.size():
			_plot(pend[pend_i], pend[pend_i + 1])
			pend_i += 2
			budget -= 1
			continue
		if q_i < q.size():
			budget -= _fill_span()
			continue
		if seed_i < seeds.size():
			_start_fill(seeds[seed_i], seeds[seed_i + 1])
			seed_i += 2
			continue
		if ci >= cmds.size():
			built = true
			break
		var c: Array = cmds[ci]
		ci += 1
		var op: String = c[0]
		if op == "c":
			vcol = int(c[1])
		elif op == "p":
			pcol = int(c[1])
		elif op == "l":
			pend = PackedInt32Array()
			pend_i = 0
			var a: Array = c[1]
			for k in range(0, a.size() - 2, 2):
				_line_points(int(a[k]), int(a[k + 1]), int(a[k + 2]), int(a[k + 3]), pend, k > 0)
			budget -= LINE_COST
		elif op == "s":
			pend = PackedInt32Array()
			pend_i = 0
			for v in c[1]:
				pend.append(int(v))
			budget -= LINE_COST
		elif op == "f":
			seeds = PackedInt32Array()
			seed_i = 0
			for v in c[1]:
				seeds.append(int(v))


func _start_fill(x: int, y: int) -> void:
	## Flutfüllung wie im Original: sichtbare Ebene an -> füllt, was dort noch weiß ist;
	## nur Prioritätsebene an -> füllt, was dort noch Priorität 4 hat.
	q = PackedInt32Array()
	q_i = 0
	if vcol >= 0:
		if vcol == 15:
			return
		fill_on_vis = true
		fill_target = 15
	elif pcol >= 0:
		if pcol == 4:
			return
		fill_on_vis = false
		fill_target = 4
	else:
		return
	q.append(x)
	q.append(y)


func _is_target(x: int, y: int) -> bool:
	var i := y * PW + x
	return (vis[i] if fill_on_vis else pri[i]) == fill_target


func _fill_span() -> int:
	## Zeilenweise Füllung aus einer Warteschlange: die Fläche wächst sichtbar Zeile um Zeile.
	var x := q[q_i]
	var y := q[q_i + 1]
	q_i += 2
	if not _is_target(x, y):
		return 1
	var x0 := x
	while x0 > 0 and _is_target(x0 - 1, y):
		x0 -= 1
	var x1 := x
	while x1 < PW - 1 and _is_target(x1 + 1, y):
		x1 += 1
	for xx in range(x0, x1 + 1):
		_plot(xx, y)
	for ny in [y - 1, y + 1]:
		if ny < 0 or ny >= PH:
			continue
		var inside := false
		for xx in range(x0, x1 + 1):
			var tg := _is_target(xx, ny)
			if tg and not inside:
				q.append(xx)
				q.append(ny)
			inside = tg
	return x1 - x0 + 1


# ---------------------------------------------------------------- Views

func _cel(rows: Array) -> Dictionary:
	var h := rows.size()
	var w := 0
	for r in rows:
		w = maxi(w, String(r).length())
	var px := PackedByteArray()
	px.resize(w * h)
	px.fill(255)
	for j in h:
		var r: String = rows[j]
		for i in r.length():
			var ch := r[i]
			if ch != "." and chars.has(ch):
				px[j * w + i] = int(chars[ch])
	return {"w": w, "h": h, "px": px}


func _draw_cel(c: Dictionary, x: int, y: int, prio: int, flip := false, only_on := -1) -> void:
	var w: int = c["w"]
	var h: int = c["h"]
	var px: PackedByteArray = c["px"]
	for j in h:
		var yy := y + j
		if yy < 0 or yy >= PH:
			continue
		for i in w:
			var v := px[j * w + (w - 1 - i if flip else i)]
			if v == 255:
				continue
			var xx := x + i
			if xx < 0 or xx >= PW:
				continue
			var k := yy * PW + xx
			if only_on >= 0 and vis[k] != only_on:
				continue
			if prio >= pri[k]:
				frame[k] = v


func _band(y: int) -> int:
	return 4 if y < 48 else mini(15, 5 + (y - 48) / 12)


func _walk_offset(n: int) -> int:
	var per := 0
	for a in advance:
		per += int(a)
	var d := (n / advance.size()) * per
	for i in n % advance.size():
		d += int(advance[i])
	return d


func _noise(x: float) -> float:
	var i := int(floor(x))
	var f := x - i
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(flick[posmod(i, 256)], flick[posmod(i + 1, 256)], f)


func _compose() -> void:
	frame = vis.duplicate()
	if built:
		_ambient()
		_badger()
	img.set_data(PW, PH, false, Image.FORMAT_R8, frame)
	tex.update(img)


func _ambient() -> void:
	var at := t - built_t
	# Wasserglitzern: kurze helle Striche, nur auf offener Wasserfläche (Farbe layout.water, sonst 1)
	for g in glints:
		var ph: float = fmod(at / float(g["period"]) + float(g["phase"]), 1.0)
		var col := -1
		var ln: int = g["len"]
		if ph < 0.10:
			col = 11
			ln = maxi(1, ln - 1)
		elif ph < 0.22:
			col = 15
		elif ph < 0.32:
			col = 11
		if col >= 0:
			for i in ln:
				var k := int(g["y"]) * PW + int(g["x"]) + i
				if vis[k] == water:
					frame[k] = col
	# Leuchtturm: Linse dreht sich, alle 2,4 s blitzt das Licht zum Betrachter
	var lp := fmod(at, 2.4) / 2.4
	var lamp: Array = amb["lamp"]
	var lo = layout.get("lamp_origin", views["ambient"]["lamp"]["origin"])   # null: kein Leuchtfeuer erkannt
	if lo != null and lp < 0.09:
		_draw_cel(lamp[1], int(lo[0]), int(lo[1]), 15)
	elif lo != null and (lp < 0.15 or lp > 0.95):
		_draw_cel(lamp[0], int(lo[0]), int(lo[1]), 15)
	# Laterne flackert im Wind (Glas, im Handbild 119..121 × 104..108). Nur gelbe Glaspixel ändern sich, damit
	# Sprossen und Rahmen einer größeren Laterne (KI-Bild) stehen bleiben; Kern ist die mittlere Spalte.
	var f := _noise(t * 9.0)
	if layout.get("lantern") != null:
		var la: Array = layout["lantern"]
		var mid := (int(la[0]) + int(la[2])) / 2
		for yy in range(int(la[1]), int(la[3]) + 1):
			for xx in range(int(la[0]), int(la[2]) + 1):
				var k := yy * PW + xx
				if vis[k] != 14:
					continue
				var core := xx == mid and yy > int(la[1]) and yy < int(la[3])
				if f < 0.22:
					frame[k] = 14 if core else 6
				elif f > 0.72 and core:
					frame[k] = 15
	# Rauch aus dem Schornstein, vom Wind nach links getragen
	var ct = layout.get("chimney_top")
	var smoke: Array = amb["smoke"]
	var born := -0.9
	while ct != null and born < at:
		var age := at - born
		if age >= 0.0 and age < 1.8:
			var seedv := int(round(born * 10.0)) + 40
			var jx := int(flick[posmod(seedv, 256)] * 3.0) - 1
			var st := mini(smoke.size() - 1, int(age / 0.3))
			var c: Dictionary = smoke[st]
			var px := int(ct[0]) - int(age * 5.0) + jx - int(c["w"]) / 2
			var py := int(ct[1]) - int(age * 9.0) - int(c["h"]) + 1
			_draw_cel(c, px, py, 15)
		born += 0.45
	# Möwe über dem Wasser, fliegt nach links
	var gx := 100 - int(at * 13.0)
	var gy := int(layout.get("gull_y", 74)) + int(round(sin(at * 2.2) * 2.0))   # Flughöhe aus der Bilddatei
	var gull: Array = amb["gull"]
	_draw_cel(gull[int(at * 5.0) % 2], gx, gy, 15)
	# Paket am Kai, bis es genommen wird
	if not parcel_taken:
		var pc := _cel(["BWBB", "WWWW", "BWBB", "BWBB"])
		_draw_cel(pc, int(layout.get("parcel_x", 102)), walk_y - 3, _band(walk_y))


func _badger() -> void:
	if fno < int(round(WALK_T * 30.0)) or no_badger:
		badger_info = ""
		return
	var n := (fno - int(round(WALK_T * 30.0))) / 3          # 10 Bilder/s: jedes Laufbild 3 Aufnahmebilder
	var y := walk_y - (bh - 1)
	var prio := _band(walk_y)
	if n < WALK_CELS:
		badger_x = start_x - _walk_offset(n)
		_draw_cel(walk_cels[n % walk_cels.size()], badger_x, y, prio, true)
		badger_info = "walk %d %d" % [n, badger_x]
	else:
		badger_x = start_x - _walk_offset(WALK_CELS - 1)
		if fno < int(round(TURN_T * 30.0)):
			var k := ((fno - int(round(WALK_T * 30.0))) / 5) % stand_cels.size()   # 6 Bilder/s
			_draw_cel(stand_cels[k], badger_x, y, prio, true)
			badger_info = "stand %d %d" % [k, badger_x]
		else:
			var k2 := ((fno - int(round(TURN_T * 30.0))) / 6) % front_cels.size()  # 5 Bilder/s
			_draw_cel(front_cels[k2], badger_x, y, prio)
			badger_info = "front %d %d" % [k2, badger_x]


# ---------------------------------------------------------------- Ablauf

func _timeline() -> void:
	msg_visible = t >= MSG_T0 and t < MSG_T1
	var n := 0
	if t >= TYPE_T:
		n = mini(COMMAND.length(), int(floor((t - TYPE_T) * 10.0)) + 1)
	typed = COMMAND.substr(0, n)
	if t >= ENTER_T:
		typed = ""
		parcel_taken = true
		score = 2
	cga = t >= CGA_T
	(pic.material as ShaderMaterial).set_shader_parameter("mode", 1 if cga else 0)
