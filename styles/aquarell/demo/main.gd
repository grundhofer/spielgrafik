extends Node2D
## Hafen von Lornholm als Aquarell.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit festem Seed.
## Lage der Lichtquellen, Wasserband, Wolken und der ganze Ablauf der Figur (ein Eintrag je Figurenbild:
## Bogen, Bild, x, Flags) stehen in res://art/scene.json (von tools/stage.py, für KI- und 3D-Figur gleich).

const CLOUD_TEX := [
	preload("res://art/fx/cloud_0.png"), preload("res://art/fx/cloud_1.png"), preload("res://art/fx/cloud_2.png"),
	preload("res://art/fx/cloud_3.png"), preload("res://art/fx/cloud_4.png"),
]
const SMOKE_TEX := [
	preload("res://art/fx/smoke_0.png"), preload("res://art/fx/smoke_1.png"),
	preload("res://art/fx/smoke_2.png"), preload("res://art/fx/smoke_3.png"),
]
const GULL_TEX := preload("res://art/fx/gull.png")
const SMOKE_LIFE := 4.2
const SMOKE_EVERY := 0.5

# Text
const TYPE_START := 0.3
const TYPE_CPS := 32.0
const CHOICE_T := [2.4, 2.6, 2.8]
const HOVER_T := 3.9
const PARSER := "> nimm paket"
const PARSER_T := 4.2
const PARSER_CPS := 14.0
const INK := Color(0.29, 0.25, 0.28)
const INK_HOVER := Color(0.17, 0.13, 0.16)

var t := 0.0
var cfg: Dictionary
var clouds: Array = []
var smoke: Array = []
var gulls: Array = []
var feet_y := 560.0
var sheets := {}          # Name -> [Texture2D, hframes]
var timeline: Array = []  # [Bogen, Bild, x, Flags] je Figurenbild
var anim_fps := 15.0
var badger_scale := 1.0

@onready var painting: Sprite2D = $World/Painting
@onready var water_glaze: Sprite2D = $World/WaterGlaze
@onready var beam: Node2D = $World/Beam
@onready var beam_sprite: Sprite2D = $World/Beam/BeamSprite
@onready var lamp_glow: Sprite2D = $World/LampGlow
@onready var lantern_glow: Sprite2D = $World/LanternGlow
@onready var window_glow: Sprite2D = $World/WindowGlow
@onready var badger: Sprite2D = $World/Badger
@onready var shadow: Sprite2D = $World/BadgerShadow
@onready var line: Label = $UI/Line
@onready var parser: Label = $UI/Parser
@onready var swatch: TextureRect = $UI/Swatch
@onready var choices: Array = [$UI/Choice1, $UI/Choice2, $UI/Choice3]


func _ready() -> void:
	cfg = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	if cfg == null:
		push_error("scene.json fehlt oder ist ungültig")
		return
	feet_y = float(cfg["feet_y"])
	var b: Dictionary = cfg["badger"]
	for name in b["sheets"]:
		var sh: Dictionary = b["sheets"][name]
		sheets[name] = [load("res://art/" + str(sh["file"])), int(sh["hframes"])]
	timeline = b["timeline"]
	anim_fps = float(b["fps"])
	badger_scale = float(b["scale"])
	badger.scale = Vector2(badger_scale, badger_scale)
	badger.offset = -_v(b["anchor"])
	shadow.scale = Vector2.ONE * float(cfg.get("badger_height", 170.0)) / 170.0
	lamp_glow.position = _v(cfg["lamp"])
	beam.position = _v(cfg["lamp"])
	lantern_glow.position = _v(cfg["lantern"])
	window_glow.position = _v(cfg["window"])
	var wg := float(cfg.get("window_glow_scale", 0.75))
	window_glow.scale = Vector2(wg * 0.93, wg * 1.07)
	var band: Array = cfg.get("water_band", [370.0, 480.0])
	water_glaze.position = Vector2(0, band[0])
	water_glaze.scale = Vector2(1.0, (float(band[1]) - float(band[0])) / 200.0)
	if "--measure" in OS.get_cmdline_user_args():
		_measure_mode()
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261010
	_build_clouds(rng)
	_build_smoke(rng)
	_build_gulls()
	_apply(0.0)


func _measure_mode() -> void:
	## Prüfmodus für tools/measure_badger.py: nur die Figur auf reinem Magenta, ohne Maske, Schatten und Papier.
	for c in $World.get_children():
		if c != badger:
			c.visible = false
	$UI.visible = false
	$Post.visible = false
	RenderingServer.set_default_clear_color(Color(1, 0, 1))
	badger.material = null


