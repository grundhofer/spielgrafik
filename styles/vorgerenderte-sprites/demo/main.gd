extends Node2D
## Vorgerenderte 3D-Sprites: Alles, was man sieht, ist in Blender gerendert und auf 15-Bit-Farben
## gebracht (Hintergrund aus zwei Ebenen, Wasserband als Bildfolge, Sprites mit je 15 Farben +
## Durchsichtig). Godot setzt nur Bilder zusammen: Bildwechsel, ganze Pixel, Farbrechnung für
## Lichtkegel und Schatten. Zeit über delta aufsummiert; Zufall mit festem Seed.
## Benutzerargument --t0=SEKUNDEN startet später (Dauerlauf prüfen); --mask zeigt nur den Dachs
## (weiß auf Schwarz) für die Fußmessung.

const SPRITE_FPS := 15.0
const WALK_CYCLES := 6           # volle Zyklen; danach noch Bild 0–6 des nächsten, Bild 6 = Durchgang
const START_X := 99              # linke Zellkante des Dachses beim Start (Bildpixel); Halt bei Wurzel ≈ 235
const FEET_ROW := 168            # Zeile des Laufwegs im Hintergrund (aus bg.json, Szenenkamera)

var t := 0.0
var meta := {}
var water_tex: Array[Texture2D] = []
var rng := RandomNumberGenerator.new()
var flicker := []                # vorab gezogene Helligkeitsstufen der Laterne (10/s)
var mask_mode := false

@onready var back: Sprite2D = $Back
@onready var water: Sprite2D = $Water
@onready var beam: Sprite2D = $Beam
@onready var boat: Sprite2D = $Boat
@onready var front: Sprite2D = $Front
@onready var barrels: Sprite2D = $Barrels
@onready var lantern: Sprite2D = $Lantern
@onready var halo: Sprite2D = $LanternHalo
@onready var shadow: Sprite2D = $BadgerShadow
@onready var badger: Sprite2D = $Badger
@onready var ui: Node2D = $UI


func _json(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("fehlt: " + path)
		return {}
	return JSON.parse_string(f.get_as_text())


func _sheet(spr: Sprite2D, name: String) -> Dictionary:
	var m := _json("res://sprites/%s.json" % name)
	spr.texture = load("res://sprites/%s.png" % name)
	var cell: Array = m["cell"]
	spr.hframes = int(m["columns"])
	spr.vframes = int(spr.texture.get_height() / int(cell[1]))
	if m.has("box"):
		var box: Array = m["box"]
		spr.position = Vector2(box[0], box[1])
	return m


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t = float(a.substr(5))
		if a == "--mask":
			mask_mode = true
	rng.seed = 1994
	var lv := 2
	for i in 400:      # Zufallsweg über die vier Stufen, Ruhelage 2
		var r := rng.randf()
		if r < 0.3:
			lv = maxi(0, lv - 1)
		elif r < 0.6:
			lv = mini(3, lv + 1)
		elif r < 0.75:
			lv = 2
		flicker.append(lv)
	meta["bg"] = _json("res://bg/bg.json")
	back.texture = load("res://bg/back.png")
	front.texture = load("res://bg/front.png")
	var wr: Array = meta["bg"]["water_rows"]
	water.position = Vector2(0, wr[0])
	for k in int(meta["bg"]["water_frames"]):
		water_tex.append(load("res://bg/water_%02d.png" % k))
	meta["boat"] = _sheet(boat, "boat")
	meta["lantern"] = _sheet(lantern, "lantern")
	meta["halo"] = _sheet(halo, "lantern_halo")
	meta["barrels"] = _sheet(barrels, "barrels")
	meta["beam"] = _sheet(beam, "beam")
	meta["badger"] = _sheet(badger, "badger")
	shadow.texture = load("res://sprites/badger_shadow.png")
	shadow.hframes = int(meta["badger"]["columns"])
	shadow.vframes = int(shadow.texture.get_height() / 48)
	if mask_mode:
		for n in [back, water, beam, boat, front, barrels, lantern, halo, shadow, ui]:
			n.visible = false
		badger.modulate = Color(100, 100, 100)    # deckende Pixel werden weiß (Snap klemmt auf 1)
		RenderingServer.set_default_clear_color(Color.BLACK)
	_apply(t)


func _process(delta: float) -> void:
	t += delta
	_apply(t)


func _anim(name: String) -> Dictionary:
	return meta["badger"]["anims"][name]


## Ablauf des Dachses in Sprite-Bildern (15/s): Laufen, Stehen, Drehen (O → SO → S), Winken, Stehen vorn.
func _badger(tt: float) -> void:
	var i := int(floor(tt * SPRITE_FPS + 1e-4))
	var walk_n := WALK_CYCLES * 8 + 7
	var adv := 17
	var x := START_X
	var fr := 0
	if i < walk_n:
		x += adv * (i / 8)
		fr = int(_anim("walk")["first"]) + i % 8
	else:
		x += adv * WALK_CYCLES
		var j := i - walk_n
		if j < 3:
			fr = int(_anim("stand")["first"])
		elif j < 5:
			fr = int(_anim("turn")["first"])
		elif j < 7:
			fr = int(_anim("turn")["first"]) + 1
		elif j < 7 + int(_anim("wave")["frames"]):
			fr = int(_anim("wave")["first"]) + j - 7
		else:
			var k := (j - 7 - int(_anim("wave")["frames"])) % int(_anim("idle")["frames"])
			fr = int(_anim("idle")["first"]) + k
	var origin: Array = meta["badger"]["origin"]
	badger.position = Vector2(x, FEET_ROW - int(origin[1]))
	badger.frame = fr
	shadow.position = Vector2(x, FEET_ROW - 8)
	shadow.frame = fr


func _apply(tt: float) -> void:
	_badger(tt)
	# Wasserband: 12 vorgerenderte Bilder, 6/s
	water.texture = water_tex[int(floor(tt * 6.0)) % water_tex.size()]
	# Boot schaukelt: 30 Bilder, 10/s
	boat.frame = int(floor(tt * 10.0)) % int(meta["boat"]["frames"])
	# Laterne: vier vorgerenderte Helligkeiten, Wechsel 10/s nach fester Zufallsfolge
	lantern.frame = flicker[int(floor(tt * 10.0)) % flicker.size()]
	halo.frame = lantern.frame
	# Leuchtfeuer: 24 Bilder je Umdrehung, 6/s (4 s je Umdrehung); das Aufblitzen ist mitgerendert
	beam.frame = int(floor(tt * 6.0)) % int(meta["beam"]["frames"])
	ui.set_time(tt)
