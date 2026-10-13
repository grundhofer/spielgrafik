extends Node2D
## Tuschmalerei (Sumi-e): Hafen von Lornholm.
## Alle Lagen, Lichtpunkte und der Ablauf der Figur kommen aus res://art/scene.json (tools/stage.py).
## Deterministisch: Zeit aus delta aufsummiert, Zufall nur über RandomNumberGenerator mit festem Seed.

const SEED := 20261011
const FPS := 30.0

var cfg: Dictionary
var t := 0.0
var rng := RandomNumberGenerator.new()

var paper_tex: Texture2D
var mat_ink: ShaderMaterial          # Vorlage für Tusche-Ebenen (multiplizierend)
var bg: Sprite2D
var mists: Array = []                # [sprite, speed]
var lights: Array = []               # [sprite, cfg]
var ripples: Array = []              # [sprite, start, dur]
var smokes: Array = []               # [sprite, phase]
var smoke_root: Sprite2D             # fester Rauchansatz direkt auf dem Schornstein
var gulls: Array = []                # [sprite, cfg]
var badger: Sprite2D
var badger_ink: Sprite2D
var badger_shadow: Sprite2D
var frames: Dictionary = {}          # name -> [Texture2D, Vector2 anchor]
var timeline: Array = []
var ui_nodes: Dictionary = {}
var figure_only := false


func _ready() -> void:
	rng.seed = SEED
	cfg = JSON.parse_string(FileAccess.get_file_as_string("res://art/scene.json"))
	paper_tex = load(cfg["paper"])
	_build_background()
	_build_mist()
	_build_ripples()
	_build_smoke()
	_build_lights()
	_build_gulls()
	_build_badger()
	_build_ui()
	# Prüfmodus für tools/measure_badger.py: nur die Figur (und ihr Bodenstrich) vor Magenta
	if "--figure-only" in OS.get_cmdline_user_args():
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
		for c in get_children():
			if c is CanvasItem and c != badger and c != badger_ink:
				(c as CanvasItem).visible = false
				c.set_process(false)
		figure_only = true
	_update(0.0)


func _shader(path: String) -> Shader:
	return load(path)


func _ink_material(amount := 1.0) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = _shader("res://shaders/ink_mul.gdshader")
	m.set_shader_parameter("amount", amount)
	return m


func _sprite(tex: Texture2D, pos: Vector2, centered := true) -> Sprite2D:
	var s := Sprite2D.new()
	s.texture = tex
	s.centered = centered
	s.position = pos
	add_child(s)
	return s


# --- Hintergrund ---------------------------------------------------------------------------------------------

func _build_background() -> void:
	bg = _sprite(load(cfg["bg"]), Vector2.ZERO, false)
	var m := ShaderMaterial.new()
	m.shader = _shader("res://shaders/bg_ink.gdshader")
	m.set_shader_parameter("paper", paper_tex)
	m.set_shader_parameter("noise_tex", load(cfg["bg_noise"]))
	bg.material = m


func _build_mist() -> void:
	for mc in cfg["mist"]:
		var s := _sprite(load(mc["tex"]), Vector2(mc["x"], mc["y"]), false)
		s.texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
		s.scale = Vector2(float(mc["w"]) / s.texture.get_width(), float(mc["h"]) / s.texture.get_height())
		var m := ShaderMaterial.new()
		m.shader = _shader("res://shaders/mist.gdshader")
		m.set_shader_parameter("paper", paper_tex)
		m.set_shader_parameter("amount", mc["amount"])
		m.set_shader_parameter("repeat_x", mc.get("repeat", 1.0))
		m.set_shader_parameter("soft_top", mc.get("soft_top", 0.35))
		m.set_shader_parameter("soft_bottom", mc.get("soft_bottom", 0.35))
		s.material = m
		mists.append([s, mc])


func _build_ripples() -> void:
	var rc: Dictionary = cfg["ripples"]
	var texs: Array = []
	for p in rc["textures"]:
		texs.append(load(p))
	for i in range(int(rc["count"])):
		var tex: Texture2D = texs[i % texs.size()]
		var s := _sprite(tex, Vector2.ZERO)
		s.material = _ink_material(rc["amount"])
		ripples.append([s, rc["slots"][i]])


