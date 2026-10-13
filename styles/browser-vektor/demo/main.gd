extends Node2D
## Vektor-Cartoon der Browserspiel-Ära: Bühne 550×400 mittig auf 1280×720 (Faktor 1,8, grauer Rand),
## alles aus Polygon2D, Animation als Bewegungs- und Form-Tweens, auf 24 Bilder/s quantisiert.
##
## Prüfschalter nach "--": --t0=<s>  --probe-no-badger  --probe-measure (ohne Zeiger, Schild, Schatten)
##                          --probe-nobake (jede Form als eigener Knoten, zum Vergleich)
##                          --probe-ssaa (Überabtastung wie unter Compatibility, auch in Forward+)
##                          --probe-feet=near|far (ein Fuß eingefärbt, der andere bzw. was ihn verdeckt
##                          ausgeblendet; nur für die Messung)
##                          --probe-cont (ohne 24-fps-Raster)  --probe-stats

const V = preload("res://vec.gd")
const H = preload("res://harbor.gd")
const M = preload("res://morph.gd")
const B = preload("res://badger.gd")
const UI = preload("res://ui.gd")

const STAGE_SIZE := Vector2(550, 400)
const SCALE := 1.8
const ANIM_FPS := 24.0
const STEP_T := 5.0 / 24.0          # Dauer eines Schritts (5 Bilder bei 24 fps)
const GROUND := 322.0
const UI_TEXT := {
	"location": "Hafen von Lornholm",
	"line": "Die Laterne flackert im Wind. Am Kai wartet ein Paket auf dich.",
	"choices": ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"],
}

var t := 0.0
var frame := -1
var quantize := true
var tweens: Array[Tween] = []
var R: Dictionary
var badger
var ui
var stage: Node2D
var fly: Node2D
var gulls: Array = []
var probe := {}

# von Tweens geschriebene Größen, je Bild angewendet
var walk_p := 0.0
var b_sq := 0.0
var breath := 0.0
var hop_y := 0.0
var head_rot := 0.0
var pupil_off := Vector2(1.0, 0.4)


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=")
		probe[kv[0]] = kv[1] if kv.size() > 1 else "1"
	quantize = not probe.has("probe-cont")
	# Kantenglättung: Forward+/Mobile über 8×-MSAA (Projekteinstellung). Compatibility (Web-Export) kann kein
	# 2D-MSAA; dort wird die Bühne doppelt so groß in einen SubViewport gezeichnet und halbiert (2×2-Überabtastung).
	var ssaa := probe.has("probe-ssaa") or RenderingServer.get_current_rendering_method() == "gl_compatibility"
	var k := 2.0 if ssaa else 1.0
	var origin := Vector2((1280.0 - STAGE_SIZE.x * SCALE) * 0.5, 0)
	var holder: Node = self
	if ssaa:
		var svp := SubViewport.new()
		svp.name = "SSAA"
		svp.size = Vector2i(STAGE_SIZE * SCALE * k)
		svp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
		svp.disable_3d = true
		add_child(svp)
		var spr := Sprite2D.new()
		spr.texture = svp.get_texture()
		spr.centered = false
		spr.position = origin
		spr.scale = Vector2(1.0 / k, 1.0 / k)
		spr.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR
		add_child(spr)
		holder = svp
		origin = Vector2.ZERO
	var clip := Control.new()
	clip.name = "StageClip"
	clip.position = origin
	clip.size = STAGE_SIZE * SCALE * k
	clip.clip_contents = true
	clip.mouse_filter = Control.MOUSE_FILTER_IGNORE
	holder.add_child(clip)
	stage = V.group(clip, "Stage")
	stage.scale = Vector2(SCALE, SCALE) * k
	R = H.build(stage)
	_gulls()
	badger = B.new()
	badger.position = Vector2(0, GROUND)
	badger.x0 = 170.0 - B.N_STEPS * B.S - B.S * 0.25
	stage.add_child(badger)
	ui = UI.new()
	ui.oversampling = 2.0 * k
	ui.build(stage, UI_TEXT)
	var tip_light: Node2D = ui.make_tip(stage, UI_TEXT["choices"][0], Vector2(-12, -22))
	var tip_parcel: Node2D = ui.make_tip(stage, UI_TEXT["choices"][1])
	var tip_badger: Node2D = ui.make_tip(stage, UI_TEXT["choices"][2], Vector2(16, 6))
	# fliegendes Paket über der Leiste (Ursprung in der Mitte, damit es sich um sich selbst dreht)
	fly = V.group(stage, "FlyParcel")
	ui.icon_parcel(V.group(fly, "Art"))
	fly.visible = false
	# Zeiger zuoberst
	stage.move_child(ui.ring, -1)
	stage.move_child(ui.cursor, -1)
	if probe.has("probe-no-badger"):
		badger.visible = false
	if probe.get("probe-feet", "") == "near":
		badger.near_foot.modulate = Color(4.0, 0.3, 0.3)
		badger.far_foot.visible = false
	elif probe.get("probe-feet", "") == "far":
		badger.far_foot.modulate = Color(0.3, 4.0, 0.3)
		badger.near_foot.visible = false
		badger.near_leg.visible = false
	if probe.has("probe-measure"):
		ui.cursor.visible = false
		ui.ring.visible = false
		badger.shadow.visible = false
		for tk in ui.tips:
			ui.tips[tk].modulate.a = 0.0
	if not probe.has("probe-nobake"):
		_bake_all()
	_ambient()
	_story(tip_light, tip_parcel, tip_badger)
	if probe.has("probe-stats"):
		var n := 0
		for c in stage.find_children("*", "Polygon2D", true, false):
			n += 1
		print("STATS ", JSON.stringify(V.stats), " polygon2d=", n)
	var t0 := float(probe.get("t0", "0"))
	if t0 > 0.0:
		t = t0
		var f := int(floor(t0 * ANIM_FPS + 1e-4))
		while frame < f:
			_advance()
	_apply()


