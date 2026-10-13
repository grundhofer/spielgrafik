extends Node2D
## Hafen von Lornholm als Befehlsmenü-Adventure eines japanischen 16-Bit-PCs (640x400, 16 aus 4096 Farben).
## Alles wird als Palettenindex 0..15 in den SubViewport "VRAM" gezeichnet (Rotkanal = Index / 15); der Shader
## des Sprite "Display" schlägt jede Farbe in 16 Palettenregistern nach, deren Kanäle nur 4 Bit haben.
## Animation sparsam wie bei den Vorbildern: Leuchtfeuer und Fenster über Palettenwechsel, Wasser über
## 3 Einzelbilder, Dachs-Porträt mit Blinzeln und Mundbewegung, Text Zeichen für Zeichen.
## Zeit wird über delta aufsummiert, Zufall nur mit festem Seed: die Aufnahme ist reproduzierbar.

const FPS := 30
const REVEAL_FROM := 12          # Bild 12..27: Porträt erscheint im 4x4-Kachelmuster (16 Stufen)
const REVEAL_FRAMES := 16
const TEXT_FROM := 36            # Bild, ab dem der Text läuft
const WATER_HOLD := 6            # Wasser: Bildwechsel alle 6 Bilder (5 Bilder/s)
const MOUTH_HOLD := 5            # Mund: Wechsel alle 5 Bilder (6 Bilder/s)
const LAMP_PERIOD := 90          # Leuchtfeuer: ein Blitz alle 3 s
const GLOW_HOLD := 3             # Fensterlicht: neuer Flackerwert alle 3 Bilder
const BLINKS := [66, 156]        # Bildnummern, an denen ein Lidschlag beginnt
# Lidschlag: halb, halb, zu, zu, zu, halb, halb (Index ins Augen-Teilbild, -1 = offen)
const BLINK_SEQ := [0, 0, 1, 1, 1, 0, 0]
# Mund beim Sprechen: 0 zu, 1 halb, 2 offen (festes Muster statt Zufall)
const TALK := [1, 2, 1, 0, 2, 2, 1, 0, 1, 2, 1, 1, 0, 2, 1, 2, 0, 1, 2, 1]

var t := 0.0
var meta: Dictionary
var pal_base: Array[Color] = []
var pal_img: Image
var pal_tex: ImageTexture
var glow_seq: Array[Color] = []
var lamp_on: Color
var lamp_off: Color
var idx_glow := 14
var idx_lamp := 15

@onready var vram: SubViewport = $VRAM
@onready var display: Sprite2D = $Display
@onready var bg: Sprite2D = $VRAM/BG
@onready var water: Sprite2D = $VRAM/Water
@onready var badger: Node2D = $VRAM/Badger
@onready var body: Sprite2D = $VRAM/Badger/Body
@onready var eyes: Sprite2D = $VRAM/Badger/Eyes
@onready var mouth: Sprite2D = $VRAM/Badger/Mouth
@onready var ui: Node2D = $VRAM/UI


func _ready() -> void:
	meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/meta.json"))
	for h in meta["palette"]:
		pal_base.append(_c12(Color.html(String(h))))
	idx_glow = int(meta["index"]["glow"])
	idx_lamp = int(meta["index"]["lamp"])
	lamp_on = _c12(Color.html(String(meta["lamp_on"])))
	lamp_off = _c12(Color.html(String(meta["lamp_off"])))
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	var steps: Array = meta["glow_steps"]
	for i in 80:
		# meist die Grundfarbe, ab und zu ein dunklerer oder hellerer Wert
		var r := rng.randf()
		var k := 0 if r < 0.45 else (1 if r < 0.75 else (2 if r < 0.9 else 3))
		glow_seq.append(_c12(Color.html(String(steps[k]))))
	pal_img = Image.create_empty(16, 1, false, Image.FORMAT_RGBA8)
	pal_tex = ImageTexture.create_from_image(pal_img)
	(display.material as ShaderMaterial).set_shader_parameter("palette_tex", pal_tex)
	display.texture = vram.get_texture()

	var scene: Array = meta["scene"]
	bg.texture = load("res://art/bg.png")
	bg.position = Vector2(scene[0], scene[1])
	water.texture = load("res://art/water.png")
	water.hframes = int(meta["water_frames"])
	water.position = bg.position
	var bp: Array = meta["badger_pos"]
	badger.position = Vector2(bp[0], bp[1])
	body.texture = load("res://art/badger_body.png")
	eyes.texture = load("res://art/badger_eyes.png")
	eyes.hframes = int(meta["eyes_frames"])
	eyes.position = Vector2(meta["eyes_pos"][0], meta["eyes_pos"][1])
	mouth.texture = load("res://art/badger_mouth.png")
	mouth.hframes = int(meta["mouth_frames"])
	mouth.position = Vector2(meta["mouth_pos"][0], meta["mouth_pos"][1])
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


static func _c12(c: Color) -> Color:
	## Kanal auf 4 Bit runden (16 Stufen je Kanal, 4096 Farben) wie ein Palettenregister
	return Color(roundf(c.r * 15.0) / 15.0, roundf(c.g * 15.0) / 15.0, roundf(c.b * 15.0) / 15.0, 1.0)


func frame() -> int:
	return int(floor(t * FPS + 0.001))


func _update() -> void:
	var f := frame()
	# Palette: Grundwerte, dann die zwei animierten Register
	var pal: Array[Color] = pal_base.duplicate()
	pal[idx_glow] = glow_seq[(f / GLOW_HOLD) % glow_seq.size()]
	pal[idx_lamp] = _lamp(f)
	for i in 16:
		pal_img.set_pixel(i, 0, pal[i])
	pal_tex.update(pal_img)

	water.frame = (f / WATER_HOLD) % water.hframes

	var rv := clampi(f - REVEAL_FROM + 1, 0, REVEAL_FRAMES)
	(badger.material as ShaderMaterial).set_shader_parameter("reveal", float(rv) / REVEAL_FRAMES)

	# Lidschlag
	var e := -1
	for b in BLINKS:
		var k: int = f - int(b)
		if k >= 0 and k < BLINK_SEQ.size():
			e = BLINK_SEQ[k]
	eyes.visible = e >= 0
	if e >= 0:
		eyes.frame = e

	# Mund folgt dem Text: offen/halb/zu nach festem Muster, solange Zeichen erscheinen; in Pausen zu
	var m := 0
	if ui.is_typing(f):
		m = TALK[((f - TEXT_FROM) / MOUTH_HOLD) % TALK.size()]
	mouth.visible = m > 0
	if m > 0:
		mouth.frame = m - 1
	ui.set_frame(f)


func _lamp(f: int) -> Color:
	## Blitzfeuer: dunkel, 4 Stufen hell, 9 Bilder voll, 4 Stufen dunkel. Zwischenwerte auf 4 Bit gerundet.
	var p := (f + 25) % LAMP_PERIOD
	var ramp := [0.25, 0.5, 0.75, 1.0]
	var s := 0.0
	if p < 8:
		s = ramp[p / 2]
	elif p < 17:
		s = 1.0
	elif p < 25:
		s = ramp[3 - (p - 17) / 2]
	return _c12(lamp_off.lerp(lamp_on, s))
