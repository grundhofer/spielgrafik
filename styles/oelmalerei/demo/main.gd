extends Node2D
## Hafen von Lornholm als expressive Ölmalerei.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit festen Seeds.
## So ist die Aufnahme mit --fixed-fps Bild für Bild reproduzierbar.

const SMOKE_TEX := [
	preload("res://art/fx/smoke1.png"), preload("res://art/fx/smoke2.png"),
	preload("res://art/fx/smoke3.png"), preload("res://art/fx/smoke4.png"),
]
const GLINT_TEX := [
	preload("res://art/fx/glint1.png"), preload("res://art/fx/glint2.png"),
	preload("res://art/fx/glint3.png"), preload("res://art/fx/glint4.png"),
]
const GULL_TEX := preload("res://art/fx/gull.png")

# Lage der Lichtquellen im Gemälde (Bildschirmpixel, Gemälde 1080x720 links oben)
const LAMP := Vector2(801, 183)
const LANTERN := Vector2(228, 352)
const CHIMNEY := Vector2(86, 186)

# Dachs: läuft von links herein und bleibt im linken Drittel auf Bild 2 (Füße beieinander) stehen.
# Bildfolge und Vorschub je Bildwechsel kommen aus walk.json (prep.py misst den Standfuß): Der Körper rückt
# nur beim Bildwechsel vor, um genau so viel, dass der Standfuß ortsfest bleibt. Die Haltezeit eines Bilds
# ist proportional zum nächsten Vorschub (in ganzen Bildern bei 30 fps), so bleibt das Tempo gleichmäßig,
# obwohl die KI-Posen ungleich weit auseinanderliegen (8..24 px).
const STOP_X := 385.0
const FEET_Y := 676.0
const PX_PER_FRAME := 4.2                  # mittleres Tempo: 4,2 px je 1/30 s = 126 px/s
const MIN_HOLD := 2                        # kürzeste Haltezeit (auf Zweien)
const ENTER_X := -70.0                     # Startpunkt: Figur ganz außerhalb des Bilds

# Leuchtturm: ein Strahl dreht sich in 9 s einmal herum. Die Phase legt die 6 s der Aufnahme so, dass er
# zur Kamera hin beginnt, bei t = 3 s ganz nach links zeigt (Poster bei 3,6 s) und nur kurz nach rechts.
const BEAM_PERIOD := 9.0
const BEAM_PHASE := PI / 3.0

# Text im Panel
const TYPE_START := 0.35
const TYPE_CPS := 30.0
const CHOICE_T := [2.55, 2.75, 2.95]
const HOVER_T := 4.4
const CHOICE_COLOR := Color(0.85, 0.42, 0.24)
const HOVER_COLOR := Color(0.96, 0.90, 0.78)

const PARSER := "> nimm paket"
const PARSER_T := 4.75
const PARSER_CPS := 14.0

const SMOKE_LIFE := 4.6
const SMOKE_EVERY := 0.55

var t := 0.0
var walk_steps: Array = []                 # [Startzeit s, Bild, x]
var smoke: Array = []
var glints: Array = []
var gulls: Array = []

@onready var badger: Sprite2D = $World/Badger
@onready var shadow: Sprite2D = $World/BadgerShadow
@onready var beam: Node2D = $World/Beam
@onready var beam_sprite: Sprite2D = $World/Beam/BeamSprite
@onready var lamp_halo: Sprite2D = $World/LampHalo
@onready var lamp_light: PointLight2D = $World/LampLight
@onready var lantern_halo: Sprite2D = $World/LanternHalo
@onready var lantern_light: PointLight2D = $World/LanternLight
@onready var window_halo: Sprite2D = $World/WindowHalo
@onready var window_light: PointLight2D = $World/WindowLight
@onready var post: ColorRect = $World/Post
@onready var portrait: TextureRect = $UI/Portrait
@onready var line: Label = $UI/Line
@onready var choices: Array = [$UI/Choice1, $UI/Choice2, $UI/Choice3]
@onready var parser: Label = $UI/Parser
@onready var add_mat: Material = beam_sprite.material


func _ready() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261010
	_build_walk()
	_build_smoke(rng)
	_build_glints(rng)
	_build_gulls()
	_apply(0.0)


func _process(delta: float) -> void:
	t += delta
	_apply(t)


