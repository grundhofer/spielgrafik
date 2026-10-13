extends Node2D
## Prozedurale Animation: alle Bewegung entsteht zur Laufzeit aus Code, nicht aus Einzelbildern.
## Fester Simulationsschritt 1/120 s, Zeit aus aufsummierten delta-Werten (im Movie-Maker-Lauf aus dem
## Bildzähler x 1/fps, weil Godot dort die ersten delta-Werte ungleich liefert: 0,025 / 0,033 / 0,042 / 0,029 …),
## Zufall nur mit festen Seeds.
## Prüfargumente nach "--": --t0=<s>, --badger-only, --only=<teile>, --keycol=r,g,b, --log=<datei>,
## --no-ui, --no-inset, --overlay-main

const Waves := preload("res://scripts/waves.gd")
const DT := 1.0 / 120.0
const PRE := 3.0                 # Vorlauf: Gang, Ketten, Boote und Schwarm sind bei t = 0 eingeschwungen
const GROUND_Y := 585.0
const START_X := 250.0           # rechts der Hausecke: y 585 liegt hier auf dem Pflaster, nicht auf der Tür

var t0 := 0.0
var t_render := 0.0
var n_done := 0
var movie_dt := 0.0              # > 0 im Movie-Maker-Lauf: Zeit = Bildzähler x movie_dt
var movie_frame := 0
var opts := {}
var bg_mat: ShaderMaterial
var fx_back: Node2D
var fx_front: Node2D
var gulls: Node2D
var smoke: Node2D
var boats: Array = []
var badger: Node2D
var overlay: Node2D
var ui: CanvasLayer
var dim: Node2D
var log_file: FileAccess


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		opts[kv[0]] = kv[1] if kv.size() > 1 else "1"
	t0 = float(opts.get("t0", "0"))
	if Engine.get_write_movie_path() != "":
		var fps := 30.0
		var args := OS.get_cmdline_args()
		for i in args.size():
			if args[i] == "--fixed-fps" and i + 1 < args.size():
				fps = float(args[i + 1])
			elif args[i].begins_with("--fixed-fps="):
				fps = float(args[i].split("=")[1])
		movie_dt = 1.0 / fps
	var scene: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	var rig: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/rig.json"))
	var motif_ui: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://art/ui_text.json"))
	Waves.horizon = float(scene["horizon_y"])
	var badger_only := opts.has("badger-only") or opts.has("only")
	get_viewport().canvas_cull_mask = 1 | (2 if opts.has("overlay-main") else 0)

	if badger_only:
		var key := ColorRect.new()
		key.color = Color(1, 0, 1)
		if opts.has("keycol"):   # z. B. --keycol=0.46,0.52,0.59 für Prüfbilder ohne Magentasaum
			var c := String(opts["keycol"]).split(",")
			key.color = Color(float(c[0]), float(c[1]), float(c[2]))
		key.size = Vector2(1280, 720)
		add_child(key)
	else:
		var bg := Sprite2D.new()
		bg.texture = load("res://art/bg.png")
		bg.centered = false
		bg_mat = ShaderMaterial.new()
		bg_mat.shader = load("res://shaders/water.gdshader")
		bg_mat.set_shader_parameter("mask_tex", load("res://art/bg_mask.png"))
		bg.material = bg_mat
		add_child(bg)
		smoke = Node2D.new()
		smoke.set_script(load("res://scripts/smoke.gd"))
		add_child(smoke)
		smoke.setup(_v2(scene["chimney_pot"]), -PRE)
		fx_back = Node2D.new()
		fx_back.set_script(load("res://scripts/fx.gd"))
		add_child(fx_back)
		fx_back.setup(scene, "back")
		gulls = Node2D.new()
		gulls.set_script(load("res://scripts/gulls.gd"))
		add_child(gulls)
		gulls.setup()
		var posts: Dictionary = scene["jetty_posts"]
		var bi: Dictionary = scene["boats"]
		# Fischerboot links vom Steg, weiter draußen; Ruderboot rechts, näher am Kai
		boats.append(_boat("res://art/boat_a.png", bi["boat_a"], 606.0, 462.0, 232.0,
			_v2(posts["left_far"]) + Vector2(0, -2), 2.7, 2.4))
		boats.append(_boat("res://art/boat_b.png", bi["boat_b"], 992.0, 506.0, 150.0,
			_v2(posts["right_mid"]) + Vector2(0, -2), 4.2, 3.8))
		fx_front = Node2D.new()
		fx_front.set_script(load("res://scripts/fx.gd"))
		add_child(fx_front)
		fx_front.setup(scene, "front")
		dim = Node2D.new()
		dim.set_script(load("res://scripts/dim.gd"))
		dim.visibility_layer = 2
		add_child(dim)

	badger = Node2D.new()
	badger.set_script(load("res://scripts/badger.gd"))
	add_child(badger)
	badger.setup(rig, GROUND_Y, START_X, String(opts.get("only", "")) if opts.has("only") else "")
	overlay = Node2D.new()
	overlay.set_script(load("res://scripts/overlay.gd"))
	overlay.b = badger
	overlay.visibility_layer = 2
	badger.add_child(overlay)
	badger.overlay = overlay
	if badger_only:
		overlay.visible = false
	badger.init_state(-PRE)
	if not (badger_only or opts.has("no-ui")):
		ui = CanvasLayer.new()
		ui.set_script(load("res://scripts/ui.gd"))
		add_child(ui)
		ui.setup(motif_ui, badger, get_viewport().world_2d, not opts.has("no-inset"))
	_advance(t0)
	if opts.has("log"):   # erst nach dem Vorlauf öffnen: eine Zeile je aufgenommenem Bild
		log_file = FileAccess.open(String(opts["log"]), FileAccess.WRITE)