func _process(delta: float) -> void:
	t += delta
	if probe.has("probe-stats") and Engine.get_process_frames() == 20:
		print("DRAW calls=", Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME),
			" objects=", Performance.get_monitor(Performance.RENDER_TOTAL_OBJECTS_IN_FRAME),
			" primitives=", Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME))
	if quantize:
		var f := int(floor(t * ANIM_FPS + 1e-4))
		var changed := false
		while frame < f:
			_advance()
			changed = true
		if changed:
			_apply()
	else:
		for tw in tweens:
			if tw.is_valid():
				tw.custom_step(delta)
		frame = int(floor(t * ANIM_FPS))
		_apply()


func _advance() -> void:
	frame += 1
	if frame == 0:
		return
	for tw in tweens:
		if tw.is_valid():
			tw.custom_step(1.0 / ANIM_FPS)


func _tw() -> Tween:
	var tw := create_tween()
	tw.pause()
	tweens.append(tw)
	return tw


## Endlos hin und her (Bewegungs-Tween mit Sinus-Easing), um 'offset' Sekunden vorgespult.
func _pingpong(obj: Object, prop: String, a, b, dur: float, offset := 0.0) -> void:
	var tw := _tw().set_loops()
	tw.tween_property(obj, prop, b, dur).from(a).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_property(obj, prop, a, dur).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	if offset > 0.0:
		tw.custom_step(offset)


func _morph_loop(m, dur: float, offset := 0.0) -> void:
	var tw := _tw().set_loops()
	tw.tween_method(m.set_t, 0.0, 1.0, dur).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	tw.tween_method(m.set_t, 1.0, 0.0, dur).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	if offset > 0.0:
		tw.custom_step(offset)