func _smoke_offset(tex: Texture2D, foot: Array) -> Vector2:
	# Ursprung des Sprites = Fuß der Rauchfahne (unterster sichtbarer Teil der Textur, aus stage.py), damit die
	# Fahne auf der Schornsteinkante ansetzt statt mit dem leeren bzw. blassen Fußbereich darüber zu schweben
	return Vector2(tex.get_width() * 0.5 - float(foot[0]), tex.get_height() * 0.5 - float(foot[1]))


func _build_smoke() -> void:
	var sc: Dictionary = cfg["smoke"]
	var n := int(sc["count"])
	for i in range(n):
		var ti: int = i % sc["textures"].size()
		var tex: Texture2D = load(sc["textures"][ti])
		var s := _sprite(tex, Vector2.ZERO)
		s.offset = _smoke_offset(tex, sc["feet"][ti])
		s.material = _ink_material(sc["amount"])
		smokes.append([s, float(i) / n])
	# fester Ansatz: unterer Teil einer Fahne (oben weich ausgeblendet), wiegt sich leicht
	var rc: Dictionary = sc["root"]
	var ri := int(rc["texture"])
	var rtex: Texture2D = load(sc["textures"][ri])
	smoke_root = _sprite(rtex, Vector2(sc["x"], sc["y"]))
	smoke_root.offset = _smoke_offset(rtex, sc["feet"][ri])
	smoke_root.scale = Vector2.ONE * float(rc["scale"])
	var m := _ink_material(float(rc["amount"]))
	m.set_shader_parameter("fade_top", float(rc["fade_top"]))
	m.set_shader_parameter("fade_len", float(rc["fade_len"]))
	smoke_root.material = m


func _build_lights() -> void:
	# Licht wie in der Tuschmalerei als Zinnober-Scheibe (die rote Sonne der Tuschbilder), multiplizierend
	var glow: Texture2D = load(cfg["glow"])
	for lc in cfg["lights"]:
		var s := _sprite(glow, Vector2(lc["x"], lc["y"]))
		s.scale = Vector2.ONE * float(lc["r"]) / 64.0
		var c: Array = lc["color"]
		s.modulate = Color(c[0], c[1], c[2], 1.0)
		s.material = _ink_material(float(lc["amount"]))
		lights.append([s, lc])


func _build_gulls() -> void:
	var gc: Dictionary = cfg["gulls"]
	var texs: Array = []
	for p in gc["frames"]:
		texs.append(load(p))
	for g in gc["birds"]:
		var s := _sprite(texs[0], Vector2(g["x0"], g["y0"]))
		s.scale = Vector2.ONE * float(g["scale"])
		s.material = _ink_material(g.get("amount", 1.0))
		gulls.append([s, g, texs])


# --- Figur ---------------------------------------------------------------------------------------------------

func _build_badger() -> void:
	var bc: Dictionary = cfg["badger"]
	for name in bc["frames"].keys():
		var f: Dictionary = bc["frames"][name]
		frames[name] = [load(f["tex"]), Vector2(f["ax"], f["ay"])]
	timeline = bc["timeline"]
	if bc.has("shadow"):
		var sh: Dictionary = bc["shadow"]
		badger_shadow = _sprite(load(sh["tex"]), Vector2.ZERO)
		badger_shadow.scale = Vector2(sh["sx"], sh["sy"])
		badger_shadow.material = _ink_material(sh["amount"])
	# zwei Durchgänge mit derselben Textur: Papier in der Silhouette (deckend), dann Tusche multiplizierend
	# (läuft 1-2 px über die Silhouette hinaus ins Papier bzw. in den Hintergrund aus)
	badger = Sprite2D.new()
	badger.centered = false
	var m := ShaderMaterial.new()
	m.shader = _shader("res://shaders/figure.gdshader")
	m.set_shader_parameter("paper", paper_tex)
	badger.material = m
	add_child(badger)
	badger_ink = Sprite2D.new()
	badger_ink.centered = false
	var mi := ShaderMaterial.new()
	mi.shader = _shader("res://shaders/figure_ink.gdshader")
	mi.set_shader_parameter("noise_tex", load(cfg["bg_noise"]))
	badger_ink.material = mi
	add_child(badger_ink)


# --- Oberfläche ----------------------------------------------------------------------------------------------

func _font(path: String, size: int) -> FontVariation:
	var fv := FontVariation.new()
	fv.base_font = load(path)
	return fv


