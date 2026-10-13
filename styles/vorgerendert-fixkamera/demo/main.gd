extends Node3D
## Vorgerenderte Hintergründe, feste Kamera (Katalogeintrag vorgerendert-fixkamera).
##
## Zwei feste Einstellungen wie in Rollenspielen und Survival-Horror-Spielen 1996–2001:
## 0–CUT_T "totale" (erhöht, schräg), danach harter Schnitt auf "nah" (niedrig vor der Figur).
## Je Einstellung: Renderbild, Tiefenbild, Bildfolge-Overlay und Laternen-Lichtebene aus Blender
## (bg/<shot>/), die Kamera bekommt exakt die Werte des Renders. Davor läuft die Low-Poly-Figur.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (reproduzierbare Aufnahme).
##
## Schalter (nach "--"): --no-depth (Figur immer vorn), --no-anim (nur ruhendes Bild), --key (Hintergrund
## magenta, ohne Oberfläche und Schatten: Messlauf für scripts/probe.py), --no-ui, --feet-log (Fußknochen je
## Bild als Welt- und Bildschirmkoordinaten ausgeben), --per-pixel (Figur je Pixel statt je Eckpunkt
## schattieren, Vergleich zu Gouraud), --shot=<name> (nur diese Einstellung).

const WALK_SPEED := 0.367        # m/s bei speed_scale 1 (shared/3d/badger_notes.md)
const WALK_RATE := 2.0           # Abspieltempo von Walk -> 0,73 m/s
const BRAKE_TIME := 0.45         # Tempo und Animation sinken gemeinsam auf 0
const CORNER_R := 0.8            # Radius der Kurve am Knick (m)
const CUT_T := 2.1               # harter Schnitt totale -> nah
const TURN_TIME := 0.5           # Drehung zur Kamera nach dem Anhalten
const WAVE_LEN := 1.5
const SEED := 20261010
const GOURAUD := preload("res://shaders/gouraud.gdshader")

var t := 0.0
var shots := {}                  # Name -> {meta, base, depth, lantern, anim}
var shot_order: Array[String] = ["totale", "nah"]
var cur := ""
var flags := {}
var path: Array[Vector2] = []    # Punkte der Bahn (x, z) mit gerundetem Knick, fein abgetastet
var path_s: Array[float] = []    # Bogenlänge je Punkt
var path_len := 0.0
var s_walk := 0.0                # zurückgelegter Weg
var brake_t := 0.0
var stop_t := 0.0
var wave_t := 0.0
var phase := 0                   # 0 Walk, 1 Idle, 2 Wave, 3 Idle
var face_cam_yaw := 0.0
var stop_yaw := 0.0
var lantern_noise := FastNoiseLite.new()
var lantern_k := 1.0
var foot_bones := []
var figure_mats: Array[ShaderMaterial] = []

