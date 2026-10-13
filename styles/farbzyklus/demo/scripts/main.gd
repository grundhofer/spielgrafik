extends Node2D
## Farbzyklus-Demo: Hafen von Lornholm als EIN Indexbild (426x240), alle Bewegung im Hintergrund über die Palette.
## Ablauf (6 s): Abend, 1,4–3,4 s Überblendung zur Nacht, 4,0–5,0 s setzt Regen ein. Der Dachs kommt von rechts,
## bleibt bei 3,3 s stehen, blinzelt; sein Schalende flattert. Im Regen fallen Tropfen auch vor dem Dachs (sein
## Shader legt die Regen-Einträge der Bahnkarte art/rain_front.png auf ihn). Zeit über delta aufsummiert, Zufall
## mit festem Seed.
## Befehlszeilen (nach --): --t0=<s> startet später (Langzeitprüfung), --probe malt den Dachs magenta (Fußmessung),
## --probe-log schreibt je Bild Zeit, Sprite-Bild und Lage nach user://probe.txt.

const ANIM_FPS := 15.0
const START_X := 404          # Ankerspalte (Kopfmitte) in Weltkoordinaten bei t = 0
const FEET_Y := 224           # Sohlenzeile auf dem Pflaster
const WALK_FRAMES := 49       # 8 Schritte (48 Bilder) + Aufsetzbild
const BLINK_AT := [16, 32]    # Blinzeln ab diesen Standbildern (je 2 Animationsbilder, im Block mit stand0),
const BLINK_PERIOD := 64      # danach alle 64 Animationsbilder (4,3 s) wieder

var t := 0.0
var t0 := 0.0
var cyc: Cycler
var bmeta: Dictionary
var probe_log := false
var log_lines := PackedStringArray()

@onready var bg: Sprite2D = $Bg
@onready var badger: Sprite2D = $Badger
@onready var ui: Node2D = $UI/Box


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
		elif a == "--probe":
			badger.material.set_shader_parameter("probe", true)
			badger.material.set_shader_parameter("rain_over", false)   # Fußmessung: reines Magenta
		elif a == "--probe-log":
			probe_log = true
	cyc = Cycler.new("res://art/palette.json")
	bmeta = JSON.parse_string(FileAccess.get_file_as_string("res://art/badger.json"))
	bg.material.set_shader_parameter("palette_tex", cyc.texture)
	badger.material.set_shader_parameter("palette_tex", cyc.texture)
	ui.setup(cyc)
	_tick(0.0)


func _process(delta: float) -> void:
	t += delta
	_tick(t)


func _tick(tt: float) -> void:
	var at := tt + t0
	cyc.update(at)
	_badger(at)
	ui.tick(at)
	if probe_log:
		log_lines.append("%d %.3f %s %d %d" % [int(round(tt * 30.0)), at, _cur_name, int(badger.position.x), int(badger.position.y)])
		if log_lines.size() % 30 == 0:
			var f := FileAccess.open("user://probe.txt", FileAccess.WRITE)
			f.store_string("\n".join(log_lines) + "\n")


var _cur_name := ""


func _badger(at: float) -> void:
	var names: Array = bmeta["frames"]
	var cw := int(bmeta["cell"][0])
	var ch := int(bmeta["cell"][1])
	var ax := int(bmeta["anchor_col"])
	var ground := int(bmeta["ground_row"])
	var step_d: Array = bmeta["step_d"]
	var stop_d: Array = bmeta["stop_d"]
	var n := int(floor(at * ANIM_FPS + 1e-4))
	var fname := ""
	var adv := 0
	if n < WALK_FRAMES:
		fname = "walk%d" % (n % 12)
		for j in n:
			adv += int(step_d[j % 6])
	else:
		for j in WALK_FRAMES - 1:         # Anker des letzten Laufbilds (Aufsetzen), dann Anhalten
			adv += int(step_d[j % 6])
		var k := n - WALK_FRAMES
		if k == 0:
			fname = "settle0"
			adv += int(stop_d[0])
		else:
			adv += int(stop_d[0]) + int(stop_d[1])
			fname = _idle_name(k)
	_cur_name = fname
	var fi := names.find(fname)
	badger.region_rect = Rect2(fi * cw, 0, cw, ch)
	# Blick nach links (gespiegelt): Spalte c des Bildes liegt bei x + (cw - 1 - c); Anker auf Weltspalte anchor
	var anchor := START_X - adv
	badger.position = Vector2(anchor - (cw - 1 - ax), FEET_Y - ground)


func _idle_name(k: int) -> String:
	# Blinzeln (je 2 Animationsbilder, am Animationsbild k gezählt, nicht an Sekunden), sonst Schalende im
	# Wind (Wechsel alle 4 Animationsbilder). Das Blinzelbild trägt das Schalende von stand0, deshalb liegt es am
	# Anfang eines stand0-Blocks (k/4 = 4 und 8, mod 8 wiederholt).
	var kb := k % BLINK_PERIOD
	for b in BLINK_AT:
		if kb >= b and kb < b + 2:
			return "blink"
	var seq := [0, 1, 2, 1, 0, 3, 2, 3]
	return "stand%d" % seq[(k / 4) % seq.size()]


func _exit_tree() -> void:
	if probe_log:
		var f := FileAccess.open("user://probe.txt", FileAccess.WRITE)
		f.store_string("\n".join(log_lines) + "\n")
