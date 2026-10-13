extends Node2D
## Hafen von Lornholm im Stil eines VGA-Adventures (320x200, 256 Farben).
## Eine Palette für alles: der Hintergrund ist ein Indexbild, die Palette wird jedes Bild neu gesetzt
## (Farbzyklus für Wasser, Sterne und Leuchtturmlampe, Flackern für Laterne und Fenster).
## Wie beim VGA-DAC hat jeder Kanal nur 6 Bit (64 Stufen): auch berechnete Farben (Flackern) werden gerundet.
## Zeit wird über delta aufsummiert, Zufall nur mit festem Seed: die Aufnahme ist reproduzierbar.

const FEET_Y := 147              # Fußlinie des Dachses auf dem Kai
const WALK_FPS := 10.0           # geht in 30 fps auf (jedes Laufbild 3 Bilder lang); 12 fps ergab Haltezeiten 3-2-3-2
const WALK_FRAMES := 29          # Laufbilder 0..28; das letzte ist wieder Kontakt (Zyklusbild 0), dann Stehen
const STOP_X := 206.0
const STOP_T := WALK_FRAMES / WALK_FPS   # 2,9 s
const TALK_T := STOP_T + 0.2     # nach kurzem Blinzeln beginnt die Rede
const BEAM_PERIOD := 4.8         # eine Umdrehung des Leuchtfeuers in Sekunden

var t := 0.0
var pal_base := PackedInt32Array()     # 256 Grundfarben als 0xRRGGBB
var pal_bytes := PackedByteArray()
var pal_img: Image
var pal_tex: ImageTexture
var meta: Dictionary
var spr: Dictionary
var flick := PackedFloat32Array()
var beam_angle := 0.0

# Zustand, den UI, Rauch und Möwe lesen
var badger_x := STOP_X
var walk_total := 0              # Strecke über alle Bildwechsel (px), daraus ergibt sich der Startpunkt
var talking := false
var sentence := ""
var sentence_flash := false
var verb_hi := ""
var cursor := Vector2(150, 96)

@onready var bg: Sprite2D = $Background
@onready var badger: Sprite2D = $Badger
@onready var ui: Node2D = $UI
@onready var smoke: Node2D = $Smoke
@onready var gull: Node2D = $Gull
@onready var parcel: Sprite2D = $Parcel

var walk_tex: Texture2D = preload("res://art/badger_walk.png")
var stand_tex: Texture2D = preload("res://art/badger_stand.png")

const TALK := [1, 2, 1, 0, 2, 1, 2, 0, 1, 2, 2, 1, 0, 1, 2, 1, 0, 2, 1, 0]


func _ready() -> void:
	meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/palette.json"))
	spr = JSON.parse_string(FileAccess.get_file_as_string("res://art/sprites.json"))
	for h in meta["palette"]:
		pal_base.append(String(h).hex_to_int())
	pal_bytes.resize(256 * 4)
	pal_img = Image.create_empty(256, 1, false, Image.FORMAT_RGBA8)
	pal_tex = ImageTexture.create_from_image(pal_img)
	var sm := bg.material as ShaderMaterial
	sm.set_shader_parameter("palette_tex", pal_tex)
	var bm: Dictionary = meta["beam"]     # Lichtkegel-Stufen aus build_bg.py
	sm.set_shader_parameter("beam_levels", int(bm["levels"]))
	sm.set_shader_parameter("beam_gain", float(bm["gain"]))
	sm.set_shader_parameter("beam_band", float(bm["band"]))
	sm.set_shader_parameter("beam_cut", float(bm["cut"]))
	sm.set_shader_parameter("beam_soft", float(bm["soft"]))
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for i in 256:
		flick.append(rng.randf())
	walk_total = _walk_offset(WALK_FRAMES - 1)
	var pp: Array = spr["parcel"]["pos"]     # Lage des Pakets am Kai (build_sprites.py, PARCEL_POS)
	parcel.position = Vector2(int(pp[0]), int(pp[1]))
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


