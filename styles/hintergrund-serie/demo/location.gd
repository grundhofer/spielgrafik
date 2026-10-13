extends Node2D
## Ein Ort der Serie: Hintergrundbild plus Umgebungsanimationen, beschrieben durch einen Eintrag in
## locations.gd. Jeder Ort lebt in einer eigenen SubViewport; main.gd mischt zwei davon im Übergangs-Shader.
## Alles ist eine reine Funktion der Zeit t (von main.gd übergeben); Zufall nur mit festem Seed.

const GLOW := preload("res://art/fx/glow.png")
const BEAM := preload("res://art/fx/beam.png")
const GLINT := preload("res://art/fx/glint.png")
const GULL := preload("res://art/fx/gull.png")
const FLAME := preload("res://art/fx/flame.png")
const SMOKE := [preload("res://art/fx/smoke1.png"), preload("res://art/fx/smoke2.png"),
	preload("res://art/fx/smoke3.png")]

var cfg: Dictionary
var glows: Array = []          # [Sprite2D, Dictionary]
var flames: Array = []
var smoke: Array = []
var glints: Array = []
var gulls: Array = []
var motes: Array = []
var beams: Array = []
var sweeps: Array = []
var badger: Node2D = null


func setup(key: String, data: Dictionary, seed_value: int, badger_only := false) -> void:
	cfg = data
	name = key
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	if badger_only:
		# Prüfmodus für tools/measure_walk.py: nur der Dachs vor reinem Magenta, ohne Effekte und Schatten
		var key_bg := ColorRect.new()
		key_bg.color = Color(1, 0, 1)
		key_bg.size = Vector2(1280, 720)
		add_child(key_bg)
		if cfg.has("badger"):
			var bcfg: Dictionary = cfg["badger"].duplicate()
			bcfg["shadow_alpha"] = 0.0
			badger = preload("res://badger.gd").new()
			add_child(badger)
			badger.setup(bcfg)
		return
	var bg := Sprite2D.new()
	bg.texture = load("res://art/bg_%s.png" % key)
	bg.centered = false
	add_child(bg)
	for g in cfg.get("glints", []):
		_build_glints(g, rng)
	for b in cfg.get("beams", []):
		_build_beam(b)
	for s in cfg.get("smoke", []):
		_build_smoke(s, rng)
	for g in cfg.get("glows", []):
		_build_glow(g, rng)
	for f in cfg.get("flames", []):
		_build_flame(f, rng)
	for s in cfg.get("sweeps", []):
		_build_sweep(s)
	for m in cfg.get("motes", []):
		_build_motes(m, rng)
	for g in cfg.get("gulls", []):
		_build_gull(g)
	if cfg.has("badger"):
		badger = preload("res://badger.gd").new()
		add_child(badger)
		badger.setup(cfg["badger"])


func update(t: float) -> void:
	for e in glows:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		var f := _flicker(t, d["phase"], d.get("flicker", 0.0))
		s.modulate.a = d.get("alpha", 0.5) * f
		var sc: float = d.get("size", 100.0) / 256.0 * (1.0 + 0.04 * (f - 1.0))
		s.scale = Vector2(sc, sc * d.get("squash", 1.0))
	for e in flames:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		# Bildwechsel auf Zweien (15 Bilder/s), Folge mit fester Zufallsreihe
		var k := int(floor(t * 15.0 + d["phase"]))
		s.frame = d["order"][k % d["order"].size()]
		var h: float = d.get("height", 40.0) / 80.0
		s.scale = Vector2(h * (0.92 + 0.08 * sin(t * 9.0 + d["phase"])), h * (0.9 + 0.12 * sin(t * 13.0 + d["phase"] * 2.0)))
	for e in smoke:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		var age := fposmod(t - d["birth"], d["life"])
		var u: float = age / d["life"]
		s.position = d["pos"] + Vector2(d["drift"].x * age + 6.0 * sin(age * 1.3 + d["phase"]), d["drift"].y * age)
		var sc: float = d["size"] / 128.0 * (0.45 + 1.1 * u)
		s.scale = Vector2(sc, sc)
		s.rotation = d["phase"] + age * 0.15
		s.modulate.a = d["alpha"] * smoothstep(0.0, 0.15, u) * (1.0 - smoothstep(0.55, 1.0, u))
	for e in glints:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		var v := sin(TAU * t / d["period"] + d["phase"])
		s.modulate.a = d["alpha"] * pow(maxf(v, 0.0), 3.0)
		s.position = d["pos"] + Vector2(round(4.0 * sin(t * 0.7 + d["phase"])), 0.0)
	for e in beams:
		var root: Node2D = e[0]
		var d: Dictionary = e[1]
		var ang: float = TAU * t / d["period"] + d["phase"]
		var c := cos(ang)
		var spr: Sprite2D = root.get_child(0)
		root.scale = Vector2(c * d["length"] / 640.0, d["width"] / 160.0)
		# nach hinten gedreht (sin < 0) schwächer; zur Kamera hin kurz und hell
		var toward := sin(ang)
		spr.modulate.a = d["alpha"] * (0.55 + 0.45 * clampf(toward * 0.5 + 0.5, 0.0, 1.0)) * smoothstep(0.02, 0.25, absf(c))
		if d.has("flare"):
			var fl: Sprite2D = d["flare"]
			fl.modulate.a = d["flare_alpha"] * (0.35 + 0.65 * pow(maxf(toward, 0.0), 6.0))
	for e in sweeps:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		var ang: float = TAU * t / d["period"] + d["phase"]
		var x := sin(ang)
		s.position = d["pos"] + Vector2(x * d["half_width"], 0.0)
		s.modulate.a = d["alpha"] * clampf(cos(ang) * 0.5 + 0.6, 0.0, 1.0)
	for e in motes:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		var u := fposmod(t * d["speed"] + d["phase"], 1.0)
		s.position = d["rect"].position + Vector2(d["x"] * d["rect"].size.x + 8.0 * sin(t * 0.9 + d["phase"] * 7.0),
			d["rect"].size.y * (1.0 - u))
		s.modulate.a = d["alpha"] * sin(u * PI)
	for e in gulls:
		var s: Sprite2D = e[0]
		var d: Dictionary = e[1]
		var u := fposmod(t / d["duration"] + d["phase"], 1.0)
		s.position = d["from"].lerp(d["to"], u) + Vector2(0.0, 6.0 * sin(u * TAU * 2.0))
		var k := int(floor(t * 6.0 + d["phase"] * 10.0)) % 4
		s.frame = [0, 1, 2, 1][k]
	if badger:
		badger.update(t)