@onready var camera: Camera3D = $Camera
@onready var bg_mat: ShaderMaterial = ($Camera/Background as MeshInstance3D).get_surface_override_material(0)
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var skel: Skeleton3D = $Badger.find_child("Skeleton3D", true, false)
@onready var blob: MeshInstance3D = $Blob
@onready var ui: Control = $UI/Box


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shot="):
			flags["shot"] = a.substr(7)
		else:
			flags[a.trim_prefix("--")] = true
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://shots.json"))
	_build_path(data["path"])
	for name in shot_order:
		var dir := "res://bg/%s/" % name
		shots[name] = {
			"meta": JSON.parse_string(FileAccess.get_file_as_string(dir + "meta.json")),
			"base": load(dir + "base.png"), "depth": load(dir + "depth.png"),
			"lantern": load(dir + "lantern.png"), "anim": load(dir + "anim.png"),
		}
	bg_mat.set_shader_parameter("use_depth", not flags.has("no-depth"))
	bg_mat.set_shader_parameter("use_anim", not flags.has("no-anim"))
	bg_mat.set_shader_parameter("key_mode", flags.has("key"))
	if flags.has("key"):
		blob.visible = false
	ui.visible = not (flags.has("key") or flags.has("no-ui"))

	# Figur: Gouraud-Schattierung je Eckpunkt (shaders/gouraud.gdshader), matt, wie Figuren der Zeit
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			var m := ShaderMaterial.new()
			m.shader = GOURAUD
			m.set_shader_parameter("albedo", Vector3(src.albedo_color.srgb_to_linear().r,
				src.albedo_color.srgb_to_linear().g, src.albedo_color.srgb_to_linear().b))
			m.set_shader_parameter("per_pixel", 1.0 if flags.has("per-pixel") else 0.0)
			mi.set_surface_override_material(i, m)
			figure_mats.append(m)
	# Die Lichtknoten liefern nur noch die Werte für den Shader (Hintergrund ist unbeleuchtet)
	for n in [$Dusk, $Fill, $WindowSide, $WindowFront, $Lantern]:
		(n as Light3D).visible = false

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.play("Walk")
	player.speed_scale = WALK_RATE

	# Anhalten genau am Ende der Bahn: Weg = v0 * brake_t + v0 * BRAKE_TIME / 2 (smoothstep-Mittel 1/2)
	var v0 := WALK_SPEED * WALK_RATE
	brake_t = path_len / v0 - BRAKE_TIME * 0.5
	stop_t = brake_t + BRAKE_TIME
	wave_t = stop_t + 0.1 + TURN_TIME + 0.05

	# Restlicht von hinten rechts, wie DuskSun im Render (Blender-Richtung (-0,25 | -1 | -0,06))
	var dusk_dir := Vector3(-0.25, -0.06, 1.0).normalized()
	($Dusk as Node3D).basis = Basis.looking_at(dusk_dir, Vector3.UP)

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	for b in ["foot.L", "foot.R"]:
		# Messpunkt Sohlenmitte: 7 cm vor und 6,2 cm unter dem Fußgelenk (Ruhepose, Skelettraum)
		var bi := skel.find_bone(b)
		var rest := skel.get_bone_global_rest(bi)
		foot_bones.append([bi, rest.affine_inverse() * (rest.origin + Vector3(0.07, -0.062, 0.0))])

	_set_shot(flags.get("shot", "totale"))
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	var want: String = flags.get("shot", "totale" if t < CUT_T else "nah")
	if want != cur:
		_set_shot(want)
	_update_badger(delta)

	# Bildfolge: 15 Bilder/s (jedes Bild zwei Takte lang bei 30 fps), Schleife über die ganze Länge
	var meta: Dictionary = shots[cur]["meta"]
	var n := int(meta["anim"]["frames"])
	var frame := int(floor(t * float(meta["anim"]["fps"]) + 0.001)) % n
	bg_mat.set_shader_parameter("anim_frame", frame)

	# Laterne flackert: Lichtebene des Renders und Punktlicht für die Figur gemeinsam
	var f := 0.8 + 0.4 * lantern_noise.get_noise_1d(t * 6.0) + 0.12 * lantern_noise.get_noise_1d(t * 23.0 + 50.0)
	lantern_k = clampf(f, 0.35, 1.25)
	bg_mat.set_shader_parameter("lantern_k", lantern_k)
	($Lantern as OmniLight3D).light_energy = 1.6 * lantern_k
	_update_figure_light()

	ui.set("t", t)
	ui.set("shot", cur)
	ui.queue_redraw()
	if flags.has("feet-log"):
		_log_feet()


func _set_shot(name: String) -> void:
	cur = name
	var sh: Dictionary = shots[name]
	var cam: Dictionary = sh["meta"]["camera"]
	var c: Array = cam["basis_columns"]
	var o: Array = cam["origin"]
	camera.transform = Transform3D(
		Basis(Vector3(c[0][0], c[0][1], c[0][2]), Vector3(c[1][0], c[1][1], c[1][2]), Vector3(c[2][0], c[2][1], c[2][2])),
		Vector3(o[0], o[1], o[2]))
	camera.fov = float(cam["fov"])
	bg_mat.set_shader_parameter("base_tex", sh["base"])
	bg_mat.set_shader_parameter("depth_tex", sh["depth"])
	bg_mat.set_shader_parameter("lantern_tex", sh["lantern"])
	bg_mat.set_shader_parameter("anim_tex", sh["anim"])
	var r: Array = sh["meta"]["anim"]["rect"]
	bg_mat.set_shader_parameter("anim_rect", Vector4i(int(r[0]), int(r[1]), int(r[2]), int(r[3])))
	bg_mat.set_shader_parameter("anim_cols", int(sh["meta"]["anim"]["cols"]))
	bg_mat.set_shader_parameter("depth_range", float(sh["meta"]["depth_range"]))
	# Aufhelllicht leicht von oben aus Kamerarichtung
	var fwd := -camera.global_basis.z
	($Fill as Node3D).basis = Basis.looking_at((fwd + Vector3(0, -0.35, 0)).normalized(), Vector3.UP)
	# Blickrichtung zur Kamera der Nahaufnahme (für die Drehung nach dem Anhalten)
	var nah: Array = shots["nah"]["meta"]["camera"]["origin"]
	var end := path[path.size() - 1]
	var to_cam := Vector2(float(nah[0]) - end.x, float(nah[2]) - end.y)
	face_cam_yaw = atan2(-to_cam.y, to_cam.x)


# --- Licht der Figur aus den Lichtknoten (linear) -----------------------------------------------
func _lin(c: Color, e: float) -> Vector3:
	var l := c.srgb_to_linear()
	return Vector3(l.r, l.g, l.b) * e


