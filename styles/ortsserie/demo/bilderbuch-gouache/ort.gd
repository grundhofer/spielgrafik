extends Node2D
## Ein Ort der Ortsserie als Bilderbuch-Seite in Gouache (Stil bilderbuch-gouache), ohne Figur.
## Hintergrund, Lage der Effekte und Text stehen in res://bilderbuch-gouache/art/<ort>.json
## (styles/ortsserie/bilderbuch-gouache/scripts/build_orte.py). Alle Effekte sind im Duktus der Bilder in Code
## gemalt (Lichthöfe aus Farbringen, Pinselstrahlen, Glitzerstriche, Rauch- und Dampftupfer, Flammen-Tupfer).
##
## Zeit: t = t0 + n / 30 mit eigenem Bildzähler n (deterministisch, unabhängig von delta); Zufall nur mit
## RandomNumberGenerator und festem Seed. Bild n einer Aufnahme zeigt t = n / 30.
## Für eine Hauptdemo: autoplay = false setzen und set_time(t) aufrufen.
## Benutzerargumente nach „--“: --t0=<s> (Startzeit), --only=bg (nur Hintergrund ohne Effekte und Text),
## --no-text (ohne Text), --no-fx (ohne Effekte).

const FPS := 30.0
const DIR := "res://bilderbuch-gouache/"

@export var ort := "leuchtturm"
@export var autoplay := true

var t := 0.0
var t0 := 0.0
var n := 0
var cfg: Dictionary
var flicker := PackedFloat32Array()
var halos: Array = []     # [Sprite2D, Dictionary]
var rays: Array = []      # [Sprite2D, Dictionary]
var stars: Array = []     # [Sprite2D, phase, speed, base_scale]
var glints: Array = []    # [Sprite2D, Vector2 base, phase, period, drift]
var puffs: Array = []     # [Dictionary cfg, Array pool, Array seeds]
var flames: Array = []    # [Sprite2D, Dictionary, Array textures]
var sweeps: Array = []    # [Control clip, Sprite2D, Dictionary]
var sway_mat: ShaderMaterial
var title_lbl: Label
var line_lbl: Label


func _ready() -> void:
	cfg = JSON.parse_string(FileAccess.get_file_as_string(DIR + "art/%s.json" % ort))
	var args := OS.get_cmdline_user_args()
	for a in args:
		if a.begins_with("--t0="):
			t0 = float(a.substr(5))
	var rng := RandomNumberGenerator.new()
	rng.seed = int(cfg.get("seed", 20261013))
	for i in range(256):
		flicker.append(rng.randf())
	$Bg.texture = load(DIR + "art/" + str(cfg["bg"]))
	if cfg.has("sway"):
		_build_sway()
	_build_fx(rng)
	_build_text()
	if "--only=bg" in args:
		$Fx.visible = false
		$Text.visible = false
		if sway_mat:
			$Bg.material = null
	if "--no-text" in args:
		$Text.visible = false
	if "--no-fx" in args:
		$Fx.visible = false
	set_time(t0)


func _process(_delta: float) -> void:
	if not autoplay:
		return
	set_time(t0 + n / FPS)
	n += 1


func set_time(sec: float) -> void:
	t = sec
	_update()


# --- Hilfen -------------------------------------------------------------------------------------------------------

func _noise(x: float) -> float:
	var i := int(floorf(x))
	var f := x - floorf(x)
	var s := f * f * (3.0 - 2.0 * f)
	return lerpf(flicker[posmod(i, 256)], flicker[posmod(i + 1, 256)], s)


func _tex(name: String) -> Texture2D:
	return load(DIR + "art/fx/" + name + ".png")


func _sprite(tex: Texture2D, parent: Node, pos: Vector2) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.position = pos
	parent.add_child(s)
	return s


func _v(a: Array) -> Vector2:
	return Vector2(float(a[0]), float(a[1]))


# --- Aufbau -------------------------------------------------------------------------------------------------------

