extends Node2D
## Mode 7 & Pseudo-3D: Kamerafahrt über die Bucht von Lornholm.
##
## Wie ein Spiel auf der 16-Bit-Konsole rechnet dieses Skript je Bild auf der "CPU":
##  - Kamera (Position, Kurs, Augenhöhe) entlang einer festen Bahn,
##  - die HDMA-Tabelle der Mode-7-Matrix (A, B, C, D je Zeile, 8.8-Festkomma) und die Register X0/Y0/HOFS/VOFS,
##  - Himmelsverlauf (Hintergrundfarbe je Zeile) und Dunst (feste Farbe je Zeile, Farbaddition auf Mode 7),
##  - die CGRAM-Animationen (Glitzern, Leuchtfeuer, Laterne, Fenster, Bojenlicht),
##  - die OAM-Liste: jedes Objekt wird projiziert und bekommt die vorgezeichnete Größenstufe, die zu seiner
##    Entfernung passt (die Hardware kann Sprites nicht skalieren).
## Dieselben Formeln stehen in scripts/m7lib.py; probe.py vergleicht beide.
## Benutzerargumente nach "--": --t0=<s> (später beginnen), --still=<s> (Zeit einfrieren), --dump=<datei>
## (Prüfprotokoll je Bild), --measure (nur der Dachs auf Schwarz, Kamera fest in der Endstellung).

const W := 256
const H := 224
const Y_H := 92
const PLANE_END := 224
const F := 236.0
const TPM := 10.0
const X_MIN := -51.2
const Y_MAX := 72.4
const HAZE_LINES := 20                 # Zeilen unter dem Horizont mit Farbaddition (Dunst)

const CAM_X0 := 0.9      # einzelne float-Konstanten: Vector2 wäre float32 und wiche von m7lib.py ab
const CAM_Y0 := -15.0
const CAM_X1 := 0.3
const CAM_Y1 := 0.0
const CAM_T := 3.7
const CAM_TH0 := -14.0
const CAM_TH1 := -3.0
const CAM_H0 := 5.0
const CAM_H1 := 2.8

const BG_HOFS0 := 100                  # Versatz der Horizontebenen (Leuchtturm bei x ≈ 180 in der Endstellung)

# Dachs: läuft auf dem Steg nach Osten, 8 Laufbilder je Schritt-Doppel bei 15 Bildern/s
const WALK_X0 := -2.9
const WALK_Y := 6.4
const WALK_V := 0.6881             # m/s = 0,367 m je Zyklus / (8/15 s): Standfuß bleibt stehen
const WALK_STOP_X := -0.05
const TURN_T := 0.2
const WAVE_DELAY := 0.15
const WAVE_FPS := 6.0

const OBJECTS := [
	["cottage", "cottage", -6.9, 17.8],
	["crates", "crates", -5.6, 11.1],
	["barrels", "barrels", -4.2, 13.0],
	["lantern", "lantern", -0.75, 7.35],
	["boat_a", "boat_a", 4.6, 15.8],
	["boat_b", "boat_b", 0.3, 23.0],
	["buoy1", "buoy", 2.7, 19.2],
	["buoy2", "buoy", 13.0, 30.7],
	["buoy3", "buoy", -11.6, 33.4],
]

var t := 0.0
var t0 := 0.0
var frame := 0
var still := -1.0
var measure := false

var cam_x := 0.0
var cam_y := 0.0
var cam_th := 0.0
var cam_h := 0.0

var hdma_img: Image
var hdma_tex: ImageTexture
var fix_img: Image
var fix_tex: ImageTexture
var sky_img: Image
var sky_tex: ImageTexture
var cgram_img: Image
var cgram_tex: ImageTexture
var cgram_base: Array = []        # 256 × [r5, g5, b5]
var cgram_now: Array = []
var names: Dictionary = {}
var glint_seq: Array = []
var regs := [0, 0, 0, 0]
var spr: Dictionary = {}
var backdrop: Dictionary = {}
var atlas: Texture2D
var mat_obj: ShaderMaterial
var mat_math: ShaderMaterial
var pool: Array[Sprite2D] = []
var oam: Array = []
var flicker: Array = []           # Zufallsfolge mit festem Seed (je 1/10 s ein Wert)
var hofs1 := 0
var dump_path := ""
var dump_file: FileAccess
var walk_stop_k := 0

