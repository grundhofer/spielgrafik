extends Node2D
## Dachs-Kurier: läuft von links herein und bleibt stehen.
## Laufbilder und Vorschub kommen aus art/walk.json (prep.py walk): Der Vorschub je Bildwechsel ist aus dem
## gemessenen Standfuß abgeleitet, deshalb bewegt sich die Figur nur beim Bildwechsel (wie in klassischen
## Adventures) und der Standfuß bleibt stehen. Bildrate 10 Bilder/s (auf Dreien bei 30 fps).
## Die Figur hält auf dem Bild walk.json "stop_frame" genau bei stop_x an; die Zahl der Schritte ergibt sich aus
## walk_time (nächste Zahl, die auf diesem Bild endet), der Startpunkt aus dem Vorschub. Gibt es "stand_frame"
## (eigenes Stehbild hinter dem Zyklus im Blatt), wird beim Anhalten dieses statt des Zyklusbilds gezeigt.

const SHADOW := preload("res://art/fx/shadow.png")
const WALK := preload("res://art/walk.png")

var c: Dictionary
var w: Dictionary
var spr: Sprite2D
var shadow: Sprite2D
var steps := 0            # Bildwechsel bis zum Stehen
var start_x := 0.0


func setup(cfg: Dictionary) -> void:
	c = cfg
	w = JSON.parse_string(FileAccess.get_file_as_string("res://art/walk.json"))
	shadow = Sprite2D.new()
	shadow.texture = SHADOW
	shadow.modulate = Color(1, 1, 1, c.get("shadow_alpha", 0.45))
	var sw: float = c.get("shadow_w", 90.0) / 128.0
	shadow.scale = Vector2(sw, sw * 0.22)
	shadow.position = Vector2(c.get("shadow_dx", 0.0), 2.0)
	add_child(shadow)
	spr = Sprite2D.new()
	spr.texture = WALK
	spr.hframes = int(w["count"])
	spr.centered = false
	spr.offset = -Vector2(w["anchor"][0], w["anchor"][1])
	spr.modulate = c.get("tint", Color(1, 1, 1))
	add_child(spr)
	_plan()
	update(0.0)


func _plan() -> void:
	## Schrittzahl und Startpunkt so wählen, dass die Figur auf dem Stehbild bei stop_x ankommt.
	var fps: float = c.get("fps", 10.0)
	var cyc: Array = w["cycle"]
	var adv: Array = w["advance"]
	var stop: int = int(w.get("stop_frame", 0))
	# Schrittzahl, die auf dem Stehbild endet und walk_time am nächsten liegt (bei Gleichstand die kürzere)
	var base := int(round(c.get("walk_time", 1.4) * fps))
	steps = base
	for d in range(0, cyc.size() + 1):
		if base - d >= 0 and int(cyc[(base - d) % cyc.size()]) == stop:
			steps = base - d
			break
		if int(cyc[(base + d) % cyc.size()]) == stop:
			steps = base + d
			break
	var total := 0.0
	for i in steps:
		total += float(adv[i % adv.size()])
	start_x = c["stop_x"] - total


func update(t: float) -> void:
	var fps: float = c.get("fps", 10.0)
	var k := int(floor(t * fps + 0.0001))
	var n := mini(k, steps)
	var cyc: Array = w["cycle"]
	var adv: Array = w["advance"]
	var x: float = start_x
	for i in n:
		x += float(adv[i % adv.size()])
	spr.frame = int(cyc[n % cyc.size()])
	position = Vector2(round(x), c["feet_y"])
	if k >= steps and w.has("stand_frame"):
		# Stehbild aus Teilen (prep.py WALK_STAND): ersetzt den Durchgang, Standfuß an derselben Stelle
		spr.frame = int(w["stand_frame"])
	if k >= steps:
		# Stehen: leichtes Atmen um den Fußpunkt (Skalierung nur in y, Füße bleiben auf der Linie)
		var idle_t: float = t - float(steps) / fps
		spr.scale = Vector2(1.0, 1.0 + 0.012 * sin(TAU * idle_t / 1.7))
	else:
		spr.scale = Vector2.ONE