# ------------------------------------------------------------------ Zusammenfassen
## Unbewegte Formen je Gruppe zu Netzen mit Eckpunktfarben zusammenfassen (Zeichenaufrufe sparen).
## Animierte Gruppen bleiben Knoten; zusammengefasst wird nur ihr Inneres.
func _bake_all() -> void:
	var morphs := []
	for m in R["waves"] + R["streaks"] + R["waterlines"] + [R["sailB"], R["pennantA"]]:
		morphs.append_array([m.fill_pg, m.ink_pg])
	for gl in gulls:
		morphs.append_array([gl[1].fill_pg, gl[1].ink_pg])
	for c in stage.get_children():
		for prefix in ["Islands", "Headland", "Lighthouse", "Jetty", "Cottage", "Quay", "LanternPost", "Rope", "Barrel", "Crate"]:
			if String(c.name).begins_with(prefix):
				V.bake(c)
	for c in R["clouds"]:
		V.bake(c)
	for p in R["smoke"].get_children():
		V.bake(p)
	V.bake(R["boatA"], morphs)
	V.bake(R["boatB"], morphs)
	for gl in gulls:
		V.bake(gl[0], morphs)
	V.bake(R["lantern"], [R["lantern_glow"], R["flame"]])
	V.bake(R["parcel_art"])
	V.bake(fly.get_child(0))
	var b = badger
	for part in [b.shadow, b.far_leg, b.near_leg, b.far_foot, b.near_foot]:
		V.bake(part)
	V.bake(b.body.get_child(0), [b.far_arm, b.scarf_end, b.near_arm, b.head])
	for piv in [b.far_arm, b.scarf_end, b.near_arm]:
		V.bake(piv.get_child(0))
	V.bake(b.head.get_child(0), [b.eye])
	V.bake(b.eye, [b.pupil])
	V.bake(b.pupil)
	V.bake(stage.get_node("UI"), ui.nav + ui.slots)
	for n in ui.nav + ui.slots:
		V.bake(n)
	for k in ui.tips:
		V.bake(ui.tips[k])
	V.bake(ui.arrow)
	V.bake(ui.hand)
	V.bake(ui.ring)
	if probe.has("probe-stats"):
		print("BAKE ", JSON.stringify(V.bake_stats), " waves=", R["waves"].size(), " streaks=", R["streaks"].size())


# ------------------------------------------------------------------ Umgebung
func _gulls() -> void:
	for spec in [[Vector2(0, 0), 0.0], [Vector2(26, 14), 1.3]]:
		var g := V.group(stage, "Gull")
		g.scale = Vector2(1.25, 1.25)
		var up := [Vector2(-12, -7), Vector2(-6, -4), Vector2(0, -1.2), Vector2(6, -4), Vector2(12, -7), Vector2(6, -1.4), Vector2(0, 1.4), Vector2(-6, -1.4)]
		var dn := [Vector2(-11, 3.5), Vector2(-6, -1.0), Vector2(0, -1.2), Vector2(6, -1.0), Vector2(11, 3.5), Vector2(6, 1.2), Vector2(0, 1.6), Vector2(-6, 1.2)]
		var m = M.make_shape(g, up, dn, Color("f6f2ff"), 1.0, 5)
		V.fill(g, V.ellipse(Vector2(0, 0.2), 2.2, 1.5, 12), Color("f6f2ff"))
		V.fill(g, PackedVector2Array([Vector2(-2.6, 0.4), Vector2(-4.4, 0.0), Vector2(-2.6, -0.6)]), Color("ffb23c"))
		gulls.append([g, m, spec[0], spec[1]])


