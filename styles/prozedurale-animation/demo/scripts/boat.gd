extends Node2D
## Boot als Feder-Dämpfer auf der Wellenfunktion: Hub und Stampfen folgen h(X, Z, t) an Bug, Mitte und Heck
## mit Trägheit (eigene Eigenfrequenz und Dämpfung). Spiegelbild und Wasserlinie kommen aus demselben h.
## Festmacher: Verlet-Seil vom Heck zum Steg-Pfosten.

const Waves := preload("res://scripts/waves.gd")
const Chain := preload("res://scripts/chain.gd")

var z_w := 10.0
var rest_y := 450.0
var len_px := 200.0
var omega_h := 3.0
var zeta_h := 0.5
var omega_p := 2.6
var zeta_p := 0.5
var y := 0.0
var vy := 0.0
var a := 0.0
var va := 0.0
var t := 0.0
var spr: Sprite2D
var refl: Sprite2D
var mat_b: ShaderMaterial
var mat_r: ShaderMaterial
var sprite_scale := 1.0
var cleat := Vector2()      # Klampe in Sprite-Koordinaten (bezogen auf Wasserlinie Mitte, vor Skalierung)
var rope: Chain
var rope_line: Line2D
var post := Vector2()


func setup(tex_path: String, info: Dictionary, x_center: float, y_waterline: float, width_px: float,
		post_pos: Vector2, oh: float, op: float) -> void:
	var tex: Texture2D = load(tex_path)
	var tw := float(tex.get_width())
	sprite_scale = width_px / tw
	len_px = width_px
	omega_h = oh
	omega_p = op
	rest_y = y_waterline
	z_w = Waves.z_of_y(y_waterline)
	position = Vector2(x_center, y_waterline)
	var wl: float = float(info["waterline_tex_y"])
	var shader: Shader = load("res://shaders/boat.gdshader")
	mat_r = ShaderMaterial.new()
	mat_r.shader = shader
	mat_r.set_shader_parameter("is_reflection", 1.0)
	mat_r.set_shader_parameter("boat_z", z_w)
	mat_b = ShaderMaterial.new()
	mat_b.shader = shader
	mat_b.set_shader_parameter("is_reflection", 0.0)
	mat_b.set_shader_parameter("boat_z", z_w)
	refl = Sprite2D.new()
	spr = Sprite2D.new()
	for s in [refl, spr]:
		s.texture = tex
		s.centered = false
		s.offset = Vector2(-tw * 0.5, -wl)
		s.texture_filter = CanvasItem.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
		add_child(s)
	refl.material = mat_r
	spr.material = mat_b
	refl.scale = Vector2(sprite_scale, -sprite_scale)
	spr.scale = Vector2(sprite_scale, sprite_scale)
	var c: Array = info["stern_cleat_tex"]
	cleat = Vector2(float(c[0]) - tw * 0.5, float(c[1]) - wl)
	post = post_pos
	rope = Chain.new()
	var start := _cleat_world()
	var n := 9
	rope.init_line(start, post - start, n, start.distance_to(post) * 1.07 / (n - 1))
	rope.inv_m[n - 1] = 0.0
	rope.min_fold = 0.0
	rope_line = Line2D.new()
	rope_line.width = 1.6
	rope_line.default_color = Color(0.20, 0.15, 0.12, 0.95)
	rope_line.antialiased = true
	add_child(rope_line)


func _cleat_world() -> Vector2:
	return position + Vector2(0, y) + (cleat * sprite_scale).rotated(a)


func step(tt: float, dt: float) -> void:
	t = tt
	var half := len_px * 0.42
	var xl := position.x - half
	var xr := position.x + half
	var dl := Waves.screen_dy(xl, z_w, tt)
	var dm := Waves.screen_dy(position.x, z_w, tt)
	var dr := Waves.screen_dy(xr, z_w, tt)
	var y_t := (dl + 2.0 * dm + dr) * 0.25
	var a_t := atan2(dr - dl, xr - xl)
	vy += (omega_h * omega_h * (y_t - y) - 2.0 * zeta_h * omega_h * vy) * dt
	y += vy * dt
	va += (omega_p * omega_p * (a_t - a) - 2.0 * zeta_p * omega_p * va) * dt
	a += va * dt
	# Seil
	var n := rope.size()
	var cw := _cleat_world()
	rope.pp[0] = rope.p[0]
	rope.p[0] = cw
	rope.integrate(dt, Vector2(0, 260), Vector2.ZERO, 0.0, 1.6)
	for it in 6:
		rope.p[0] = cw
		rope.p[n - 1] = post
		rope.solve(true)


func render() -> void:
	spr.position = Vector2(0, y)
	spr.rotation = a
	refl.position = Vector2(0, y)
	refl.rotation = -a
	for m in [mat_b, mat_r]:
		Waves.apply_uniforms(m, t)
	var pts := PackedVector2Array()
	for p in rope.p:
		pts.append(p - position)
	rope_line.points = pts
