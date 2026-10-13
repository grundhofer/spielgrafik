extends Node2D
## Hafen von Lornholm als illustriertes Textadventure auf einem 16-Bit-Heimcomputer (Amiga OCS, Lowres 320x200).
## Zwei Bildschirme übereinander wie zwei Intuition-Screens: oben das Bild (320x144, 32 Register aus 4096 Farben),
## unten der Textschirm (eigene 4 Farben). Das Bild wird zu Beginn von oben herabgezogen.
## Animation nur über Farbregister (Farbzyklus Wasser, Leuchtfeuer, Laterne, Fenster) und über Blitter-Objekte
## (Dachs aus vorgerenderten Einzelbildern mit Kontaktschatten, Rauch, Möwe). Zeit über delta aufsummiert, Zufall
## mit festem Seed.
## Nach der Eingabe "nimm paket" zieht sich, falls vorhanden, ein zweites Bild (Nahaufnahme des Dachses, eigene
## 32 Register) über das erste herab; während des Ziehens gelten oberhalb der Kante die neuen, darunter die alten
## Register (wie ein Copper-Wechsel der Palette an einer Rasterzeile).

const PIC_H := 144
const ROLL_T0 := 0.10           # Bild wird ab hier herabgezogen ...
const ROLL_T1 := 0.95           # ... und ist hier ganz unten
const LAMP_PERIOD := 3.0        # Kennung des Leuchtfeuers: zwei Blitze alle 3 s
const LAMP_OFFSET := 1.6        # erster Blitz
const TYPE_T0 := 2.25           # erster Tastendruck im Parser (text_screen.gd)
const ENTER_T := 3.60           # Eingabetaste: Antwortzeile erscheint
const CLOSE_T0 := 3.85          # Nahaufnahme wird herabgezogen ...
const CLOSE_T1 := 4.60          # ... und ist hier ganz unten

var t := 0.0
var meta: Dictionary
var bj: Dictionary
var flick := PackedFloat32Array()
var roll := 0                   # sichtbare Zeilen des Bildes (0..145)
var roll2 := 0                  # sichtbare Zeilen der Nahaufnahme (0..145)
var stop_x := 150
var feet_y := 133
var has_close := false
var pic := {}                   # Palette des Hafenbilds: base, now, img, tex
var close := {}                 # Palette der Nahaufnahme

@onready var picture: Node2D = $PictureClip/Picture
@onready var bg: Sprite2D = $PictureClip/Picture/Background
@onready var badger: Sprite2D = $PictureClip/Picture/Badger
@onready var smoke: Node2D = $PictureClip/Picture/Smoke
@onready var gull: Node2D = $PictureClip/Picture/Gull
@onready var shadow: Node2D = $PictureClip/Picture/Shadow
@onready var close_clip: Control = $CloseClip
@onready var close_pic: Node2D = $CloseClip/Close
@onready var close_bg: Sprite2D = $CloseClip/Close/Background
@onready var text_screen: Node2D = $TextScreen


func _palette(m: Dictionary, sprite: Sprite2D) -> Dictionary:
	## Registersatz eines Bildes: Grundwerte aus palette.json, 32x1-Textur für den Shader
	var p := {"meta": m, "base": PackedColorArray(), "now": PackedColorArray()}
	for h in m["rgb"]:
		p["base"].append(Color.html(String(h)))
	p["now"].resize(32)
	p["img"] = Image.create_empty(32, 1, false, Image.FORMAT_RGBA8)
	p["tex"] = ImageTexture.create_from_image(p["img"])
	(sprite.material as ShaderMaterial).set_shader_parameter("palette_tex", p["tex"])
	return p


func _ready() -> void:
	meta = JSON.parse_string(FileAccess.get_file_as_string("res://art/palette.json"))
	bj = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	pic = _palette(meta, bg)
	stop_x = int(meta.get("stop_x", 150))
	feet_y = int(meta.get("feet_line", 133))
	# Nahaufnahme nur, wenn sie gebaut ist (scripts/build_assets.py --picture closeup)
	has_close = FileAccess.file_exists("res://art/closeup_palette.json") and ResourceLoader.exists("res://art/closeup_index.png")
	close_clip.visible = false
	if has_close:
		close_bg.texture = load("res://art/closeup_index.png")
		close = _palette(JSON.parse_string(FileAccess.get_file_as_string("res://art/closeup_palette.json")), close_bg)
	var rng := RandomNumberGenerator.new()
	rng.seed = 1987
	for i in 256:
		flick.append(rng.randf())
	if "--probe-badger" in OS.get_cmdline_user_args():
		# Prüflauf: nur der Dachs vor schwarzem Grund (scripts/probe.py misst Füße und Kopf)
		bg.visible = false
		smoke.visible = false
		gull.visible = false
		shadow.visible = false
		$PictureClip/Picture/Edge.visible = false
		text_screen.visible = false
		has_close = false
	_update()