func _update_figure_light() -> void:
	var env: Environment = ($WorldEnvironment as WorldEnvironment).environment
	var amb := _lin(env.ambient_light_color, env.ambient_light_energy)
	var dd := PackedVector3Array()
	var dc := PackedVector3Array()
	for n: DirectionalLight3D in [$Dusk, $Fill]:
		dd.append(-n.global_basis.z)
		dc.append(_lin(n.light_color, n.light_energy))
	var pp := PackedVector3Array()
	var pc := PackedVector3Array()
	var pr := PackedVector2Array()
	for n: OmniLight3D in [$WindowSide, $WindowFront, $Lantern]:
		pp.append(n.global_position)
		pc.append(_lin(n.light_color, n.light_energy))
		pr.append(Vector2(n.omni_range, n.omni_attenuation))
	for m in figure_mats:
		m.set_shader_parameter("ambient", amb)
		m.set_shader_parameter("dir_dir", dd)
		m.set_shader_parameter("dir_col", dc)
		m.set_shader_parameter("pt_pos", pp)
		m.set_shader_parameter("pt_col", pc)
		m.set_shader_parameter("pt_range", pr)


# --- Bahn: Polylinie mit gerundetem Knick ----------------------------------------------------
func _build_path(pts: Array) -> void:
	var p := []
	for q in pts:
		p.append(Vector2(float(q["x"]), float(q["z"])))
	var raw: Array[Vector2] = [p[0]]
	for i in range(1, p.size() - 1):
		var a: Vector2 = p[i - 1]
		var b: Vector2 = p[i]
		var c: Vector2 = p[i + 1]
		var d0 := (b - a).normalized()
		var d1 := (c - b).normalized()
		var ang := d0.angle_to(d1)
		var tl := CORNER_R * tan(absf(ang) * 0.5)
		var s0 := b - d0 * tl
		var s1 := b + d1 * tl
		# Kreisbogen von s0 nach s1
		var nrm := Vector2(-d0.y, d0.x) * signf(ang)
		var center := s0 + nrm * CORNER_R
		var a0 := (s0 - center).angle()
		var steps := 24
		for k in steps + 1:
			raw.append(center + Vector2.from_angle(a0 + ang * float(k) / steps) * CORNER_R)
		raw.append(s1)
	raw.append(p[p.size() - 1])
	# fein abtasten (5 cm)
	path = [raw[0]]
	path_s = [0.0]
	for i in range(1, raw.size()):
		var seg := raw[i] - raw[i - 1]
		var n := maxi(1, int(ceil(seg.length() / 0.05)))
		for k in range(1, n + 1):
			var q := raw[i - 1] + seg * float(k) / n
			path_s.append(path_s[path_s.size() - 1] + q.distance_to(path[path.size() - 1]))
			path.append(q)
	path_len = path_s[path_s.size() - 1]


func _path_at(s: float) -> Array:
	s = clampf(s, 0.0, path_len)
	var i := path_s.bsearch(s)
	i = clampi(i, 1, path.size() - 1)
	var u := (s - path_s[i - 1]) / maxf(path_s[i] - path_s[i - 1], 1e-6)
	var pos := path[i - 1].lerp(path[i], u)
	var dir := (path[i] - path[i - 1]).normalized()
	return [pos, dir]


# --- Figur -------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	if phase == 0:
		var rate := WALK_RATE * (1.0 - smoothstep(brake_t, stop_t, t))
		player.speed_scale = rate
		s_walk = minf(s_walk + WALK_SPEED * rate * delta, path_len)
		if t >= stop_t:
			phase = 1
			player.speed_scale = 1.0
			player.play("Idle", 0.3)
	elif phase == 1 and t >= wave_t:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= wave_t + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	var pd := _path_at(s_walk)
	var pos: Vector2 = pd[0]
	var dir: Vector2 = pd[1]
	badger.position = Vector3(pos.x, 0.01, pos.y)
	var walk_yaw := atan2(-dir.y, dir.x)     # Figur blickt bei 0 nach +X; Blick (cos, -sin) in (x, z)
	if t < stop_t:
		stop_yaw = walk_yaw
		badger.rotation.y = walk_yaw
	else:
		var u := smoothstep(stop_t + 0.1, stop_t + 0.1 + TURN_TIME, t)
		badger.rotation.y = lerp_angle(stop_yaw, face_cam_yaw, u)
	blob.position = Vector3(pos.x, 0.025, pos.y)
	blob.rotation.y = badger.rotation.y


func _log_feet() -> void:
	var parts := ["t=%.4f" % t, "shot=" + cur]
	for fb in foot_bones:
		var bi: int = fb[0]
		var w: Vector3 = skel.global_transform * skel.get_bone_global_pose(bi) * (fb[1] as Vector3)
		var sp := camera.unproject_position(w)
		parts.append("%s=(%.4f,%.4f,%.4f)|(%.2f,%.2f)" % [skel.get_bone_name(bi), w.x, w.y, w.z, sp.x, sp.y])
	print("FEET ", " ".join(parts))