@onready var sky: ColorRect = $Sky
@onready var plane: ColorRect = $Plane
@onready var objs: Node2D = $Objs
@onready var ui: Node2D = $UI


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a.begins_with("--still="):
			still = float(a.substr(8))
		elif a.begins_with("--dump="):
			dump_path = a.substr(7)
		elif a == "--measure":
			measure = true
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/cgram.json"))
	names = data["names"]
	cgram_base = data["base"]
	glint_seq = data["glint_seq"]
	spr = JSON.parse_string(FileAccess.get_file_as_string("res://data/sprites.json"))
	backdrop = JSON.parse_string(FileAccess.get_file_as_string("res://data/backdrop.json"))
	cgram_img = Image.create(256, 1, false, Image.FORMAT_RGB8)
	cgram_tex = ImageTexture.create_from_image(cgram_img)
	hdma_img = Image.create(H, 1, false, Image.FORMAT_RGBAF)
	hdma_tex = ImageTexture.create_from_image(hdma_img)
	fix_img = Image.create(H, 1, false, Image.FORMAT_RGBF)
	fix_tex = ImageTexture.create_from_image(fix_img)
	sky_img = Image.create(Y_H + 1, 1, false, Image.FORMAT_RGB8)
	_build_sky()
	sky_tex = ImageTexture.create_from_image(sky_img)
	var m7 := plane.material as ShaderMaterial
	m7.set_shader_parameter("hdma", hdma_tex)
	m7.set_shader_parameter("fixcol", fix_tex)
	m7.set_shader_parameter("cgram", cgram_tex)
	m7.set_shader_parameter("row0", Y_H + 1)
	m7.set_shader_parameter("rows", PLANE_END - Y_H - 1)
	plane.position = Vector2(0, Y_H + 1)
	plane.size = Vector2(W, PLANE_END - Y_H - 1)
	var sm := sky.material as ShaderMaterial
	sm.set_shader_parameter("cgram", cgram_tex)
	sm.set_shader_parameter("skycol", sky_tex)
	sm.set_shader_parameter("rows", Y_H + 1)
	sky.position = Vector2.ZERO
	sky.size = Vector2(W, Y_H + 1)
	atlas = load("res://art/obj_atlas.png")
	mat_obj = ShaderMaterial.new()
	mat_obj.shader = load("res://shaders/obj.gdshader")
	mat_obj.set_shader_parameter("cgram", cgram_tex)
	mat_math = ShaderMaterial.new()
	mat_math.shader = load("res://shaders/obj_math.gdshader")
	mat_math.set_shader_parameter("cgram", cgram_tex)
	for i in 64:
		var s := Sprite2D.new()
		s.texture = atlas
		s.centered = false
		s.region_enabled = true
		s.visible = false
		objs.add_child(s)
		pool.append(s)
	var rng := RandomNumberGenerator.new()
	rng.seed = 1993
	for i in 2000:
		flicker.append(rng.randf())
	var k := 0
	while WALK_X0 + WALK_V * k / 15.0 < WALK_STOP_X or k % 4 != 0:
		k += 1
	walk_stop_k = k
	if measure:
		sky.visible = false
		plane.visible = false
		ui.visible = false
		RenderingServer.set_default_clear_color(Color.BLACK)
	if dump_path != "":
		dump_file = FileAccess.open(dump_path, FileAccess.WRITE)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update(t)


# ---------------------------------------------------------------------------------------------
# Kamera und HDMA
# ---------------------------------------------------------------------------------------------
static func rnd(x: float) -> int:
	return int(floor(x + 0.5))


static func ease_out(s: float, k: float = 2.2) -> float:
	s = clampf(s, 0.0, 1.0)
	return 1.0 - pow(1.0 - s, k)


static func smooth(s: float) -> float:
	s = clampf(s, 0.0, 1.0)
	return s * s * (3.0 - 2.0 * s)


func camera_at(tt: float) -> void:
	var s := ease_out(tt / CAM_T)
	cam_x = CAM_X0 + (CAM_X1 - CAM_X0) * s
	cam_y = CAM_Y0 + (CAM_Y1 - CAM_Y0) * s
	cam_th = CAM_TH0 + (CAM_TH1 - CAM_TH0) * smooth(tt / CAM_T)
	cam_h = CAM_H0 + (CAM_H1 - CAM_H0) * ease_out(tt / CAM_T, 1.6)