func _label(text: String, font: String, size: int, pos: Vector2, color: Color, reveal := false) -> Label:
	var l := Label.new()
	l.text = text
	l.position = pos
	var ls := LabelSettings.new()
	ls.font = load(font)
	ls.font_size = size
	ls.font_color = color
	l.label_settings = ls
	if reveal:
		var m := ShaderMaterial.new()
		m.shader = _shader("res://shaders/text_reveal.gdshader")
		l.material = m
	add_child(l)
	return l


func _build_ui() -> void:
	var u: Dictionary = cfg["ui"]
	var ink := Color(u["ink"][0], u["ink"][1], u["ink"][2], u["ink"][3])
	var dim := Color(u["ink_dim"][0], u["ink_dim"][1], u["ink_dim"][2], u["ink_dim"][3])
	# Pinselstrich hinter der gewählten Antwort (zuerst, damit die Schrift darüber liegt)
	var hs := _sprite(load(u["highlight"]["tex"]), Vector2(u["highlight"]["x"], u["highlight"]["y"]), false)
	hs.scale = Vector2(u["highlight"]["sx"], u["highlight"]["sy"])
	hs.material = _ink_material(u["highlight"]["amount"])
	ui_nodes["highlight"] = hs
	ui_nodes["title"] = _label(u["title"]["text"], u["font_bold"], u["title"]["size"],
		Vector2(u["title"]["x"], u["title"]["y"]), ink, true)
	ui_nodes["line"] = _label(u["line"]["text"], u["font"], u["line"]["size"],
		Vector2(u["line"]["x"], u["line"]["y"]), ink, true)
	if u["line"].has("width"):
		var l: Label = ui_nodes["line"]
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.size = Vector2(u["line"]["width"], 0)
	var tl: Label = ui_nodes["title"]
	var seal_x: float = tl.position.x + tl.get_minimum_size().x + float(u["seal"]["gap"])
	var seal := _sprite(load(u["seal"]["tex"]), Vector2(seal_x, u["seal"]["y"]))
	seal.material = _ink_material(1.0)
	ui_nodes["seal"] = seal
	var dots: Array = []
	var chs: Array = []
	for i in range(u["choices"].size()):
		var c: Dictionary = u["choices"][i]
		# Punkt auf die Mitte der x-Höhe: Grundlinie (Oberkante + Oberlänge der Schrift) minus halbe x-Höhe
		var cf: Font = load(u["font"])
		var cs := int(u["choice_size"])
		var dot_y: float = float(c["y"]) + cf.get_ascent(cs) - 0.5 * float(u["x_height_em"]) * cs
		var d := _sprite(load(c["dot"]), Vector2(float(c["x"]) - 18.0, dot_y))
		d.scale = Vector2.ONE * c.get("dot_scale", 1.0)
		d.material = _ink_material(1.0)
		dots.append(d)
		chs.append(_label(c["text"], u["font"], u["choice_size"], Vector2(c["x"], c["y"]),
			ink if c.get("selected", false) else dim, true))
	ui_nodes["dots"] = dots
	ui_nodes["choices"] = chs
	ui_nodes["parser"] = _label(u["parser"]["text"], u["font"], u["parser"]["size"],
		Vector2(u["parser"]["x"], u["parser"]["y"]), dim, true)
	var cur := ColorRect.new()
	cur.color = ink
	cur.size = Vector2(u["parser"]["size"] * 0.5, 2.5)
	add_child(cur)
	ui_nodes["cursor"] = cur


# --- Ablauf --------------------------------------------------------------------------------------------------

func _process(delta: float) -> void:
	t += delta
	_update(t)


func _ease(x: float) -> float:
	x = clamp(x, 0.0, 1.0)
	return x * x * (3.0 - 2.0 * x)


