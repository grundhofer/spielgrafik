extends Node2D
## Hafen von Lornholm als 16-Bit-Konsolenbild (SNES Mode 1, 256×224).
## BG1 = Hafen, BG2 = Himmel und Meer (beide 4bpp, je Kachel eine von 7 Paletten mit 15 Farben),
## BG3 = Textfenster (2bpp, 3 Farben je Kachel, bg3.gd), Sprites = Dachs, Paket, Rauch, Möwen (obj.gd).
## Wie auf der Konsole kommt Bewegung aus drei Quellen: CGRAM-Werte je Bild (Lampe, Laterne, Fenster),
## HDMA-Tabelle mit einem horizontalen Versatz je Bildschirmzeile (Meer) und Sprites (OAM).
## Alle Farben liegen auf dem 5-Bit-Raster (BGR555), auch die zur Laufzeit berechneten.
## Zeit über delta aufsummiert, Zufall nur mit festem Seed: die Aufnahme ist reproduzierbar.

const WALK_FPS := 15.0            # 15 Laufbilder/s = jedes Bild 2 Aufnahmebilder bei 30 fps
const WALK_N := 45                # Laufbilder 0..44, danach Stehen (Bild 45 = Kontakt, siehe _badger)
const STOP_X := 156               # Sprite-Zelle (32×32) links beim Anhalten; der Dachs kommt von rechts
                                  # (H-Spiegelung wie das Flip-Bit im OAM) und bleibt vor dem offenen Wasser stehen
const CELL_Y := 118               # Sprite-Zelle oben; Sohle (Zeile 30) auf y = 148
const PARCEL_POS := Vector2i(136, 140)
const SMOKE_ORIGIN := Vector2(16, 24)
const LAMP_PERIOD := 3.2          # Leuchtfeuer: ein Aufblitzen je Umdrehung
const LAMP_PEAK := 1.6            # erstes Aufblitzen (weitere alle 3,2 s)

# BG3-Paletten 0..3 (CGRAM 0..15) in 5-Bit-Werten: [Füllung, Hell (Rahmen, Schrift), Dunkel (Kontur, Schatten)]
# Füllung von oben nach unten dunkler: je zwei Kachelzeilen eine Palette.
const BG3_FILL := [[6, 8, 22], [5, 6, 18], [4, 5, 15], [3, 4, 12]]
const BG3_LIGHT := [30, 30, 31]
const BG3_DARK := [2, 2, 7]

var t := 0.0
var frame := 0
var cgram_base := PackedColorArray()
var cgram_img: Image
var cgram_tex: ImageTexture
var hdma_img: Image
var hdma_tex: ImageTexture
var hdma := PackedInt32Array()
var bgmeta: Dictionary
var spr: Dictionary
var noise := PackedFloat32Array()
var probe_path := ""
var only := ""                     # Prüflauf: "badger" blendet alles außer dem Dachs aus
var probe_log: Array = []

# Zustand für obj.gd und bg3.gd
var oam: Array = []                # [{x, y, rect: Rect2i, pal, size}]
var title_open := 0.0
var box_open := 0.0
var chars := 0
var choices := false
var cursor := -1
var cursor_on := true

@onready var bg1: Sprite2D = $BG1
@onready var bg2: Sprite2D = $BG2
@onready var obj: Node2D = $OBJ
@onready var bg3: Node2D = $BG3


static func c5(v: float) -> int:
	## 8-Bit-Wert auf das 5-Bit-Raster der SNES-Palette (zurück als 8 Bit)
	var q := clampi(roundi(v * 31.0 / 255.0), 0, 31)
	return (q << 3) | (q >> 2)