func _v(a: Array) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _process(delta: float) -> void:
	t += delta
	_apply(t)


# --- Aufbau ---------------------------------------------------------------------------------------

func _build_clouds(rng: RandomNumberGenerator) -> void:
	# [Textur, x, y, Geschwindigkeit px/s, Deckkraft] – höhere Wolken ziehen schneller (Parallaxe)
	var rows: Array = cfg.get("clouds", [[0, 220.0, 70.0, 9.0, 0.9], [2, 760.0, 120.0, 7.0, 0.8],
			[1, 1100.0, 60.0, 10.0, 0.7], [3, 480.0, 210.0, 4.5, 0.55], [4, 1000.0, 250.0, 4.0, 0.5]])
	for r in rows:
		var s := Sprite2D.new()
		s.texture = CLOUD_TEX[int(r[0])]
		s.material = $World/BadgerShadow.material.duplicate()
		s.material.set_shader_parameter("region_mask", load("res://art/sky_mask.png"))
		s.material.set_shader_parameter("use_region", 1.0)
		s.flip_h = rng.randf() < 0.5
		$World/Clouds.add_child(s)
		clouds.append({"node": s, "x": float(r[1]), "y": float(r[2]), "v": float(r[3]), "a": float(r[4])})


func _build_smoke(rng: RandomNumberGenerator) -> void:
	var n := int(ceil((6.0 + SMOKE_LIFE) / SMOKE_EVERY)) + 1
	for i in n:
		var s := Sprite2D.new()
		s.texture = SMOKE_TEX[i % SMOKE_TEX.size()]
		# Rauch ausgewaschen (zum Papier aufgehellt): auf dem dunklen Abendhimmel bliebe eine Lasur unsichtbar
		s.material = $World/LampGlow.material
		s.modulate = Color(1.0, 0.98, 0.96)
		s.flip_h = rng.randf() < 0.5
		$World/Smoke.add_child(s)
		smoke.append({
			"node": s, "spawn": -SMOKE_LIFE + i * SMOKE_EVERY, "period": n * SMOKE_EVERY,
			"wob": rng.randf_range(0.0, TAU), "rot": rng.randf_range(-0.5, 0.5),
			"end": rng.randf_range(1.6, 2.2), "drift": rng.randf_range(4.0, 8.0),
		})


func _build_gulls() -> void:
	# [Start-x, y, Geschwindigkeit, Maßstab, Flügelphase]
	for g in cfg.get("gulls", [[-40.0, 150.0, 58.0, 0.8, 0.0], [300.0, 96.0, 44.0, 0.6, 0.45]]):
		var s := Sprite2D.new()
		s.texture = GULL_TEX
		s.hframes = 3
		s.scale = Vector2(g[3], g[3])
		s.material = $World/BadgerShadow.material
		$World/Gulls.add_child(s)
		gulls.append({"node": s, "x0": g[0], "y": g[1], "v": g[2], "ph": g[4]})


# --- Animation ------------------------------------------------------------------------------------

func _flicker(time: float) -> float:
	var f := 0.5 * sin(time * 11.0) + 0.3 * sin(time * 23.7 + 1.1) + 0.2 * sin(time * 41.3 + 2.3)
	var dip := pow(maxf(0.0, sin(time * 2.9 + 0.7)), 24.0)
	return clampf(f - 1.2 * dip, -1.0, 1.0)


func _badger(time: float) -> void:
	var f := clampi(int(floor(time * anim_fps + 0.0001)), 0, timeline.size() - 1)
	var e: Array = timeline[f]
	var sh: Array = sheets[e[0]]
	if badger.texture != sh[0]:
		badger.texture = sh[0]
		badger.hframes = sh[1]
	badger.frame = int(e[1])
	var x := float(e[2])
	badger.position = Vector2(roundf(x), roundf(feet_y))
	shadow.position = Vector2(roundf(x) + 4.0, roundf(feet_y) + 1.0)
	# Atmen (nur im Stehen ohne eigene Idle-Bilder): Höhe um die Fußlinie leicht gestaucht
	var breath := 1.0 + (0.009 * sin(time * 2.6) if (int(e[3]) & 1) == 1 else 0.0)
	# Abendlicht: kühl, in Laternennähe wärmer
	var lan := _v(cfg["lantern"])
	var warm := clampf(1.0 - absf(x - lan.x) / 500.0, 0.0, 1.0)
	var tint := Vector3(0.93, 0.89, 0.95).lerp(Vector3(1.0, 0.92, 0.84), warm)
	if badger.material:
		badger.material.set_shader_parameter("tint", tint)
		badger.material.set_shader_parameter("breath", breath)