func color(i: int) -> Color:
	## Farbe eines Paletteneintrags im aktuellen Bild (für Rauch, Möwe, Text)
	return Color8(pal_bytes[i * 4], pal_bytes[i * 4 + 1], pal_bytes[i * 4 + 2])


func _dac(v: float) -> int:
	## VGA-DAC: 6 Bit je Kanal; 0..255 auf 64 Stufen runden und wie build_bg.vga6 auf 8 Bit zurückspreizen
	var v6 := clampi(roundi(v * 63.0 / 255.0), 0, 63)
	return (v6 << 2) | (v6 >> 4)


func _set_rgb(i: int, rgb: int, scale := 1.0) -> void:
	# Erste Fassung skalierte Laterne und Fenster stufenlos auf beliebige 8-Bit-Werte; jetzt DAC-Raster
	pal_bytes[i * 4] = _dac(((rgb >> 16) & 255) * scale)
	pal_bytes[i * 4 + 1] = _dac(((rgb >> 8) & 255) * scale)
	pal_bytes[i * 4 + 2] = _dac((rgb & 255) * scale)
	pal_bytes[i * 4 + 3] = 255


func _noise(x: float) -> float:
	var i := int(floor(x))
	var f := x - i
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(flick[posmod(i, 256)], flick[posmod(i + 1, 256)], f)


func _update_palette() -> void:
	for i in 256:
		_set_rgb(i, pal_base[i])
	var g: Dictionary = meta["groups"]
	# Wasser: echte Palettenrotation in 8 Tonstufen zu je 6 Einträgen, schrittweise wie auf dem PC;
	# der Maskenrand rotiert gleich, aber mit schwächeren Einträgen (weicher Übergang)
	for key in ["water", "water_edge"]:
		var w: Dictionary = g[key]
		var wn := int(w["len"])
		var steps := int(floor(t * float(w["steps_per_second"])))
		for tone in int(w["tones"]):
			var s0 := int(w["start"]) + tone * wn
			for j in wn:
				_set_rgb(s0 + j, pal_base[s0 + posmod(j - steps, wn)])
	# Sterne: 4 Einträge rotieren langsam
	var st: Dictionary = g["stars"]
	var ss := int(floor(t * float(st["steps_per_second"])))
	for j in 4:
		_set_rgb(int(st["start"]) + j, pal_base[int(st["start"]) + posmod(j - ss, 4)])
	# Leuchtturmlampe: 8 Spalten-Einträge rotieren synchron zum Strahl (heller Fleck wandert über die Linse)
	var lp := int(g["lamp"]["start"])
	var sh := roundi(-(beam_angle - PI / 2.0) / TAU * 8.0)
	for j in 8:
		_set_rgb(lp + j, pal_base[lp + posmod(j - sh, 8)])
	# Laterne: Glas und Lichthof flackern (Palettenwerte, keine Pixeländerung)
	var f := 0.80 + 0.30 * _noise(t * 11.0) + 0.04 * sin(t * 37.0)
	var la := int(g["lantern"]["start"])
	for j in 4:
		_set_rgb(la + j, pal_base[la + j], f)
		_set_rgb(la + 4 + j, pal_base[la + 4 + j], 1.0 + (f - 1.0) * 0.6)
	var wi := int(g["window"]["start"])
	var fw := 0.94 + 0.08 * _noise(t * 3.0 + 40.0)
	for j in 4:
		_set_rgb(wi + j, pal_base[wi + j], fw)
	pal_img.set_data(256, 1, false, Image.FORMAT_RGBA8, pal_bytes)
	pal_tex.update(pal_img)