static func col5(r5: int, g5: int, b5: int) -> Color:
	return Color8((r5 << 3) | (r5 >> 2), (g5 << 3) | (g5 >> 2), (b5 << 3) | (b5 >> 2))


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--probe="):
			probe_path = a.substr(8)
		if a.begins_with("--only="):
			only = a.substr(7)
		if a.begins_with("--t0="):
			t = float(a.substr(5))          # Prüflauf ab späterer Zeit (Dauerlauf von Wasser, Rauch, Möwen)
	bgmeta = JSON.parse_string(FileAccess.get_file_as_string("res://art/bg.json"))
	spr = JSON.parse_string(FileAccess.get_file_as_string("res://art/sprites.json"))
	cgram_base.resize(256)
	for i in 256:
		cgram_base[i] = Color(0, 0, 0)
	# BG3 (Textfenster): Palette p = CGRAM 4p..4p+3, Farbe 0 durchsichtig
	for p in 4:
		var f: Array = BG3_FILL[p]
		cgram_base[4 * p + 1] = col5(f[0], f[1], f[2])
		cgram_base[4 * p + 2] = col5(BG3_LIGHT[0], BG3_LIGHT[1], BG3_LIGHT[2])
		cgram_base[4 * p + 3] = col5(BG3_DARK[0], BG3_DARK[1], BG3_DARK[2])
	# CGRAM 0 = Hintergrundfarbe (nie sichtbar, BG2 deckt alles): dunkles Himmelblau
	cgram_base[0] = col5(3, 3, 12)
	var first := int(bgmeta["cgram_first"])
	var lst: Array = bgmeta["cgram"]
	for i in lst.size():
		cgram_base[first + i] = Color.html(lst[i])
	var op: Dictionary = spr["obj_palettes"]
	for p in op.keys():
		var arr: Array = op[p]
		for j in arr.size():
			cgram_base[128 + 16 * int(p) + 1 + j] = Color.html(arr[j])
	cgram_img = Image.create_empty(256, 1, false, Image.FORMAT_RGBA8)
	cgram_tex = ImageTexture.create_from_image(cgram_img)
	hdma_img = Image.create_empty(224, 1, false, Image.FORMAT_R8)
	hdma_tex = ImageTexture.create_from_image(hdma_img)
	hdma.resize(224)
	for s in [bg1, bg2]:
		var m := s.material as ShaderMaterial
		m.set_shader_parameter("cgram", cgram_tex)
		m.set_shader_parameter("hdma", hdma_tex)
	var rng := RandomNumberGenerator.new()
	rng.seed = 1991
	for i in 512:
		noise.append(rng.randf())
	_update()


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update()


func _smooth_noise(x: float, ofs: int) -> float:
	var i := int(floor(x))
	var f := x - i
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(noise[(i + ofs) % 512], noise[(i + 1 + ofs) % 512], f)


func _scaled(c: Color, k: float, white: float) -> Color:
	var r := c.r8 * k + (255.0 - c.r8 * k) * white
	var g := c.g8 * k + (255.0 - c.g8 * k) * white
	var b := c.b8 * k + (255.0 - c.b8 * k) * white
	return Color8(c5(r), c5(g), c5(b))


func _update_cgram() -> void:
	var cur := cgram_base.duplicate()
	var ph := (t - LAMP_PEAK) / LAMP_PERIOD
	var flash := pow(maxf(0.0, cos(TAU * ph)), 10.0)
	var lights: Dictionary = bgmeta["lights"]
	for i in lights["lamp"]:
		cur[int(i)] = _scaled(cgram_base[int(i)], 0.5 + 0.5 * flash, 0.45 * flash * flash)
	for i in lights["glint"]:
		cur[int(i)] = _scaled(cgram_base[int(i)], 0.45 + 0.55 * flash, 0.3 * flash * flash)
	var fl := _smooth_noise(t * 9.0, 0)
	for i in lights["lantern"]:
		cur[int(i)] = _scaled(cgram_base[int(i)], 0.74 + 0.26 * fl, 0.0)
	var wn := _smooth_noise(t * 2.5, 200)
	for i in lights["window"] + lights["keeper"]:
		cur[int(i)] = _scaled(cgram_base[int(i)], 0.88 + 0.12 * wn, 0.0)
	for i in 256:
		cgram_img.set_pixel(i, 0, cur[i])
	cgram_tex.update(cgram_img)


func _update_hdma() -> void:
	## Zeilenscroll für BG2 (Meer): ab der Horizontzeile ein Versatz je Zeile, nach vorn stärker.
	var top := int(bgmeta["sea_top"])
	for y in 224:
		var off := 0
		if y > top:
			var d := float(y - top) / float(224 - top)
			var amp := 0.55 + 2.2 * d
			var w := sin(0.62 * y - 3.1 * t) * 0.75 + sin(0.23 * y + 1.7 * t) * 0.25
			off = roundi(amp * w)
		hdma[y] = off
		hdma_img.set_pixel(y, 0, Color8(off + 128, 0, 0))
	hdma_tex.update(hdma_img)


func _walk_dist(n: int) -> int:
	var steps: Array = spr["walk"]["step_px"]
	var d := 0
	for i in n:
		d += int(steps[i % steps.size()])
	return d