func _process(delta: float) -> void:
	t += delta
	_update()


static func q12(c: Color) -> Color:
	## Amiga-Farbregister: 4 Bit je Kanal (Werte n*17)
	return Color8(clampi(roundi(c.r * 15.0), 0, 15) * 17, clampi(roundi(c.g * 15.0), 0, 15) * 17,
			clampi(roundi(c.b * 15.0), 0, 15) * 17)


func reg(i: int) -> Color:
	## aktueller Wert eines Farbregisters des Hafenbilds (für Rauch und Möwe)
	return pic["now"][i]


func _noise(x: float) -> float:
	var i := int(floor(x))
	var f := x - i
	f = f * f * (3.0 - 2.0 * f)
	return lerpf(flick[posmod(i, 256)], flick[posmod(i + 1, 256)], f)


func _lamp_level(tt: float) -> float:
	## zwei kurze Blitze (0,25 s) im Abstand von 0,6 s, dann Pause; dazwischen glimmt die Lampe.
	## Versatz 1,6 s: Blitze bei 1,6/2,2 s (Totale) und 4,6/5,2 s (Nahaufnahme ist dann ganz unten)
	var p := fposmod(tt - LAMP_OFFSET, LAMP_PERIOD)
	for s in [0.0, 0.6]:
		var d: float = p - s
		if d >= 0.0 and d < 0.25:
			return 1.0 - d / 0.25 * 0.3
	return 0.0


func _update_palette(p: Dictionary) -> void:
	var base: PackedColorArray = p["base"]
	var now: PackedColorArray = p["now"]
	for i in 32:
		now[i] = base[i]
	var g: Dictionary = p["meta"]["groups"]
	# Farbzyklus Wasser: Register start..start+len-1 rotieren in ganzen Schritten (wie CRNG in DPaint)
	var w: Dictionary = g["water"]
	var ws := int(w["start"])
	var wn := int(w["len"])
	var steps := int(floor(t * float(w["steps_per_second"])))
	for j in wn:
		now[ws + j] = base[ws + posmod(j - steps, wn)]
	# Leuchtfeuer: Lampe und Lichthof
	var lv := _lamp_level(t)
	var lamp := int(g["lamp"])
	var dim := Color(0.80, 0.45, 0.18)      # glimmt warm zwischen den Blitzen
	now[lamp] = q12(dim.lerp(Color(1, 1, 0.93), lv))
	var halo := int(g["halo"])
	now[halo] = q12(Color.html(String(g["halo_off"])).lerp(Color.html(String(g["halo_on"])), lv))
	# Laterne flackert, Fenster glimmt (Registerwerte, keine Pixeländerung)
	var la := int(g["lantern"])
	var f := 0.72 + 0.32 * _noise(t * 9.0) + 0.05 * sin(t * 31.0)
	now[la] = q12(base[la] * f)
	var wi := int(g["window"])
	now[wi] = q12(base[wi] * (0.9 + 0.1 * _noise(t * 2.5 + 50.0)))
	var img: Image = p["img"]
	for i in 32:
		img.set_pixel(i, 0, now[i])
	(p["tex"] as ImageTexture).update(img)
	p["now"] = now


func _ease(a: float, b: float, x: float) -> float:
	var k := clampf((x - a) / (b - a), 0.0, 1.0)
	return k * k * (3.0 - 2.0 * k)


func _update_badger() -> void:
	var frames: Array = bj["frames"]
	var fps := float(bj["fps"])
	var k := mini(int(floor(t * fps + 1e-4)), frames.size() - 1)
	var cell: Array = bj["cell"]
	var fr: Dictionary = frames[k]
	badger.frame = k
	badger.position = Vector2(stop_x + int(fr["left"]), feet_y - (int(cell[1]) - int(bj["foot_margin"])))


func _update() -> void:
	roll = roundi(145.0 * _ease(ROLL_T0, ROLL_T1, t))
	picture.position = Vector2(0, roll - 145)
	_update_palette(pic)
	_update_badger()
	if has_close:
		roll2 = roundi(145.0 * _ease(CLOSE_T0, CLOSE_T1, t))
		close_clip.visible = roll2 > 0
		close_pic.position = Vector2(0, roll2 - 145)
		_update_palette(close)
	smoke.queue_redraw()
	gull.queue_redraw()
	shadow.queue_redraw()
	text_screen.queue_redraw()