func _flicker(t: float, ph: float, amount: float) -> float:
	if amount <= 0.0:
		return 1.0
	var n := 0.5 * sin(t * 11.3 + ph) + 0.3 * sin(t * 23.9 + ph * 2.3) + 0.2 * sin(t * 41.7 + ph * 3.1)
	return 1.0 + amount * n


func _sprite(tex: Texture2D, pos: Vector2, color: Color, additive: bool) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.position = pos
	s.modulate = color
	if additive:
		var m := CanvasItemMaterial.new()
		m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
		s.material = m
	add_child(s)
	return s


func _build_glow(d: Dictionary, rng: RandomNumberGenerator) -> void:
	var s := _sprite(GLOW, d["pos"], d.get("color", Color(1.0, 0.75, 0.4)), d.get("add", true))
	var dd := d.duplicate()
	dd["phase"] = rng.randf() * TAU
	glows.append([s, dd])


func _build_flame(d: Dictionary, rng: RandomNumberGenerator) -> void:
	var s := _sprite(FLAME, d["pos"], Color(1, 1, 1, d.get("alpha", 0.9)), d.get("add", false))
	s.hframes = 4
	s.offset = Vector2(0, -40)            # Fußpunkt der Flamme unten
	var dd := d.duplicate()
	dd["phase"] = rng.randf() * 10.0
	var order: Array = []
	for i in 16:
		order.append(rng.randi_range(0, 3))
	dd["order"] = order
	flames.append([s, dd])


func _build_smoke(d: Dictionary, rng: RandomNumberGenerator) -> void:
	var n: int = d.get("count", 8)
	var life: float = d.get("life", 4.0)
	for i in n:
		var s := _sprite(SMOKE[i % 3], d["pos"], d.get("color", Color(0.78, 0.78, 0.86)), false)
		smoke.append([s, {"pos": d["pos"], "birth": -life + life * float(i) / n, "life": life,
			"drift": d.get("drift", Vector2(14, -22)), "size": d.get("size", 40.0),
			"alpha": d.get("alpha", 0.35), "phase": rng.randf() * TAU}])


func _build_glints(d: Dictionary, rng: RandomNumberGenerator) -> void:
	var rect: Rect2 = d["rect"]
	for i in d.get("count", 12):
		var p := rect.position + Vector2(rng.randf() * rect.size.x, rng.randf() * rect.size.y)
		var s := _sprite(GLINT, p.round(), d.get("color", Color(1.0, 0.85, 0.6)), true)
		var sc: float = d.get("size", 1.0) * rng.randf_range(0.5, 1.0)
		s.scale = Vector2(sc, sc * 0.8)
		glints.append([s, {"pos": p.round(), "period": rng.randf_range(1.1, 2.2), "phase": rng.randf() * TAU,
			"alpha": d.get("alpha", 0.6)}])


func _build_beam(d: Dictionary) -> void:
	var root := Node2D.new()
	root.position = d["pos"]
	add_child(root)
	var s := Sprite2D.new()
	s.texture = BEAM
	s.centered = false
	s.offset = Vector2(0, -80)
	s.modulate = d.get("color", Color(1.0, 0.92, 0.7))
	var m := CanvasItemMaterial.new()
	m.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	s.material = m
	root.add_child(s)
	var dd := d.duplicate()
	if d.has("flare_size"):
		var fl := _sprite(GLOW, d["pos"], Color(1.0, 0.88, 0.6), true)
		fl.scale = Vector2.ONE * d["flare_size"] / 256.0
		dd["flare"] = fl
	beams.append([root, dd])


func _build_sweep(d: Dictionary) -> void:
	var s := _sprite(GLOW, d["pos"], d.get("color", Color(1.0, 0.9, 0.65)), true)
	s.scale = Vector2(d.get("w", 40.0), d.get("h", 120.0)) / 256.0
	sweeps.append([s, d.duplicate()])


func _build_motes(d: Dictionary, rng: RandomNumberGenerator) -> void:
	for i in d.get("count", 10):
		var s := _sprite(GLOW, Vector2.ZERO, d.get("color", Color(1.0, 0.9, 0.7)), true)
		var sz: float = rng.randf_range(4.0, 8.0) / 256.0
		s.scale = Vector2(sz, sz)
		motes.append([s, {"rect": d["rect"], "x": rng.randf(), "speed": rng.randf_range(0.04, 0.09),
			"phase": rng.randf(), "alpha": d.get("alpha", 0.5)}])


func _build_gull(d: Dictionary) -> void:
	var s := _sprite(GULL, d["from"], Color(1, 1, 1, d.get("alpha", 0.85)), false)
	s.hframes = 3
	s.scale = Vector2.ONE * d.get("scale", 0.5)
	if d["to"].x < d["from"].x:
		s.flip_h = true
	gulls.append([s, d.duplicate()])
