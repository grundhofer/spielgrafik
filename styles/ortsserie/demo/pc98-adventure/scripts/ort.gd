extends Node2D
## Ein Ort der Ortsserie im Stil pc98-adventure (16 aus 4096 Farben, 640x360-Ausschnitt des 640x400-Schirms, ×2).
## Alles wird als Palettenindex 0..15 in den SubViewport "VRAM" gezeichnet (Rotkanal = Index / 15); der Shader von
## "Display" schlägt jede Farbe in 16 Palettenregistern nach, deren Kanäle 4 Bit haben. Bewegung wie bei den
## Vorbildern sparsam: animierte Palettenregister (Licht) und wenige Einzelbilder (Wasser, Linse), keine Figur.
## Daten je Ort aus build_ort.py: art/<ort>/meta.json, bg.png und Streifen. Zeit aus dem Bildzähler (30 Bilder/s),
## Zufall nur mit festem Seed: jede Aufnahme ist gleich.

@export var ort := "leuchtturm"

const BASE := "res://pc98-adventure"

var n := 0
var meta: Dictionary
var pal_base: Array[Color] = []
var pal_img: Image
var pal_tex: ImageTexture
var regs: Array = []                 # [{index, mode, ...}] aus meta.json
var strips: Array = []               # [[Sprite2D, frames, hold]]

@onready var vram: SubViewport = $VRAM
@onready var display: Sprite2D = $Display
@onready var bg: Sprite2D = $VRAM/BG
@onready var anim: Node2D = $VRAM/Anim
@onready var ui: Node2D = $VRAM/UI


func _ready() -> void:
	var dir := BASE + "/art/" + ort
	meta = JSON.parse_string(FileAccess.get_file_as_string(dir + "/meta.json"))
	for h in meta["palette"]:
		pal_base.append(_c12(Color.html(String(h))))
	for r in meta["registers"]:
		var reg: Dictionary = r.duplicate()
		if String(reg["mode"]) == "flicker":
			var rng := RandomNumberGenerator.new()
			rng.seed = int(reg["seed"])
			var seq: Array[Color] = []
			var steps: Array = reg["steps"]
			for i in 80:
				var x := rng.randf()
				var k := 0 if x < 0.45 else (1 if x < 0.75 else (2 if x < 0.9 else 3))
				seq.append(_c12(Color.html(String(steps[mini(k, steps.size() - 1)]))))
			reg["seq"] = seq
		regs.append(reg)
	pal_img = Image.create_empty(16, 1, false, Image.FORMAT_RGBA8)
	pal_tex = ImageTexture.create_from_image(pal_img)
	(display.material as ShaderMaterial).set_shader_parameter("palette_tex", pal_tex)
	display.texture = vram.get_texture()

	var scene: Array = meta["scene"]
	bg.texture = load(dir + "/bg.png")
	bg.position = Vector2(scene[0], scene[1])
	for s in meta["strips"]:
		var sp := Sprite2D.new()
		sp.centered = false
		sp.texture = load(dir + "/" + String(s["file"]))
		sp.hframes = int(s["frames"])
		sp.position = Vector2(scene[0] + int(s["pos"][0]), scene[1] + int(s["pos"][1]))
		anim.add_child(sp)
		strips.append([sp, int(s["frames"]), int(s["hold"])])
	ui.setup(meta, BASE + "/fonts")
	_update(0)


func _process(_delta: float) -> void:
	_update(n)
	n += 1


static func _c12(c: Color) -> Color:
	## Kanal auf 4 Bit runden (16 Stufen je Kanal, 4096 Farben) wie ein Palettenregister
	return Color(roundf(c.r * 15.0) / 15.0, roundf(c.g * 15.0) / 15.0, roundf(c.b * 15.0) / 15.0, 1.0)


func _update(f: int) -> void:
	var pal: Array[Color] = pal_base.duplicate()
	for reg in regs:
		pal[int(reg["index"])] = _register(reg, f)
	for i in 16:
		pal_img.set_pixel(i, 0, pal[i])
	pal_tex.update(pal_img)
	for s in strips:
		var sp: Sprite2D = s[0]
		sp.frame = (f / int(s[2])) % int(s[1])
	ui.set_frame(f)


func _register(reg: Dictionary, f: int) -> Color:
	match String(reg["mode"]):
		"flicker":
			## Flackern: alle hold Bilder ein Wert aus einer festen Folge (meist Grundwert, ab und zu dunkler/heller)
			var seq: Array = reg["seq"]
			return seq[(f / int(reg["hold"])) % seq.size()]
		"flash":
			## Blitzfeuer: aus, 4 Stufen hell, voll, 4 Stufen dunkel; Zwischenwerte auf 4 Bit gerundet
			var off := _c12(Color.html(String(reg["off"])))
			var on := _c12(Color.html(String(reg["on"])))
			var p := (f + int(reg["phase"])) % int(reg["period"])
			var ramp := [0.25, 0.5, 0.75, 1.0]
			var s := 0.0
			if p < 8:
				s = ramp[p / 2]
			elif p < 17:
				s = 1.0
			elif p < 25:
				s = ramp[3 - (p - 17) / 2]
			return _c12(off.lerp(on, s))
		"pulse":
			## Langsames Atmen zwischen zwei Farben in 4-Bit-Stufen (Dreieck, Wechsel nur alle hold Bilder)
			var a := _c12(Color.html(String(reg["a"])))
			var b := _c12(Color.html(String(reg["b"])))
			var per := int(reg["period"])
			var q := ((f / int(reg["hold"])) * int(reg["hold"])) % per
			var tri := 1.0 - absf(2.0 * q / per - 1.0)
			return _c12(a.lerp(b, tri))
	return pal_base[int(reg["index"])]