func build_hdma(tt: float) -> void:
	var cu := (cam_x - X_MIN) * TPM
	var cv := (Y_MAX - cam_y) * TPM
	var th := deg_to_rad(cam_th)
	var fu := sin(th)
	var fv := -cos(th)
	var ru := cos(th)
	var rv := sin(th)
	var x0 := rnd(cu)
	var y0 := rnd(cv)
	regs = [x0, y0, x0 - 128, y0]
	for y in range(Y_H + 1, PLANE_END):
		var lam := F * cam_h * TPM / float(y - Y_H)
		var step := lam / F
		var a := clampi(rnd(step * ru * 256.0), -32768, 32767)
		var c := clampi(rnd(step * rv * 256.0), -32768, 32767)
		var b := clampi(rnd((cu - x0 + lam * fu) * 256.0 / float(y)), -32768, 32767)
		var d := clampi(rnd((cv - y0 + lam * fv) * 256.0 / float(y)), -32768, 32767)
		hdma_img.set_pixel(y, 0, Color(a, b, c, d))
	hdma_tex.update(hdma_img)
	var mat := plane.material as ShaderMaterial
	mat.set_shader_parameter("x0", regs[0])
	mat.set_shader_parameter("y0", regs[1])
	mat.set_shader_parameter("hofs", regs[2])
	mat.set_shader_parameter("vofs", regs[3])
	# Horizontebenen: waagrechter Versatz aus dem Kurs (ganze Pixel), Wolken treiben langsam
	hofs1 = rnd(F * th) + BG_HOFS0
	var sm := sky.material as ShaderMaterial
	sm.set_shader_parameter("hofs1", hofs1)
	sm.set_shader_parameter("hofs2", hofs1 - int(floor(tt * 2.0)))


func build_fixcol() -> void:
	## Farbaddition je Zeile: warmer Dunst, der zum Horizont hin zunimmt (in 5-Bit-Stufen).
	for y in range(Y_H + 1, PLANE_END):
		var k := y - Y_H
		var s := clampf(1.0 - float(k - 1) / float(HAZE_LINES), 0.0, 1.0)
		s = s * s
		fix_img.set_pixel(y, 0, Color(roundf(15.0 * s), roundf(7.0 * s), roundf(6.0 * s)))
	fix_tex.update(fix_img)


func _build_sky() -> void:
	## Himmelsverlauf: je Zeile ein 5-Bit-Wert der Hintergrundfarbe (CGRAM 0 per HDMA umgeschrieben).
	var stops: Array = backdrop["sky"]
	for y in Y_H + 1:
		var k := 0
		for i in stops.size():
			if int(stops[i][0]) <= y:
				k = i
		var c: Array = stops[k][1]
		var col := Vector3(c[0], c[1], c[2])
		if k < stops.size() - 1:
			var c2: Array = stops[k + 1][1]
			var f := float(y - int(stops[k][0])) / float(int(stops[k + 1][0]) - int(stops[k][0]))
			col = col.lerp(Vector3(c2[0], c2[1], c2[2]), f)
		sky_img.set_pixel(y, 0, Color8(rnd(roundf(col.x) * 255.0 / 31.0), rnd(roundf(col.y) * 255.0 / 31.0),
			rnd(roundf(col.z) * 255.0 / 31.0)))


# ---------------------------------------------------------------------------------------------
# CGRAM
# ---------------------------------------------------------------------------------------------
func cgram_color(i: int) -> Color:
	var c: Array = cgram_now[i] if cgram_now.size() == 256 else cgram_base[i]
	return Color8(rnd(c[0] * 255.0 / 31.0), rnd(c[1] * 255.0 / 31.0), rnd(c[2] * 255.0 / 31.0))


func _set5(name: String, c: Vector3) -> void:
	cgram_now[int(names[name])] = [clampi(rnd(c.x), 0, 31), clampi(rnd(c.y), 0, 31), clampi(rnd(c.z), 0, 31)]


func _base5(name: String) -> Vector3:
	var c: Array = cgram_base[int(names[name])]
	return Vector3(c[0], c[1], c[2])


func lighthouse_flash(tt: float) -> float:
	## Leuchtfeuer: alle 3,2 s ein Blitz (0,1 s an, 0,4 s abklingend), erster Blitz bei 1,1 s.
	var p := fmod(tt + 2.1, 3.2)
	if p < 0.1:
		return 1.0
	if p < 0.5:
		return 1.0 - (p - 0.1) / 0.4
	return 0.0