# --- Aufbau -----------------------------------------------------------------------------------

func _build_walk() -> void:
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/walk.json"))
	badger.offset = Vector2(-float(meta["anchor_x"]), -float(meta["feet_y"]))
	# Füße (unterste 14 px über der Fußlinie) vom Boil ausnehmen
	badger.material.set_shader_parameter("boil_stop_v", (float(meta["feet_y"]) - 14.0) / float(meta["frame_h"]))
	# JSON liefert Zahlen als float; für find() und frame in int umwandeln
	var seq: Array = []
	for v in meta["seq"]:
		seq.append(int(v))
	var adv: Array = meta["advance"]           # adv[i]: Vorschub beim Wechsel seq[i-1] -> seq[i]
	# Vom Halt aus rückwärts bis außerhalb des Bilds: Schrittfolge und Positionen
	var i := seq.find(2)
	var x := STOP_X
	var idx := [i]
	var xs := [x]
	while x > ENTER_X:
		x -= float(adv[i])
		i = posmod(i - 1, seq.size())
		idx.push_front(i)
		xs.push_front(x)
	# Haltezeiten: Bild k bleibt stehen, bis der Körper um adv des nächsten Wechsels vorrücken darf;
	# die letzten beiden Schritte etwas langsamer (Abbremsen)
	var time := 0.0
	for k in idx.size():
		walk_steps.append([time, int(seq[idx[k]]), float(xs[k])])
		if k + 1 < idx.size():
			var frames := maxi(MIN_HOLD, roundi(float(adv[idx[k + 1]]) / PX_PER_FRAME))
			if k + 3 >= idx.size():
				frames = roundi(frames * 1.35)
			time += frames / 30.0


func _build_smoke(rng: RandomNumberGenerator) -> void:
	var n := int(ceil((6.0 + SMOKE_LIFE) / SMOKE_EVERY)) + 1
	for i in n:
		var s := Sprite2D.new()
		s.texture = SMOKE_TEX[(i * 3) % SMOKE_TEX.size()]
		s.flip_h = rng.randf() < 0.5
		$World/Smoke.add_child(s)
		smoke.append({
			"node": s, "spawn": -SMOKE_LIFE + i * SMOKE_EVERY, "period": n * SMOKE_EVERY,
			"wob": rng.randf_range(0.0, TAU), "rot": rng.randf_range(-0.4, 0.4),
			"end": rng.randf_range(0.4, 0.55), "drift": rng.randf_range(-7.0, -3.0),
		})


func _build_glints(rng: RandomNumberGenerator) -> void:
	# Zonen: Spiegelungen der Lichter auf dem Wasser [x0, x1, y0, y1, Anzahl, Maßstab, Farbe]
	var zones := [
		[788, 818, 405, 515, 7, 0.42, Color(1, 1, 1)],          # Spiegelung des Leuchtturms
		[600, 650, 460, 520, 4, 0.4, Color(1, 1, 1)],           # Boote / Abendlicht im Becken
		[420, 600, 300, 325, 5, 0.28, Color(1, 0.9, 0.8)],      # Horizontband draußen
		[150, 330, 535, 560, 5, 0.5, Color(1, 1, 1)],           # Laterne auf nassem Kaistein
		[660, 780, 430, 540, 6, 0.4, Color(0.7, 0.8, 0.95)],    # Becken, kühl
	]
	for z in zones:
		for k in int(z[4]):
			var s := Sprite2D.new()
			s.texture = GLINT_TEX[rng.randi() % GLINT_TEX.size()]
			s.material = add_mat
			s.position = Vector2(rng.randf_range(z[0], z[1]), rng.randf_range(z[2], z[3]))
			var sc: float = z[5] * rng.randf_range(0.7, 1.2) * lerpf(0.7, 1.15, (s.position.y - 250.0) / 280.0)
			s.scale = Vector2(sc, sc * 0.8)
			s.flip_h = rng.randf() < 0.5
			$World/Glints.add_child(s)
			glints.append({
				"node": s, "period": rng.randf_range(1.4, 2.8), "phase": rng.randf(),
				"peak": rng.randf_range(0.55, 0.95), "tint": z[6], "dx": rng.randf_range(-3.0, 3.0),
			})