func _apply(time: float) -> void:
	var fl := _flicker(time)
	_badger(time)
	painting.material.set_shader_parameter("time_s", time)

	# Wasser: die Lasurebene gleitet langsam seitwärts und wiegt sich ein wenig auf und ab
	water_glaze.region_rect = Rect2(fposmod(time * 9.0, 1280.0), 0.0, 1280.0, 200.0)
	water_glaze.offset = Vector2(0.0, 2.0 * sin(time * 0.9))

	# Wolken ziehen nach links
	for c in clouds:
		var s: Sprite2D = c["node"]
		var w := float(s.texture.get_width())
		s.position = Vector2(fposmod(c["x"] - c["v"] * time + w, 1280.0 + 2.0 * w) - w, c["y"])
		s.modulate.a = c["a"]

	# Leuchtturm: Lichtbahn dreht sich (ausgewaschen = zum Papier hin aufgehellt)
	var period := 8.0
	var th := TAU * time / period - 0.39   # Phase: bei 4,5 s (Poster) zeigt die Bahn ganz nach links
	var side := cos(th)
	var front := maxf(0.0, sin(th))
	beam_sprite.scale = Vector2(side, lerpf(0.5, 0.8, absf(side)))
	beam_sprite.modulate.a = clampf(0.1 + 0.6 * absf(side), 0.0, 1.0) * (0.6 if sin(th) < 0.0 else 1.0)
	var flare := pow(front, 5.0)
	lamp_glow.scale = Vector2.ONE * float(cfg.get("lamp_glow_scale", 1.0)) * (0.32 + 0.35 * flare)
	lamp_glow.modulate.a = 0.55 + 0.4 * flare

	# Laterne und Fenster
	lantern_glow.modulate.a = 0.5 + 0.18 * fl
	lantern_glow.scale = Vector2.ONE * (float(cfg.get("lantern_glow_scale", 0.6)) + 0.05 * fl)
	window_glow.modulate.a = 0.3 + 0.04 * sin(time * 5.3)

	# Rauch
	var ch := _v(cfg["chimney"])
	for p in smoke:
		var s: Sprite2D = p["node"]
		var age: float = fposmod(time - p["spawn"], p["period"])
		if age > SMOKE_LIFE:
			s.visible = false
			continue
		s.visible = true
		var kk := age / SMOKE_LIFE
		s.position = ch + Vector2(p["drift"] * age + 3.0 * sin(age * 1.3 + p["wob"]), -(16.0 * age - 0.6 * age * age))
		s.scale = Vector2.ONE * lerpf(0.5, p["end"], sqrt(kk))
		s.rotation = p["rot"] + 0.1 * age
		s.modulate.a = smoothstep(0.0, 0.3, age) * (1.0 - smoothstep(0.35, 1.0, kk)) * float(cfg.get("smoke_alpha", 0.5))

	# Möwen
	for g in gulls:
		var s: Sprite2D = g["node"]
		s.position = Vector2(fposmod(g["x0"] + g["v"] * time + 60.0, 1400.0) - 60.0, g["y"] + 4.0 * sin(time * 1.5 + g["ph"] * 5.0))
		s.frame = [0, 1, 2, 1][int(floor(time * 6.0 + g["ph"] * 4.0)) % 4]

	# Text
	line.visible_characters = clampi(int((time - TYPE_START) * TYPE_CPS), 0, line.text.length())
	for i in choices.size():
		var c: Label = choices[i]
		c.modulate.a = smoothstep(CHOICE_T[i], CHOICE_T[i] + 0.35, time)
		var hover: bool = i == 1 and time >= HOVER_T
		c.add_theme_color_override("font_color", INK_HOVER if hover else INK)
	swatch.modulate.a = smoothstep(HOVER_T, HOVER_T + 0.25, time) * 0.9
	var n := clampi(int((time - PARSER_T) * PARSER_CPS) + 1, 1, PARSER.length())
	var caret := "_" if fposmod(time, 0.8) < 0.45 else " "
	parser.text = PARSER.substr(0, n) + caret if time >= PARSER_T - 0.6 else ""