func _badger() -> Dictionary:
	var fr: Dictionary = spr["frames"]
	var n := int(floor(t * WALK_FPS))
	var name := "stand"
	var x := STOP_X
	if n < WALK_N:
		name = "walk%d" % (n % 6)
		x = STOP_X + _walk_dist(WALK_N) - _walk_dist(n)
	elif n == WALK_N:
		name = "walk%d" % (n % 6)          # Kontaktbild (45 % 6 = 3), beide Füße am Boden
	else:
		# kurzer Gruß beim Öffnen des Fensters (Pfote hoch, Mund offen), danach Stehen mit zweimal Blinzeln
		if t >= 3.3 and t < 3.9:
			name = "talk"
		var blinks := [4.3, 5.55]
		for b in blinks:
			if t >= b and t < b + 0.1:
				name = "blink"
	var r: Array = fr[name]
	return {"x": x, "y": CELL_Y, "rect": Rect2i(r[0], r[1], r[2], r[3]), "pal": 0, "size": 32, "name": name, "flip": true}


func _smoke() -> Array:
	## Rauchwölkchen alle 0,4 s, 3 s Lebensdauer, 5 Größenstufen (die letzte zerfällt), ab 1,6 s dunklere Töne;
	## der Wind schiebt sie nach rechts. Positionen ganzzahlig.
	var out: Array = []
	var small: Dictionary = spr["small"]
	var every := 0.4
	var k := int(floor((t + 3.0) / every))
	var ages := [0.3, 0.8, 1.5, 2.2]
	for j in range(k - 8, k + 1):
		var born := j * every - 3.0
		var a := t - born
		if a < 0.0 or a >= 3.0:
			continue
		var stage := 0
		for s in ages:
			if a >= s:
				stage += 1
		var key := "smoke%d" % stage
		if a >= 1.6:
			key += "_old"
		var r: Array = small[key]
		var wob := sin(j * 1.7) * 1.5
		var px: float = SMOKE_ORIGIN.x + 2.5 * a + 2.0 * a * a + wob * minf(a, 1.0) - r[2] * 0.5
		var py: float = SMOKE_ORIGIN.y - 9.5 * a + 1.1 * a * a - r[3] * 0.5
		out.append({"x": roundi(px), "y": roundi(py), "rect": Rect2i(r[0], r[1], r[2], r[3]), "pal": 1, "size": 8})
	return out


func _gulls() -> Array:
	var out: Array = []
	var small: Dictionary = spr["small"]
	var defs := [[214.0, 34.0, -11.0, 0.0], [176.0, 22.0, -8.0, 0.37]]
	for g in defs:
		var x: float = fposmod(g[0] + g[2] * t + 20.0, 296.0) - 20.0
		var y: float = g[1] + 2.0 * sin(t * 1.3 + g[3] * 6.0)
		var flap := int(floor(t * 6.0 + g[3] * 6.0)) % 4
		var key := "gull0" if flap < 2 else "gull1"
		if int(floor(t / 1.5 + g[3])) % 2 == 1:
			key = "gull0"                     # gleitet: Flügel oben
		var r: Array = small[key]
		out.append({"x": roundi(x), "y": roundi(y), "rect": Rect2i(r[0], r[1], r[2], r[3]), "pal": 2, "size": 8})
	return out


func _update() -> void:
	_update_cgram()
	_update_hdma()
	oam = []
	var b := _badger()
	oam.append(b)
	if only == "badger":
		bg1.visible = false
		bg2.visible = false
		bg3.visible = false
		obj.queue_redraw()
		_log()
		return
	var pr: Array = spr["small"]["parcel"]
	oam.append({"x": PARCEL_POS.x, "y": PARCEL_POS.y, "rect": Rect2i(pr[0], pr[1], pr[2], pr[3]), "pal": 0, "size": 8, "tiles": 2})
	oam.append_array(_gulls())
	oam.append_array(_smoke())
	obj.queue_redraw()
	# Textfenster
	title_open = clampf((t - 0.1) / 0.27, 0.0, 1.0)
	box_open = clampf((t - 3.1) / 0.27, 0.0, 1.0)
	chars = maxi(0, int(floor((t - 3.4) * 60.0)))
	choices = t >= 4.5
	cursor = -1
	if t >= 4.6:
		cursor = 0 if t < 5.3 else 1
	cursor_on = true
	bg3.queue_redraw()
	_log()


func _log() -> void:
	## Prüfprotokoll (nur mit --probe=…): ein Eintrag je aufgenommenem Bild, daher nicht für den Aufruf aus _ready
	if probe_path != "" and frame > 0:
		var o: Array = []
		for e in oam:
			var rr: Rect2i = e["rect"]
			o.append([e["x"], e["y"], rr.size.x, rr.size.y, e["pal"], e.get("name", "")])
		probe_log.append({"f": frame, "t": t, "oam": o, "hdma": Array(hdma)})


func _exit_tree() -> void:
	if probe_path != "":
		var f := FileAccess.open(probe_path, FileAccess.WRITE)
		f.store_string(JSON.stringify(probe_log))