func _ambient() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261013
	for m in R["waves"]:
		_morph_loop(m, rng.randf_range(0.9, 1.5), rng.randf_range(0.0, 2.0))
	for m in R["streaks"]:
		_morph_loop(m, rng.randf_range(1.1, 1.7), rng.randf_range(0.0, 2.0))
	for m in R["waterlines"]:
		_morph_loop(m, 1.1, rng.randf_range(0.0, 1.0))
	_morph_loop(R["sailB"], 1.5, 0.3)
	_morph_loop(R["pennantA"], 0.42, 0.1)
	# Boote schaukeln (Bewegungs-Tween: Drehung + Höhe)
	var bA: Node2D = R["boatA"]
	var bB: Node2D = R["boatB"]
	_pingpong(bA, "rotation", -0.045, 0.045, 1.3, 0.4)
	_pingpong(bA, "position:y", bA.position.y - 1.0, bA.position.y + 1.0, 1.05, 0.0)
	_pingpong(bB, "rotation", 0.06, -0.06, 1.1, 0.9)
	_pingpong(bB, "position:y", bB.position.y + 0.8, bB.position.y - 0.8, 0.95, 0.5)
	# Wolken treiben, Sterne funkeln
	var i := 0
	for c in R["clouds"]:
		_pingpong(c, "position:x", c.position.x - 4.0, c.position.x + 4.0, 4.0 + i, i * 1.7)
		i += 1
	for s in R["stars"]:
		_pingpong(s, "scale", Vector2(0.45, 0.45), Vector2(1.15, 1.15), rng.randf_range(0.5, 1.1), rng.randf_range(0, 1.2))
	# Laterne pendelt
	_pingpong(R["lantern"], "rotation", -0.07, 0.07, 0.9, 0.45)
	# Leuchtfeuer dreht sich (Strahl als Projektion: scale.x = cos)
	var tw := _tw().set_loops()
	tw.tween_method(_set_beam, 0.0, TAU, 4.4)
	tw.custom_step(1.3)
	# Rauch: Kringel steigen auf, wachsen, verblassen (Bewegungs-Tween mit Easing)
	var top: Vector2 = R["chimney_top"]
	for k in 4:
		var p := V.group(R["smoke"], "Puff", top)
		var blob := V.smooth([Vector2(-9, 2), Vector2(-10, -4), Vector2(-5, -9), Vector2(1, -8), Vector2(6, -10), Vector2(10, -5), Vector2(9, 2), Vector2(2, 4)], true, 6)
		V.fill(p, blob, Color("cbbfdc"))
		V.fill(p, V.smooth([Vector2(-7, -3), Vector2(-4, -7), Vector2(0, -6.6), Vector2(-4, -4.6)], true, 4), Color("ebe4f4"))
		V.ink(p, blob, 1.2, 0.4, [], Color("3a2a52"))
		var st := _tw().set_loops()
		st.set_parallel(true)
		st.tween_property(p, "position:y", top.y - 58.0, 3.2).from(top.y - 3.0)
		st.tween_property(p, "position:x", top.x - 30.0, 3.2).from(top.x).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
		st.tween_property(p, "scale", Vector2(1.5, 1.5), 3.2).from(Vector2(0.5, 0.5)).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)
		st.tween_method(_puff_alpha.bind(p), 0.0, 1.0, 3.2)
		st.tween_property(p, "rotation", -0.6, 3.2).from(0.0)
		st.custom_step(k * 0.8)
	# Möwen ziehen in Bögen über den Himmel, Flügelschlag als Form-Tween
	for gl in gulls:
		var g: Node2D = gl[0]
		var off: Vector2 = gl[2]
		var gt := _tw().set_loops()
		gt.tween_method(func(u: float) -> void: g.position = Vector2(lerpf(600.0, -60.0, u), 122.0 - 26.0 * sin(PI * u)) + off, 0.0, 1.0, 9.0)
		gt.custom_step(2.6 + float(gl[3]))
		_morph_loop(gl[1], 0.22, float(gl[3]) * 0.31)
	# Pfeile pulsieren
	for n in ui.nav:
		_pingpong(n, "scale", Vector2(1, 1), Vector2(1.14, 1.14), 0.55)


func _puff_alpha(u: float, p: Node2D) -> void:
	p.modulate.a = clampf((1.0 - u) / 0.4, 0.0, 1.0)


func _set_beam(a: float) -> void:
	var beam: Node2D = R["beam"]
	beam.scale.x = cos(a)
	var flash := pow(maxf(0.0, sin(a)), 10.0)
	R["lamp"].scale = Vector2.ONE * (1.0 + 1.1 * flash)


