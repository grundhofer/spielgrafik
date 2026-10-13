extends Node
## Nachbearbeitung als Kette von SubViewports (je ein ColorRect mit Shader, Gleitkomma-Ziele).
## Godot zeichnet Geschwister-Viewports in der Reihenfolge, in der sie in den Baum kommen; die
## Durchgänge entstehen hier nach Color und Ctrl und lesen deshalb im selben Bild deren Ergebnis
## (geprüft: Kanten bewegter Objekte liegen in allen Durchgängen auf demselben Pixel).
##
##   Color (3D, sRGB) ─┬─ Tensor ─ Blur x ─ Blur y ─┬─ Kuwahara ─┬─ Blur x ─ Blur y ─┐
##                     │                             └─ LIC ──────┼───────────────────┼─ Paint (Bildschirm)
##   Ctrl (Steuerkarte) ─────────────────────────────────────────┴───────────────────┘
##
## Voreinstellungen der Malart in PRESETS; Vergleichsschalter siehe main.gd.

const SIZE := Vector2i(1280, 720)

const PRESETS := {
	# Deckende Malerei (Gouache/Öl) auf grobem Papier: kräftiger Kuwahara, sichtbare Striche,
	# Randabdunklung mäßig
	"gouache": {
		"kuwahara": {"r_min": 2.5, "r_max": 9.0, "q": 8.0, "alpha": 1.0},
		"lic": {"len_min": 6.0, "len_max": 15.0},
		"paint": {"edge_strength": 1.6, "stroke_tone": 0.20, "stroke_relief": 0.25, "stroke_hue": 0.08,
				"turbulence": 0.14, "granulation": 0.14, "paper_relief": 0.05, "wobble_px": 1.4, "border": 1.0,
				"gain": 1.08},
	},
	# Aquarell: kleinere Flächen, starke Ränder, Granulation, Lasur
	"aquarell": {
		"kuwahara": {"r_min": 2.0, "r_max": 7.0, "q": 6.0, "alpha": 1.0},
		"lic": {"len_min": 3.0, "len_max": 8.0},
		"paint": {"wash": 0.85, "wash_sat": 0.9, "edge_strength": 2.2, "edge_gain": 3.0, "stroke_tone": 0.05,
				"stroke_relief": 0.0, "stroke_hue": 0.03, "turbulence": 0.30, "granulation": 0.30,
				"paper_relief": 0.08, "wobble_px": 2.4, "border": 1.0, "paper_tint": 0.04},
	},
}

@export var color_vp: SubViewport
@export var ctrl_vp: SubViewport
@export var paint_rect: ColorRect

var mats := {}


func _ready() -> void:
	var opts := {}
	for a in OS.get_cmdline_user_args():
		var kv := a.trim_prefix("--").split("=", true, 1)
		opts[kv[0]] = kv[1] if kv.size() > 1 else true
	var preset: Dictionary = PRESETS[opts.get("preset", "gouache")]
	var color_tex := color_vp.get_texture()
	var ctrl_tex := ctrl_vp.get_texture()

	var tensor := _pass("Tensor", "res://shaders/post_tensor.gdshader", {"src": color_tex})
	var tbx := _pass("TensorBlurX", "res://shaders/post_blur.gdshader", {"src": tensor, "dir": Vector2(1, 0), "sigma": 3.5})
	var tfm := _pass("TensorBlurY", "res://shaders/post_blur.gdshader", {"src": tbx, "dir": Vector2(0, 1), "sigma": 3.5})
	var kp: Dictionary = preset["kuwahara"].duplicate()
	kp.merge({"src": color_tex, "tfm": tfm, "ctrl": ctrl_tex})
	if opts.has("no-kuwahara"):
		kp["radius_scale"] = 0.0
	var kuw := _pass("Kuwahara", "res://shaders/post_kuwahara.gdshader", kp)
	var kbx := _pass("KuwBlurX", "res://shaders/post_blur.gdshader", {"src": kuw, "dir": Vector2(1, 0), "sigma": 3.0})
	var kblur := _pass("KuwBlurY", "res://shaders/post_blur.gdshader", {"src": kbx, "dir": Vector2(0, 1), "sigma": 3.0})
	var lp: Dictionary = preset["lic"].duplicate()
	lp.merge({"tfm": tfm, "ctrl": ctrl_tex})
	if opts.has("no-lic"):
		lp["contrast"] = 0.0
	if opts.has("screen-noise"):
		lp["screen_noise"] = 1.0
	var lic := _pass("Lic", "res://shaders/post_lic.gdshader", lp)

	var pm := ShaderMaterial.new()
	pm.shader = load("res://shaders/post_paint.gdshader")
	var pp: Dictionary = preset["paint"].duplicate()
	pp.merge({"kuw": kuw, "kblur": kblur, "lic": lic, "ctrl": ctrl_tex})
	if opts.has("no-edges"):
		pp["edge_strength"] = 0.0
	if opts.has("no-paper"):
		pp.merge({"paper_relief": 0.0, "granulation": 0.0, "border": 0.0, "paper_tint": 0.0, "turbulence": 0.0,
				"wobble_px": 0.0}, true)
	for k in pp:
		pm.set_shader_parameter(k, pp[k])
	mats["Paint"] = pm
	paint_rect.material = pm

	# Feineinstellung beim Ausprobieren: --set=Kuwahara.r_max=12,Paint.stroke_tone=0.2
	if opts.has("set"):
		for kv in String(opts["set"]).split(","):
			var parts := kv.split("=")
			var path := parts[0].split(".")
			(mats[path[0]] as ShaderMaterial).set_shader_parameter(path[1], float(parts[1]))

	if opts.has("raw") or opts.has("mask"):
		paint_rect.material = _copy_material(color_tex)
		# ohne Nachbearbeitung: Steuerkamera und Durchgänge gar nicht rendern (Vergleich der Bildzeit)
		ctrl_vp.render_target_update_mode = SubViewport.UPDATE_DISABLED
		for c in get_children():
			(c as SubViewport).render_target_update_mode = SubViewport.UPDATE_DISABLED
	elif opts.has("show-ctrl"):
		paint_rect.material = _copy_material(ctrl_tex)
	elif opts.has("show"):
		var name: String = opts["show"]
		paint_rect.material = _copy_material((get_node(name) as SubViewport).get_texture())


func _pass(pass_name: String, shader_path: String, params: Dictionary) -> ViewportTexture:
	var vp := SubViewport.new()
	vp.name = pass_name
	vp.size = SIZE
	vp.use_hdr_2d = true
	vp.disable_3d = true
	vp.transparent_bg = false
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var rect := ColorRect.new()
	rect.size = Vector2(SIZE)
	var m := ShaderMaterial.new()
	m.shader = load(shader_path)
	for k in params:
		m.set_shader_parameter(k, params[k])
	rect.material = m
	vp.add_child(rect)
	add_child(vp)
	mats[pass_name] = m
	return vp.get_texture()


func _copy_material(tex: Texture2D) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = load("res://shaders/post_copy.gdshader")
	m.set_shader_parameter("src", tex)
	return m