func _build_sway() -> void:
	var sw: Dictionary = cfg["sway"]
	sway_mat = ShaderMaterial.new()
	sway_mat.shader = load(DIR + "shaders/sway.gdshader")
	sway_mat.set_shader_parameter("mask", load(DIR + "art/" + str(sw["mask"])))
	sway_mat.set_shader_parameter("amp_px", float(sw["amp_px"]))
	sway_mat.set_shader_parameter("screen_px", Vector2(1280, 720))
	$Bg.material = sway_mat


func _build_fx(rng: RandomNumberGenerator) -> void:
	var fx: Node2D = $Fx
	# Sterne (gefunden in den Himmelsflächen, nicht hinter der Schrift)
	var star_tex := _tex("star")
	var text_rect := Rect2(_v(cfg["text_rect"]), _v(cfg["text_rect"].slice(2)) - _v(cfg["text_rect"])).grow(24.0)
	for p in cfg.get("stars", []):
		var pos := _v(p)
		if text_rect.has_point(pos):
			continue
		var s := _sprite(star_tex, fx, pos.round())
		stars.append([s, rng.randf() * TAU, rng.randf_range(1.6, 2.8), rng.randf_range(0.45, 0.65)])
	# Glitzerstriche auf dem Wasser (in Rechtecken, ganze Pixel)
	for g in cfg.get("glints", []):
		var r: Array = g["rect"]
		for k in range(int(g["n"])):
			var pos := Vector2(rng.randf_range(float(r[0]), float(r[2])), rng.randf_range(float(r[1]), float(r[3])))
			var ti := rng.randi_range(0, 3)
			var s := _sprite(_tex("glint_%d" % ti), fx, pos.round())
			s.scale = Vector2.ONE * float(g.get("scale", 1.0))
			glints.append([s, pos, rng.randf() * TAU, rng.randf_range(2.2, 3.6),
					rng.randf_range(2.0, 6.0) * float(g.get("scale", 1.0))])
	# Lichtwanderung (z. B. in der Linse): heller Pinselstrich, der in einem Ausschnitt durchläuft
	for w in cfg.get("sweeps", []):
		var r: Array = w["rect"]
		var clip := Control.new()
		clip.clip_contents = true
		clip.position = Vector2(float(r[0]), float(r[1]))
		clip.size = Vector2(float(r[2]) - float(r[0]), float(r[3]) - float(r[1]))
		clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
		fx.add_child(clip)
		var s := Sprite2D.new()
		s.texture = _tex(str(w["tex"]))
		clip.add_child(s)
		sweeps.append([clip, s, w])
	# Lichthöfe aus gemalten Farbringen
	for h in cfg.get("halos", []):
		var s := _sprite(_tex(str(h["tex"])), fx, _v(h["pos"]))
		s.scale = Vector2.ONE * float(h.get("scale", 1.0))
		halos.append([s, h])
	# Flammen-Tupfer (wenige gemalte Bilder, 10 Bilder/s)
	for f in cfg.get("flames", []):
		var texs: Array = []
		for k in range(int(f["frames"])):
			texs.append(_tex("%s_%d" % [str(f["tex"]), k]))
		var s := Sprite2D.new()
		s.texture = texs[0]
		s.centered = false
		s.offset = Vector2(-texs[0].get_width() / 2.0, -texs[0].get_height())   # Fußpunkt unten Mitte
		s.position = _v(f["pos"])
		s.scale = Vector2.ONE * float(f.get("scale", 1.0))
		fx.add_child(s)
		flames.append([s, f, texs])
	# Pinselstrahlen (Blinken)
	for r in cfg.get("rays", []):
		var s := _sprite(_tex(str(r.get("tex", "rays"))), fx, _v(r["pos"]))
		rays.append([s, r])
	# Rauch- und Dampftupfer: Pool von Sprites
	for p in cfg.get("puffs", []):
		var pool: Array = []
		var seeds: Array = []
		var count := int(ceilf(float(p["life"]) / float(p["every"]))) + 1
		for i in range(count):
			var s := Sprite2D.new()
			fx.add_child(s)
			pool.append(s)
		for i in range(64):
			seeds.append([rng.randi_range(0, 2), rng.randf() * TAU, rng.randf_range(0.85, 1.1),
					rng.randf_range(0.6, 1.4)])
		puffs.append([p, pool, seeds])