func build_cgram(tt: float) -> void:
	cgram_now = cgram_base.duplicate(true)
	var n := glint_seq.size()
	var step := int(floor(tt * 10.0))
	for k in 4:
		var key := "glint%d" % k
		cgram_now[int(names[key])] = glint_seq[(step + k * 3) % n]
	# Laterne: Flackern je 1/10 s aus der festen Zufallsfolge
	var fl := 0.72 + 0.28 * float(flicker[step % flicker.size()])
	_set5("obj.props.glass0", _base5("obj.props.glass0") * fl)
	_set5("obj.props.glass1", _base5("obj.props.glass1") * (0.86 + 0.14 * fl))
	for g in ["g1", "g2", "g3"]:
		_set5("obj.glow." + g, _base5("obj.glow." + g) * fl)
	# Fenster des Häuschens: langsames Glimmen
	var fw := 0.88 + 0.12 * sin(tt * 2.3) * float(flicker[(step / 3 + 500) % flicker.size()])
	_set5("obj.cottage.win0", _base5("obj.cottage.win0") * fw)
	# Leuchtfeuer
	var fla := lighthouse_flash(tt)
	var dim := _base5("bg.tower.lamp0")
	var bright := Vector3(31, 30, 22)
	_set5("bg.tower.lamp1", dim.lerp(bright, fla))
	# Bojenlicht: 1,2 s an, 1,2 s aus
	if fmod(tt, 2.4) >= 1.2:
		_set5("obj.props.light", Vector3(12, 9, 5))
	# Sterne funkeln
	if int(floor(tt * 4.0)) % 3 == 0:
		_set5("bg.clouds.star0", _base5("bg.clouds.star1"))
	for i in 256:
		var c: Array = cgram_now[i]
		cgram_img.set_pixel(i, 0, Color8(rnd(c[0] * 255.0 / 31.0), rnd(c[1] * 255.0 / 31.0), rnd(c[2] * 255.0 / 31.0)))
	cgram_tex.update(cgram_img)


# ---------------------------------------------------------------------------------------------
# Sprites (OAM)
# ---------------------------------------------------------------------------------------------
func project(wx: float, wy: float, alt: float = 0.0) -> Array:
	## Weltpunkt -> [Bild-x, Bild-y, Entfernung] wie m7lib.project(); leer, wenn hinter der Kamera.
	var th := deg_to_rad(cam_th)
	var du := (wx - cam_x) * TPM
	var dv := (cam_y - wy) * TPM
	var z := (du * sin(th) + dv * -cos(th)) / TPM
	var xr := (du * cos(th) + dv * sin(th)) / TPM
	if z <= 0.3:
		return []
	return [128.0 + F * xr / z, Y_H + F * (cam_h - alt) / z, z]


func pick_step(sheet: String, ideal_ppm: float) -> String:
	## Vorgezeichnete Größenstufe mit dem kleinsten Abstand im logarithmischen Maßstab.
	var best := ""
	var bd := 1e9
	for k in spr[sheet]["steps"]:
		var d: float = absf(log(float(spr[sheet]["steps"][k]["ppm"]) / ideal_ppm))
		if d < bd:
			bd = d
			best = k
	return best


func frame_of(sheet: String, step: String, fr: int, roll: int = 0) -> Dictionary:
	for f in spr[sheet]["steps"][step]["frames"]:
		if int(f["frame"]) == fr and int(f["roll"]) == roll:
			return f
	return spr[sheet]["steps"][step]["frames"][0]


func push(sheet: String, step: String, f: Dictionary, sx: float, sy: float, z: float, math := false,
		flip := false, dy := 0) -> void:
	var r: Array = f["rect"]
	var anc: Array = f["anchor"]
	var ax: float = float(anc[0]) if not flip else float(r[2]) - float(anc[0])
	var x := rnd(sx - ax)
	var y := rnd(sy - float(anc[1])) + dy
	oam.append({"sheet": sheet, "step": step, "rect": r, "x": x, "y": y, "z": z, "math": math, "flip": flip})


func badger_state(tt: float) -> Dictionary:
	var k := int(floor(tt * 15.0))
	var t_stop := walk_stop_k / 15.0
	if k < walk_stop_k:
		return {"x": WALK_X0 + WALK_V * k / 15.0, "sheet": "badger_walk", "frame": k % 8}
	var x := WALK_X0 + WALK_V * walk_stop_k / 15.0
	var dt := tt - t_stop
	if dt < 0.1:
		return {"x": x, "sheet": "badger_walk", "frame": walk_stop_k % 8}
	if dt < 0.1 + TURN_T:
		return {"x": x, "sheet": "badger_turn", "frame": 0}
	var dw := dt - 0.1 - TURN_T - WAVE_DELAY
	if dw >= 0.0 and dw < 6.0 / WAVE_FPS:
		return {"x": x, "sheet": "badger_wave", "frame": int(floor(dw * WAVE_FPS))}
	var idle := int(floor((dt - 0.1 - TURN_T) * 2.0)) % 4
	return {"x": x, "sheet": "badger_idle", "frame": idle}