func _build_gulls() -> void:
	# [Start-x, y, Geschwindigkeit, Maßstab, Flügelphase]
	# Möwe 1 fliegt rechts der Rauchsäule über das Becken, Möwe 2 höher und kleiner. gull.png ist in der
	# Anzeigegröße der vorderen Möwe gebacken (Maßstab 1), die hintere ist 0,74-mal so groß.
	for g in [[330.0, 140.0, 62.0, 1.0, 0.0], [210.0, 84.0, 48.0, 0.74, 0.5]]:
		var s := Sprite2D.new()
		s.texture = GULL_TEX
		s.hframes = 3
		s.scale = Vector2(g[3], g[3])
		s.modulate = Color(1, 1, 1, 0.92)
		$World/Gulls.add_child(s)
		gulls.append({"node": s, "x0": g[0], "y": g[1], "v": g[2], "ph": g[4]})


# --- Animation --------------------------------------------------------------------------------

func _flicker(time: float) -> float:
	# Laternenflackern: Summe unharmonischer Sinusschwingungen plus kurze Einbrüche, Bereich etwa -1..1
	var f := 0.5 * sin(time * 11.0) + 0.3 * sin(time * 23.7 + 1.1) + 0.2 * sin(time * 41.3 + 2.3)
	var dip := pow(maxf(0.0, sin(time * 2.9 + 0.7)), 24.0)
	return clampf(f - 1.2 * dip, -1.0, 1.0)