# ------------------------------------------------------------------ Handlung
func _story(tip_light: Node2D, tip_parcel: Node2D, tip_badger: Node2D) -> void:
	var cur: Node2D = ui.cursor
	var parcel: Node2D = R["parcel"]
	var lh: Vector2 = R["lighthouse_hotspot"]
	var pp := parcel.position + Vector2(2, -11)
	var bh := Vector2(178, 288)
	cur.position = Vector2(470, 300)
	# Dachs: Gang (13 Schritte + Schlussschritt), dann Aufsetzen mit Stauchen und Nachfedern
	var walk_t := (B.N_STEPS + 1) * STEP_T
	var w := _tw()
	w.tween_property(self, "walk_p", float(B.N_STEPS + 1), walk_t).from(0.0)
	w.tween_property(self, "b_sq", 0.085, 0.07).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	w.tween_property(self, "b_sq", 0.0, 0.6).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
	# Freudenhüpfer, wenn der Zeiger auf ihm steht: ausholen, strecken, landen, nachfedern
	w.tween_interval(5.30 - walk_t - 0.67)
	w.tween_property(self, "b_sq", 0.10, 0.10).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	w.set_parallel(true)
	w.chain().tween_property(self, "b_sq", -0.09, 0.16).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	w.tween_property(self, "hop_y", 9.0, 0.16).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	w.chain().tween_property(self, "hop_y", 0.0, 0.14).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_IN)
	w.tween_property(self, "b_sq", 0.0, 0.14)
	w.chain().tween_property(self, "b_sq", 0.08, 0.06).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	w.chain().tween_property(self, "b_sq", 0.0, 0.6).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)
	_pingpong(self, "breath", -0.012, 0.012, 0.8)
	# Kopf und Blick: zum Paket, dem fliegenden Paket nach, zum Zeiger
	var hd := _tw()
	hd.tween_interval(walk_t + 0.05)
	hd.set_parallel(true)
	hd.chain().tween_property(self, "head_rot", 0.12, 0.3).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	hd.tween_property(self, "pupil_off", Vector2(1.4, 1.4), 0.2)
	hd.chain().tween_interval(3.80 - walk_t - 0.35)
	hd.chain().tween_property(self, "head_rot", -0.14, 0.35).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	hd.tween_property(self, "pupil_off", Vector2(0.6, -1.4), 0.25)
	hd.chain().tween_interval(0.5)
	hd.chain().tween_property(self, "head_rot", 0.0, 0.35).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	hd.tween_property(self, "pupil_off", Vector2(-0.2, 1.0), 0.3)
	# Blinzeln (zwei Bilder bei 24 fps)
	var bl := _tw()
	var last := 0.0
	for at in [1.5, 3.30, 5.95]:
		bl.tween_interval(at - last)
		bl.tween_callback(_blink.bind(0.12))
		bl.tween_interval(2.0 / ANIM_FPS)
		bl.tween_callback(_blink.bind(1.0))
		last = at + 2.0 / ANIM_FPS
	# Zeiger: Leuchtturm -> Paket (Klick) -> Dachs
	var c := _tw()
	c.tween_interval(0.30)
	c.tween_property(cur, "position", lh, 0.80).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	c.tween_callback(_hover.bind(tip_light, lh))
	c.tween_property(tip_light, "scale", Vector2.ONE, 0.18).from(Vector2(0.4, 0.4)).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	c.tween_interval(0.57)
	c.tween_callback(_unhover.bind(tip_light))
	c.tween_property(cur, "position", pp, 0.85).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	c.tween_callback(_hover.bind(tip_parcel, pp))
	c.tween_property(tip_parcel, "scale", Vector2.ONE, 0.18).from(Vector2(0.4, 0.4)).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	c.tween_interval(3.55 - 2.88)
	# Klick: Hand drückt, Ring läuft aus
	c.tween_property(cur, "scale", Vector2(0.82, 0.82), 0.07)
	c.tween_callback(_click.bind(pp))
	c.tween_property(cur, "scale", Vector2.ONE, 0.10).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	c.tween_callback(_unhover.bind(tip_parcel))
	c.tween_interval(4.55 - 3.72)
	c.tween_property(cur, "position", bh, 0.70).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_IN_OUT)
	c.tween_callback(_hover.bind(tip_badger, bh))
	c.tween_property(tip_badger, "scale", Vector2.ONE, 0.18).from(Vector2(0.4, 0.4)).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	# Paket: stauchen, strecken, im Bogen ins Inventar, Feld federt
	var slot: Node2D = ui.slots[4]
	var start := parcel.position + Vector2(0, -7.5)
	var dest: Vector2 = slot.position
	var p := _tw()
	p.tween_interval(3.62)
	p.tween_property(parcel, "scale", Vector2(1.32, 0.68), 0.08).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	p.tween_property(parcel, "scale", Vector2(0.82, 1.25), 0.08).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	p.tween_callback(_fly_start.bind(start))
	p.set_parallel(true)
	p.tween_method(_fly_at.bind(start, dest), 0.0, 1.0, 0.62).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	p.tween_property(fly, "rotation", -TAU, 0.62).from(0.0).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_IN_OUT)
	p.tween_property(fly, "scale", Vector2(0.95, 0.95), 0.62).from(Vector2(1.0, 1.25)).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	p.chain().tween_callback(_fly_end.bind(slot))
	p.chain().tween_property(slot, "scale", Vector2.ONE, 0.55).from(Vector2(1.45, 1.45)).set_trans(Tween.TRANS_ELASTIC).set_ease(Tween.EASE_OUT)