func _update(tt: float) -> void:
	# Tusche zieht beim Szenenstart ins Papier (helle Lasuren zuerst, satte Striche zuletzt)
	var a: Dictionary = cfg["bg_anim"]
	var p := clampf((tt - float(a["start"])) / float(a["dur"]), 0.0, 1.0)
	(bg.material as ShaderMaterial).set_shader_parameter("progress", p)

	for mm in mists:
		var s: Sprite2D = mm[0]
		var mc: Dictionary = mm[1]
		var off := float(mc["phase"]) + tt * float(mc["speed"]) / float(mc["w"]) * float(mc.get("repeat", 1.0))
		(s.material as ShaderMaterial).set_shader_parameter("offset", off)
		var breathe := 1.0 + 0.12 * sin(tt * 0.9 + float(mc["phase"]) * 6.28)
		(s.material as ShaderMaterial).set_shader_parameter("amount", float(mc["amount"]) * breathe)

	for rr in ripples:
		var s: Sprite2D = rr[0]
		var sl: Dictionary = rr[1]
		var per := float(sl["period"])
		var lt := fposmod(tt - float(sl["t0"]), per)
		var draw := float(sl["draw"])
		var hold := float(sl["hold"])
		var fade := float(sl["fade"])
		var m := s.material as ShaderMaterial
		s.position = Vector2(sl["x"], sl["y"]) + Vector2(roundf(lt * float(sl["drift"])), 0)
		s.scale = Vector2(sl["sx"], sl["sy"])
		s.flip_h = bool(sl.get("flip", false))
		if lt < draw:
			m.set_shader_parameter("reveal", lt / draw * 1.1)
			s.modulate.a = 1.0
		elif lt < draw + hold:
			m.set_shader_parameter("reveal", 2.0)
			s.modulate.a = 1.0
		elif lt < draw + hold + fade:
			m.set_shader_parameter("reveal", 2.0)
			s.modulate.a = 1.0 - _ease((lt - draw - hold) / fade)
		else:
			s.modulate.a = 0.0
		s.modulate.a *= p

	var sc: Dictionary = cfg["smoke"]
	for sm in smokes:
		var s: Sprite2D = sm[0]
		var life := float(sc["life"])
		var k := fposmod(tt / life + float(sm[1]), 1.0)
		var base := Vector2(sc["x"], sc["y"])
		# die Fahne löst sich langsam vom Schornstein (Aufstieg ~ k^rise_pow) und wird erst oben schneller;
		# das Pendeln wächst mit k, damit der Fuß am Schornstein bleibt
		var rk := pow(k, float(sc["rise_pow"]))
		s.position = base + Vector2(-k * float(sc["drift"]) + sin(k * 5.0 + float(sm[1]) * 9.0) * 6.0 * k, -rk * float(sc["rise"]))
		s.scale = Vector2.ONE * lerpf(float(sc["s0"]), float(sc["s1"]), k)
		s.rotation = lerpf(0.0, -0.35, k)
		# am Schornstein schon sichtbar (kurzes Einblenden), dann mit dem Aufsteigen verblassen
		s.modulate.a = smoothstep(0.0, 0.06, k) * pow(1.0 - k, 1.5) * p
	var rc: Dictionary = sc["root"]
	smoke_root.rotation = sin(tt * 1.3) * 0.07 + sin(tt * 0.55 + 1.0) * 0.04
	smoke_root.modulate.a = (0.85 + 0.15 * sin(tt * 2.3)) * p

	for lt in lights:
		var s: Sprite2D = lt[0]
		var lc: Dictionary = lt[1]
		var amt := float(lc["amount"])
		match String(lc["kind"]):
			"lamp":
				# Leuchtfeuer: Kennung "Blinken alle 2 s", weich auf- und abschwellend
				var ph := fposmod(tt + float(lc.get("phase", 0.0)), float(lc["period"]))
				var on := _ease(ph / 0.25) * (1.0 - _ease((ph - 0.6) / 0.5))
				amt *= lerpf(float(lc["low"]), 1.0, on)
				s.scale = Vector2.ONE * float(lc["r"]) / 64.0 * lerpf(0.8, 1.15, on)
			"lantern":
				var f := 0.75 + 0.15 * sin(tt * 13.0) + 0.1 * sin(tt * 29.0 + 1.0) + 0.08 * sin(tt * 4.3)
				amt *= f
			_:
				amt *= 0.92 + 0.08 * sin(tt * 2.1)
		# Lichter erst, wenn ihre Gebäude eingezogen sind
		(s.material as ShaderMaterial).set_shader_parameter("amount", amt * smoothstep(0.7, 1.0, p))

	for g in gulls:
		var s: Sprite2D = g[0]
		var gc: Dictionary = g[1]
		var texs: Array = g[2]
		var k := (tt + float(gc["t0"])) / float(gc["dur"])
		s.position = Vector2(lerpf(gc["x0"], gc["x1"], k), lerpf(gc["y0"], gc["y1"], k) + sin(k * 9.0) * 4.0)
		s.position = s.position.round()
		# Flügelschlag als Ping-Pong: oben, Mitte, unten, Mitte
		var fi := int(floor((tt + float(gc["t0"])) * float(gc["fps"])))
		var seq := [0, 1, 2, 1]
		s.texture = texs[seq[fi % seq.size()]]
		s.modulate.a = p

	_update_badger(tt, p)
	_update_ui(tt)
	if figure_only:
		for c in get_children():
			if c is CanvasItem and c != badger and c != badger_ink:
				(c as CanvasItem).visible = false