func _apply(time: float) -> void:
	var fl := _flicker(time)

	# Dachs
	var step: Array = walk_steps[0]
	for st in walk_steps:
		if st[0] <= time + 0.0001:
			step = st
	badger.frame = step[1]
	var x: float = step[2]
	var t_stop: float = walk_steps[-1][0]
	var breathe := 0.0
	if time > t_stop:
		breathe = sin((time - t_stop) * TAU / 1.9) * 0.5 + 0.5
	badger.position = Vector2(roundf(x), FEET_Y)   # ganze Pixel: Textur 1:1, nicht weichgezeichnet
	badger.scale = Vector2(1.0, 1.0 + 0.014 * breathe)
	# Kontaktschatten: gemalter Tupfer, leicht zur laternenabgewandten Seite versetzt
	shadow.position = Vector2(roundf(x + 8.0 * clampf((x - LANTERN.x) / 60.0, -1.0, 1.0)), FEET_Y + 1.0)
	# Licht der Umgebung: nahe der Laterne wärmer und heller, sonst kühles Abendlicht
	var warm := clampf(1.0 - absf(x - LANTERN.x) / 420.0, 0.0, 1.0)
	var tint := Vector3(0.98, 0.97, 1.02).lerp(Vector3(1.08, 1.0, 0.9), warm) * (1.0 + 0.05 * fl * warm)
	badger.material.set_shader_parameter("tint", tint)
	badger.material.set_shader_parameter("time_s", time)
	# Kantenlicht: Richtung zur Laterne (von der Brust des Dachses aus), mit etwas Himmelslicht von oben
	var to_lantern := (LANTERN - Vector2(x, FEET_Y - 90.0)).normalized()
	var ld := (to_lantern * (0.4 + 0.6 * warm) + Vector2(0.0, -1.0) * 0.5).normalized()
	badger.material.set_shader_parameter("light_dir", ld)
	badger.material.set_shader_parameter("rim", (0.35 + 0.4 * warm) * (1.0 + 0.2 * fl * warm))

	# Leuchtturm: Strahl dreht sich um die senkrechte Achse; seitlich lang, zur Kamera hin Aufleuchten
	var th := TAU * time / BEAM_PERIOD + BEAM_PHASE
	var side := cos(th)
	var front := maxf(0.0, sin(th))
	# Lasur statt additiver Helligkeit: der Strahl liegt wie ein halbdeckender heller Pinselstrich auf dem Himmel
	# Kegel aus beam_cone.png: am Lampenhaus schmal, zur Spitze breiter; seitlich lang, zur Kamera kurz
	beam_sprite.scale = Vector2(side, lerpf(0.55, 0.8, absf(side)))
	beam.rotation = 0.06 * signf(side)
	# Farbe ist in beam_cone.png gemalt (am Lampenhaus warm, außen Creme); hier nur die Deckung
	beam_sprite.modulate = Color(1.0, 1.0, 1.0, clampf(0.2 + 0.6 * absf(side) + 0.1 * front, 0.0, 1.0)
			* (0.7 if front < 0.0 else 1.0))
	var flare := pow(front, 6.0)
	# Lichthof aus gemalten Tupfern (normale Mischung); springt mit 6 Bildern/s leicht wie gemaltes Licht
	var boil := floorf(time * 6.0)
	lamp_halo.rotation = 0.12 * sin(boil * 2.3)
	lamp_halo.scale = Vector2.ONE * (0.26 + 0.3 * flare)
	lamp_halo.modulate.a = 0.5 + 0.4 * flare
	lamp_light.energy = 0.35 + 0.9 * flare

	# Laterne und Fenster
	lantern_light.energy = 0.85 + 0.28 * fl
	lantern_halo.modulate.a = 0.42 + 0.14 * fl
	lantern_halo.scale = Vector2.ONE * (0.42 + 0.03 * fl)
	lantern_halo.rotation = 0.1 * sin(boil * 1.7 + 0.5)
	var wf := 0.5 * sin(time * 5.3) + 0.5 * sin(time * 8.9 + 0.4)
	window_light.energy = 0.45 + 0.08 * wf
	window_halo.modulate.a = 0.32 + 0.05 * wf

	# Rauch aus dem Schornstein
	for p in smoke:
		var s: Sprite2D = p["node"]
		var age: float = fposmod(time - p["spawn"], p["period"])
		if age > SMOKE_LIFE:
			s.visible = false
			continue
		s.visible = true
		var k := age / SMOKE_LIFE
		s.position = CHIMNEY + Vector2(p["drift"] * age + 4.0 * sin(age * 1.2 + p["wob"]),
				-(19.0 * age - 0.9 * age * age))
		s.scale = Vector2.ONE * lerpf(0.10, p["end"], sqrt(k))
		s.rotation = p["rot"] + 0.08 * age
		s.modulate = Color(0.80, 0.79, 0.80, smoothstep(0.0, 0.2, age) * (1.0 - smoothstep(0.3, 1.0, k)) * 0.55)

	# Glitzern auf dem Wasser: jedes Glanzlicht blüht kurz auf und vergeht
	for g in glints:
		var s: Sprite2D = g["node"]
		var ph: float = fposmod(time / g["period"] + g["phase"], 1.0)
		var a: float = pow(maxf(0.0, sin(ph * PI)), 3.0) * g["peak"]
		var c: Color = g["tint"]
		s.modulate = Color(c.r, c.g, c.b, a)
		s.offset = Vector2(g["dx"] * ph * 4.0, 0)

	# Möwen
	for g in gulls:
		var s: Sprite2D = g["node"]
		s.position = Vector2(fposmod(g["x0"] + g["v"] * time + 80.0, 1200.0) - 80.0,
				g["y"] + 5.0 * sin(time * 1.6 + g["ph"] * 4.0)).round()   # ganze Pixel, sonst verwischt
		s.frame = [0, 1, 2, 1][int(floor(time * 7.0 + g["ph"] * 4.0)) % 4]

	post.material.set_shader_parameter("time_s", time)

	# Dialogpanel
	portrait.material.set_shader_parameter("flicker", fl)
	portrait.material.set_shader_parameter("time_s", time)
	line.visible_characters = clampi(int((time - TYPE_START) * TYPE_CPS), 0, line.text.length())
	for i in choices.size():
		var c: Label = choices[i]
		c.modulate.a = smoothstep(CHOICE_T[i], CHOICE_T[i] + 0.3, time)
		var hover := i == 1 and time >= HOVER_T
		c.add_theme_color_override("font_color", HOVER_COLOR if hover else CHOICE_COLOR)
		(c.get_node("Num") as Label).add_theme_color_override("font_color", HOVER_COLOR if hover else CHOICE_COLOR)
	# Parser-Zeile: tippt nach der Auswahl, Schreibmarke blinkt
	var n := clampi(int((time - PARSER_T) * PARSER_CPS) + 1, 1, PARSER.length())
	var caret := "_" if fposmod(time, 0.8) < 0.45 else " "
	parser.text = PARSER.substr(0, n) + " " + caret if time >= PARSER_T - 0.6 else ""