func build_oam(tt: float) -> void:
	oam.clear()
	if not measure:
		_static_objects(tt)
		_gulls(tt)
		_lighthouse_halo(tt)
	var b := badger_state(tt)
	var p := project(b["x"], WALK_Y)
	if p.size() > 0:
		var sheet: String = b["sheet"]
		var st := pick_step("badger_walk", F / p[2])
		if not spr[sheet]["steps"].has(st):
			st = "1"
		var fr := frame_of(sheet, st, b["frame"])
		push(sheet, st, fr, p[0], p[1], p[2])
		if not measure:
			var ss := pick_step("shadow", F / p[2])
			push("shadow", ss, frame_of("shadow", ss, 0), p[0], p[1], p[2] + 0.001, true)
	# Zeichenreihenfolge: fern zuerst (auf der Konsole: nahe Objekte bekommen die kleineren OAM-Nummern)
	oam.sort_custom(func(a, c): return a["z"] > c["z"])
	# Farbmathematik gilt nur außerhalb des Dunstbands (dort addiert HDMA die feste Farbe zur Ebene)
	var kept := []
	for e in oam:
		if e["math"]:
			var r: Array = e["rect"]
			if e["y"] < Y_H + 1 + HAZE_LINES and e["y"] + int(r[3]) > Y_H + 1:
				continue
		kept.append(e)
	oam = kept


func _static_objects(tt: float) -> void:
	for o in OBJECTS:
		var kind: String = o[1]
		var p := project(o[2], o[3])
		if p.size() == 0 or p[0] < -80 or p[0] > W + 80:
			continue
		var st := pick_step(kind, F / p[2])
		var dy := 0
		var roll := 0
		if kind.begins_with("boat"):
			var ph := 0.0 if kind == "boat_a" else 1.7
			var s := sin(tt * TAU / 2.8 + ph)
			roll = 0 if s < -0.45 else (1 if s < 0.45 else 2)
			dy = 0 if sin(tt * TAU / 2.8 + ph + 1.2) < 0.3 else 1
		elif kind == "buoy":
			dy = 0 if sin(tt * TAU / 2.1 + float(o[2])) < 0.0 else 1
		var fr := frame_of(kind, st, 0, roll)
		var flip := kind == "lantern"      # Ausleger nach Osten: H-Spiegelung wie das Flip-Bit im OAM
		push(kind, st, fr, p[0], p[1], p[2], false, flip, dy)
		if kind == "lantern":
			var mk: Array = fr["marks"]["glass"]
			var wr: float = float(fr["rect"][2])
			var gx: float = p[0] - (wr - float(fr["anchor"][0])) + (wr - float(mk[0]))
			var gy: float = p[1] - float(fr["anchor"][1]) + float(mk[1])
			var gs := pick_step("glow", float(spr["lantern"]["steps"][st]["ppm"]) * 0.22)
			push("glow", gs, frame_of("glow", gs, 0), gx, gy, p[2] + 0.01, true)
		if kind == "cottage":
			_smoke(tt, p, fr, st)


func _smoke(tt: float, p: Array, fr: Dictionary, st: String) -> void:
	## Rauchwolken aus dem Schornstein: alle 0,35 s eine neue, steigt 2,4 s, wächst und treibt nach rechts.
	var ppm: float = float(spr["cottage"]["steps"][st]["ppm"])
	var mk: Array = fr["marks"]["chimney"]
	var cx: float = p[0] - float(fr["anchor"][0]) + float(mk[0])
	var cy: float = p[1] - float(fr["anchor"][1]) + float(mk[1])
	var first := int(floor((tt - 2.4) / 0.35)) + 1
	for i in range(first, int(floor(tt / 0.35)) + 1):
		var age := tt - i * 0.35
		if age < 0.0 or age > 2.4:
			continue
		var j: float = flicker[(i + 1000) % flicker.size()]
		var rise := 0.55 * age
		var drift := 0.28 * age + 0.1 * sin(age * 2.0 + j * 6.0)
		var rad := (0.22 + 0.22 * age) * ppm
		var k := clampi(rnd(rad) - 1, 0, 5)
		push("smoke", str(k), frame_of("smoke", str(k), 0), cx + drift * ppm, cy - rise * ppm,
			p[2] - 0.02 - age * 0.001, true)