func _blink(sy: float) -> void:
	badger.eye.scale.y = sy


func _fly_start(start: Vector2) -> void:
	R["parcel"].visible = false
	fly.visible = true
	fly.position = start


## Bogen als quadratische Bézierkurve über einen Punkt rechts oberhalb des Pakets.
func _fly_at(u: float, start: Vector2, dest: Vector2) -> void:
	var mid := Vector2(262, 100)
	fly.position = start.lerp(mid, u).lerp(mid.lerp(dest, u), u)


func _fly_end(slot: Node2D) -> void:
	fly.visible = false
	ui.icon_parcel(V.group(slot, "Parcel"))


func _hover(tip: Node2D, at: Vector2) -> void:
	ui.arrow.visible = false
	ui.hand.visible = true
	tip.position = at
	tip.visible = true


func _unhover(tip: Node2D) -> void:
	ui.arrow.visible = true
	ui.hand.visible = false
	tip.visible = false


func _click(at: Vector2) -> void:
	if probe.has("probe-measure"):
		return
	var r: Node2D = ui.ring
	r.position = at
	r.visible = true
	var tw := _tw()
	tw.set_parallel(true)
	tw.tween_property(r, "scale", Vector2(2.2, 2.2), 0.35).from(Vector2(0.3, 0.3)).set_trans(Tween.TRANS_QUAD).set_ease(Tween.EASE_OUT)
	tw.tween_property(r, "modulate:a", 0.0, 0.35).from(1.0)


# ------------------------------------------------------------------ je Bild (24 fps)
func _apply() -> void:
	var tq := frame / ANIM_FPS if quantize else t
	if walk_p < B.N_STEPS + 1:
		badger.walk_pose(walk_p)
	else:
		badger.walk_pose(B.N_STEPS + 1)
		badger.stand_pose(b_sq + breath, hop_y)
		badger.head.rotation = head_rot
		badger.scarf_end.rotation = 0.12 + 0.07 * sin(TAU * tq / 1.3) + 0.04 * sin(TAU * tq / 0.53)
		badger.far_arm.rotation = 0.05 * sin(TAU * tq / 1.6) - 0.25 * hop_y / 9.0
		badger.near_arm.rotation = -0.12 * hop_y / 9.0
	badger.pupil.position = pupil_off
	# Laterne flackert: Zufall mit fester Saat je Bild
	var rng := RandomNumberGenerator.new()
	rng.seed = 7000 + frame
	var fl := rng.randf()
	R["lantern_glow"].scale = Vector2.ONE * (0.9 + 0.22 * fl)
	R["lantern_glow"].modulate.a = 0.72 + 0.28 * rng.randf()
	R["flame"].scale = Vector2(0.85 + 0.25 * rng.randf(), 0.8 + 0.4 * fl)
	R["window_glow"].modulate.a = 0.85 + 0.15 * sin(TAU * tq / 2.3)