func _update_badger(tt: float, p: float) -> void:
	var fi := clampi(int(floor(tt * FPS + 0.001)), 0, timeline.size() - 1)
	var e: Array = timeline[fi]
	var f: Array = frames[e[0]]
	var anchor: Vector2 = f[1]
	var foot := Vector2(float(e[1]), float(cfg["badger"]["foot_y"]))
	for b in [badger, badger_ink]:
		b.texture = f[0]
		b.position = (foot - anchor).round()
		var m := b.material as ShaderMaterial
		m.set_shader_parameter("foot_y", anchor.y)
		m.set_shader_parameter("breathe", float(e[2]) if e.size() > 2 else 0.0)
	# die Tusche der Figur zieht wie der Hintergrund ein (gleicher Fortschritt, gleiches Rauschen)
	(badger_ink.material as ShaderMaterial).set_shader_parameter("progress", p)
	if badger_shadow:
		var sh: Dictionary = cfg["badger"]["shadow"]
		badger_shadow.position = (foot + Vector2(sh["dx"], sh["dy"])).round()
		badger_shadow.modulate.a = p


func _update_ui(tt: float) -> void:
	var u: Dictionary = cfg["ui"]
	var r: Dictionary = u["reveal"]
	# Schrift wird geschrieben: Ort, dann Zeile, dann Antworten (Bildschirm-x je Zeitpunkt)
	_reveal(ui_nodes["title"], tt, float(r["title"]), float(r["speed"]))
	_reveal(ui_nodes["line"], tt, float(r["line"]), float(r["speed"]))
	for i in range(ui_nodes["choices"].size()):
		_reveal(ui_nodes["choices"][i], tt, float(r["choices"]) + i * 0.12, float(r["speed"]) * 1.4)
		var d: Sprite2D = ui_nodes["dots"][i]
		d.modulate.a = _ease((tt - float(r["choices"]) - i * 0.12) / 0.15)
	_reveal(ui_nodes["parser"], tt, float(r["parser"]), float(r["speed"]))
	# Stempel wird aufgedrückt
	var seal: Sprite2D = ui_nodes["seal"]
	var ks := clampf((tt - float(r["seal"])) / 0.18, 0.0, 1.0)
	seal.modulate.a = 1.0 if ks >= 1.0 else ks * ks
	seal.scale = Vector2.ONE * float(u["seal"]["scale"]) * lerpf(1.25, 1.0, _ease(ks))
	# Pinselstrich unter der gewählten Antwort wird gezogen
	var hs: Sprite2D = ui_nodes["highlight"]
	var kh := clampf((tt - float(r["highlight"])) / 0.45, 0.0, 1.0)
	(hs.material as ShaderMaterial).set_shader_parameter("reveal", 2.0 if kh >= 1.0 else kh * 1.1)
	hs.visible = tt >= float(r["highlight"])
	# Schreibmarke
	var cur: ColorRect = ui_nodes["cursor"]
	var pl: Label = ui_nodes["parser"]
	cur.position = Vector2(pl.position.x + pl.get_minimum_size().x + 4, pl.position.y + float(u["parser"]["size"]) * 1.25)
	cur.visible = tt > float(r["parser"]) + 0.4 and fmod(tt, 1.0) < 0.6


func _reveal(l: Label, tt: float, start: float, speed: float) -> void:
	var m := l.material as ShaderMaterial
	if m == null:
		return
	var x := l.position.x + (tt - start) * speed
	m.set_shader_parameter("reveal_x", x if tt < start + 4.0 else 99999.0)