func _v2(a) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


func _boat(tex: String, info: Dictionary, x: float, y: float, w: float, post: Vector2, oh: float, op: float) -> Node2D:
	var b := Node2D.new()
	b.set_script(load("res://scripts/boat.gd"))
	add_child(b)
	b.setup(tex, info, x, y, w, post, oh, op)
	return b


func _process(delta: float) -> void:
	if movie_dt > 0.0:
		t_render = movie_frame * movie_dt     # Bild k zeigt genau t = k / fps (k = 0, 1, 2 …)
		movie_frame += 1
	else:
		t_render += delta
	_advance(t0 + t_render)


func _advance(tt: float) -> void:
	var n_target := int(round((tt + PRE) / DT))
	while n_done < n_target:
		n_done += 1
		var st := -PRE + n_done * DT
		badger.step(st, DT)
		for b in boats:
			b.step(st, DT)
		if gulls:
			gulls.step(st, DT)
		if smoke:
			smoke.step(st, DT)
	var tn := -PRE + n_done * DT
	badger.render()
	for b in boats:
		b.render()
	if gulls:
		gulls.queue_redraw()
	if smoke:
		smoke.queue_redraw()
	if bg_mat:
		Waves.apply_uniforms(bg_mat, tn)
	if fx_back:
		fx_back.update(tn)
	if fx_front:
		fx_front.update(tn)
		badger.mat.set_shader_parameter("lantern_glow", fx_front.lantern_k)
	else:
		badger.mat.set_shader_parameter("lantern_glow", 0.0)
	if ui:
		ui.update(tn)
	if log_file:
		var fl := []
		for f in badger.feet:
			fl.append({"name": f.name, "swing": f.swing, "s": f.s, "A": [f.A.x, f.A.y], "pos": f.pos.x, "phi": f.phi})
		var sc: PackedVector2Array = badger.scarf.p
		var sp: PackedVector2Array = badger.strap.p
		log_file.store_line(JSON.stringify({"t": tn, "hip": [badger.hip.x, badger.hip.y], "q": badger.q, "sy": badger.sy,
			"tilt": badger.tilt, "feet": fl, "scarf_tip": [sc[sc.size() - 1].x, sc[sc.size() - 1].y],
			"scarf_root": [sc[0].x, sc[0].y], "bag": [sp[sp.size() - 1].x, sp[sp.size() - 1].y], "steps": badger.n_steps,
			"blink": badger.blink, "air": [badger.air.x, badger.air.y],
			"scarf_stretch": badger.scarf.length_total() / (badger.scarf.seg * (sc.size() - 1)) - 1.0,
			"strap_stretch": badger.strap.length_total() / (badger.strap.seg * (sp.size() - 1)) - 1.0}))
		log_file.flush()