func _font(path: String, wght: float, opsz: float, spacing := 0) -> FontVariation:
	var ts := TextServerManager.get_primary_interface()
	var fv := FontVariation.new()
	fv.base_font = load(path)
	fv.variation_opentype = {ts.name_to_tag("wght"): wght, ts.name_to_tag("opsz"): opsz,
			ts.name_to_tag("SOFT"): 100.0, ts.name_to_tag("WONK"): 0.0}
	fv.spacing_glyph = spacing
	return fv


func _label(text: String, font: Font, size: int, col: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_override("font", font)
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", col)
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.visible_characters_behavior = TextServer.VC_CHARS_AFTER_SHAPING
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	$Text.add_child(l)
	return l


func _build_text() -> void:
	var tx: Dictionary = cfg["text"]
	var f_title := _font(DIR + "fonts/Fraunces-var.ttf", 620.0, 24.0, 3)
	var f_text := _font(DIR + "fonts/Fraunces-var.ttf", 480.0, 48.0)
	if tx.has("band"):
		var b: Array = tx["band"]
		var band := TextureRect.new()
		band.texture = _tex("band_text")
		band.position = Vector2(float(b[0]), float(b[1]))
		band.modulate = Color(1, 1, 1, float(b[2]))
		band.mouse_filter = Control.MOUSE_FILTER_IGNORE
		$Text.add_child(band)
	var cx := float(tx.get("cx", 640.0))
	title_lbl = _label(str(tx["title"]), f_title, 17, Color(str(tx["title_col"])))
	title_lbl.position = Vector2(cx - 320.0, float(tx["y"]))
	title_lbl.size = Vector2(640, 24)
	line_lbl = _label(str(tx["line"]), f_text, 31, Color(str(tx["line_col"])))
	line_lbl.add_theme_constant_override("line_spacing", -2)
	line_lbl.position = Vector2(cx - 340.0, float(tx["y"]) + 28.0)
	line_lbl.size = Vector2(680, 90)


# --- Ablauf -------------------------------------------------------------------------------------------------------

func _level(h: Dictionary) -> float:
	## 0..1 je nach Art: flicker (Flamme), breathe (langsames Atmen), blink (Leuchtfeuer)
	var mode := str(h.get("mode", "breathe"))
	var ph := float(h.get("phase", 0.0))
	if mode == "flicker":
		return _noise(t * 8.0 + ph) * 0.55 + _noise(t * 19.0 + 40.0 + ph) * 0.45
	if mode == "blink":
		var period := float(h.get("period", 2.5))
		var cyc := fposmod(t + ph, period) / period
		return exp(-pow((cyc - 0.25) / 0.09, 2.0))
	return 0.5 + 0.5 * sin(t * TAU / float(h.get("period", 3.0)) + ph)


func _update() -> void:
	for s in stars:
		var sp: Sprite2D = s[0]
		var v: float = 0.5 + 0.5 * sin(t * float(s[2]) + float(s[1]))
		sp.scale = Vector2.ONE * (float(s[3]) * (0.75 + 0.35 * v))
		sp.modulate = Color(1, 1, 1, 0.5 + 0.5 * v)
	for g in glints:
		var sp: Sprite2D = g[0]
		var ph := t / float(g[3]) * TAU + float(g[2])
		var v := 0.5 + 0.5 * sin(ph)
		sp.position = ((g[1] as Vector2) + Vector2(sin(ph * 0.5) * float(g[4]), 0)).round()
		sp.modulate = Color(1, 1, 1, smoothstep(0.25, 0.9, v) * 0.95)
	for h in halos:
		var sp: Sprite2D = h[0]
		var d: Dictionary = h[1]
		var lv := _level(d)
		var a: Array = d.get("alpha", [0.4, 0.8])
		var sc: Array = d.get("grow", [0.95, 1.05])
		sp.modulate = Color(1, 1, 1, lerpf(float(a[0]), float(a[1]), lv))
		sp.scale = Vector2.ONE * float(d.get("scale", 1.0)) * lerpf(float(sc[0]), float(sc[1]), lv)
	for r in rays:
		var sp: Sprite2D = r[0]
		var d: Dictionary = r[1]
		var lv := _level(d)
		sp.modulate = Color(1, 1, 1, smoothstep(0.15, 0.7, lv))
		sp.scale = Vector2.ONE * float(d.get("scale", 1.0)) * (0.75 + 0.3 * lv)
		sp.rotation = t * 0.25
	for w in sweeps:
		var clip: Control = w[0]
		var sp: Sprite2D = w[1]
		var d: Dictionary = w[2]
		var period := float(d.get("period", 4.0))
		var u := fposmod(t + float(d.get("phase", 0.0)), period) / period
		var span := clip.size.x + sp.texture.get_width() * 1.0
		sp.position = Vector2(roundf(-sp.texture.get_width() * 0.5 + u * span), roundf(clip.size.y * 0.5))
		var edge := minf(u, 1.0 - u) * 2.0
		sp.modulate = Color(1, 1, 1, float(d.get("alpha", 0.8)) * smoothstep(0.0, 0.5, edge))
	for f in flames:
		var sp: Sprite2D = f[0]
		var d: Dictionary = f[1]
		var texs: Array = f[2]
		var k := int(floorf(t * float(d.get("fps", 10.0)) + 0.001 + float(d.get("phase", 0.0))))
		sp.texture = texs[posmod(k, texs.size())]
		var lv := _noise(t * 6.0 + float(d.get("phase", 0.0)) * 7.0)
		sp.scale = Vector2(1.0, 0.9 + 0.2 * lv) * float(d.get("scale", 1.0))
	for p in puffs:
		_update_puffs(p)
	if sway_mat:
		sway_mat.set_shader_parameter("t", t)
	_update_text()


func _update_puffs(p: Array) -> void:
	var d: Dictionary = p[0]
	var pool: Array = p[1]
	var seeds: Array = p[2]
	var life := float(d["life"])
	var every := float(d["every"])
	var origin := _v(d["pos"])
	var sc0 := float(d.get("scale", 1.0))
	for s in pool:
		(s as Sprite2D).visible = false
	var first := int(floorf((t - life) / every)) + 1
	var last := int(floorf(t / every))
	for i in range(first, last + 1):
		var age := t - i * every
		if age < 0.0 or age >= life:
			continue
		var sd: Array = seeds[posmod(i, seeds.size())]
		var sp: Sprite2D = pool[posmod(i, pool.size())]
		var u := age / life
		sp.visible = true
		sp.texture = _tex("%s_%d" % [str(d.get("tex", "smoke")), int(sd[0])])
		var sway := sin(age * 1.6 + float(sd[1])) * float(d.get("sway", 5.0)) * u
		var drift := float(d.get("drift", 10.0)) * float(sd[3])
		sp.position = (origin + Vector2(drift * age + sway, -float(d.get("rise", 24.0)) * age)).round()
		var sc := (0.22 + 0.62 * sqrt(u)) * float(sd[2]) * sc0
		sp.scale = Vector2(sc, sc * (0.92 + 0.08 * sin(age * 2.0 + float(sd[1]))))
		var a := clampf(age / 0.25, 0.0, 1.0) * (1.0 - smoothstep(0.55, 1.0, u)) * float(d.get("alpha", 1.0))
		sp.modulate = Color(1, 1, 1, a)
		sp.z_index = 200 - i


func _update_text() -> void:
	var tx: Dictionary = cfg["text"]
	title_lbl.modulate = Color(1, 1, 1, smoothstep(0.15, 0.65, t))
	var cnt := int(floorf(maxf(0.0, t - 0.5) * 34.0))
	var line := str(tx["line"])
	line_lbl.visible_characters = cnt if cnt < line.length() else -1