func _walk_offset(n: int) -> int:
	## Strecke nach n Bildwechseln. Der Körper rückt je Bildwechsel um den in sprites.json gemessenen
	## Vorschub vor (3/3/2/2 px), damit der Standfuß auf dem Kai stehen bleibt statt zu rutschen.
	var steps: Array = spr["walk"]["step_px"]
	var per_cycle := 0
	for s in steps:
		per_cycle += int(s)
	var d := (n / steps.size()) * per_cycle
	for i in n % steps.size():
		d += int(steps[i])
	return d


func walk_x(tt: float) -> float:
	var n := mini(int(floor(tt * WALK_FPS)), WALK_FRAMES - 1)
	return STOP_X + float(walk_total - _walk_offset(n))


func _update_badger() -> void:
	var walk: Dictionary = spr["walk"]
	var stand: Dictionary = spr["stand"]
	if t < STOP_T:
		badger_x = walk_x(t)
		badger.texture = walk_tex
		badger.hframes = int(walk["frames"])
		badger.frame = int(floor(t * WALK_FPS)) % int(walk["frames"])
		_place(walk)
		talking = false
	else:
		badger_x = STOP_X
		badger.texture = stand_tex
		badger.hframes = int(stand["frames"])
		var fr := 0
		talking = t >= TALK_T
		if t < STOP_T + 0.09:
			# Übergangsbild (Rumpf des letzten Laufbilds, Stehbeine) für 3 Aufnahmebilder: Beine und Rumpf
			# wechseln nacheinander statt gleichzeitig
			fr = int(stand["transition_frame"])
		elif talking:
			fr = TALK[int(floor((t - TALK_T) * 6.0)) % TALK.size()]
		elif t > STOP_T + 0.08 and t < STOP_T + 0.18:
			fr = 3  # Blinzeln
		badger.frame = fr
		_place(stand)


func _place(info: Dictionary) -> void:
	# läuft nach links: Sprite gespiegelt, Anker (Kopfmitte) bleibt auf badger_x
	var cell: Array = info["cell"]
	badger.flip_h = true
	var ax := float(cell[0]) - float(info["anchor_x"])
	badger.position = Vector2(roundi(badger_x - ax), FEET_Y - int(cell[1]))


func _ease(a: float, b: float, x: float) -> float:
	var k := clampf((x - a) / (b - a), 0.0, 1.0)
	return k * k * (3.0 - 2.0 * k)


func _update_cursor() -> void:
	var p_sea := Vector2(150, 96)
	var p_lh := Vector2(292, 42)
	var p_badger := Vector2(walk_x(2.5) - 2.0, 120)
	# Die Lücke in der Mitte des Fadenkreuzes liegt über der oberen rechten Paketecke: die Arme laufen nur über
	# die Kontur, und der Cursor zielt auf das Paket (erste Fassung stand 6 px daneben)
	var pp: Array = spr["parcel"]["pos"]
	var p_parcel := Vector2(int(pp[0]) + 12, int(pp[1]))
	var p := p_sea
	p = p.lerp(p_lh, _ease(0.9, 1.5, t))
	p = p.lerp(p_badger, _ease(1.8, 2.5, t))
	p = p.lerp(p_parcel, _ease(3.0, 3.4, t))
	cursor = p.round()
	verb_hi = ""
	sentence_flash = false
	if t < 1.35:
		sentence = "Gehe zu Hafen"
	elif t < 2.0:
		sentence = "Gehe zu Leuchtturm"
	elif t < 3.05:
		verb_hi = "Rede mit"
		sentence = "Rede mit Dachs-Kurier" if t >= 2.35 else "Rede mit"
		sentence_flash = t >= 2.65 and t < 2.9
	else:
		verb_hi = "Nimm"
		sentence = "Nimm Paket" if t >= 3.3 else "Nimm"


func _update() -> void:
	beam_angle = -PI / 2.0 + TAU * t / BEAM_PERIOD
	(bg.material as ShaderMaterial).set_shader_parameter("beam_angle", beam_angle)
	_update_palette()
	_update_badger()
	_update_cursor()
	smoke.queue_redraw()
	gull.queue_redraw()
	ui.queue_redraw()