func _gulls(tt: float) -> void:
	## Zwei Möwen: eine kreist über der Bucht, eine quert näher von rechts nach links.
	var paths := [
		[2.0 + 7.0 * cos(tt * 0.55), 21.0 + 5.0 * sin(tt * 0.55), 7.5, -sin(tt * 0.55)],
		[11.0 - 3.6 * fmod(tt, 9.0), 10.0 + 1.0 * fmod(tt, 9.0), 5.2 + 0.3 * sin(tt * 2.0), -1.0],
	]
	for g in paths.size():
		var q: Array = paths[g]
		var p := project(q[0], q[1], q[2])
		if p.size() == 0:
			continue
		var span: float = F / p[2] * 0.9         # Spannweite 0,9 m
		var st := pick_step("gull", span / 1.1)
		var ph := int(floor(tt * 10.0 + g * 2)) % 4
		push("gull", st, frame_of("gull", st, ph), p[0], p[1], p[2], false, float(q[3]) > 0.0)


func _lighthouse_halo(tt: float) -> void:
	var fla := lighthouse_flash(tt)
	if fla <= 0.15:
		return
	var lamp: Array = backdrop["lamp"]
	var sx := fposmod(float(lamp[0]) - hofs1, 512.0)
	if sx > W + 16:
		return
	var st := "0" if fla > 0.7 else ("1" if fla > 0.4 else "2")
	push("glow", st, frame_of("glow", st, 0), sx, float(lamp[1]), 9999.0, true)


func apply_oam() -> void:
	for i in pool.size():
		var s := pool[i]
		if i >= oam.size():
			s.visible = false
			continue
		var e: Dictionary = oam[i]
		var r: Array = e["rect"]
		s.visible = true
		s.region_rect = Rect2(r[0], r[1], r[2], r[3])
		s.position = Vector2(e["x"], e["y"])
		s.flip_h = e["flip"]
		s.material = mat_math if e["math"] else mat_obj


# ---------------------------------------------------------------------------------------------
# Textfenster
# ---------------------------------------------------------------------------------------------
func build_ui(tt: float) -> void:
	ui.visible_win = tt >= 0.15
	ui.slide = clampi(rnd(52.0 * (1.0 - ease_out((tt - 0.15) / 0.3, 2.0))), 0, 52)
	ui.chars = clampi(int(floor((tt - 0.6) * 40.0)), 0, 99)
	ui.parser_chars = clampi(int(floor((tt - 2.7) * 14.0)), 0, 12)
	ui.cursor_on = tt >= 2.5 and int(floor(tt * 30.0 / 12.0)) % 2 == 0
	ui.queue_redraw()


func _update(tt: float) -> void:
	# kleiner Zuschlag: die aufsummierte Zeit liegt sonst bei floor(t * 15) knapp unter der Bildgrenze
	var tc := tt + t0 + 1e-6
	if still >= 0.0:
		tc = still
	camera_at(CAM_T + 1.0 if measure else tc)
	if measure:
		cam_th = 0.0      # Laufweg parallel zur Bildebene, damit die Bodenzeile fest bleibt
	build_hdma(tc)
	build_fixcol()
	build_cgram(tc)
	build_oam(tc)
	apply_oam()
	build_ui(tc)
	if dump_file:
		_dump(tc)


func _dump(tc: float) -> void:
	## Prüfprotokoll je Bild (eine JSON-Zeile): Zeit, Kamera, Register, HDMA-Tabelle, OAM.
	var tab := []
	for y in range(Y_H + 1, PLANE_END):
		var c := hdma_img.get_pixel(y, 0)
		tab.append([int(c.r), int(c.g), int(c.b), int(c.a)])
	var o := []
	for e in oam:
		o.append([e["sheet"], e["step"], e["x"], e["y"], e["rect"], e["math"], e["flip"]])
	dump_file.store_line(JSON.stringify({"frame": frame, "t": tc, "cam": [cam_x, cam_y, cam_th, cam_h],
		"regs": regs, "hofs1": hofs1, "hdma": tab, "oam": o}))
	dump_file.flush()
