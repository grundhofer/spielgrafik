extends Node3D
## Katalogeintrag einbit-3d: 1-Bit-Dithering auf der gemeinsamen 3D-Grundlage (shared/3d).
##
## Alle glTF-Materialien werden nach Namen durch einen Grauwert ersetzt (shaders/onebit_surface.gdshader),
## Godot beleuchtet die Szene ganz normal, und die Nachbearbeitung (shaders/onebit_post.gdshader) setzt
## jedes Pixel der 640×360-Szene auf Papier oder Tinte: Bayer-Matrix auf Oberflächen, Blue Noise in der Luft,
## Linien an Silhouetten, Knicken und Materialwechseln. Himmel, Dunst, Lichtkegel, Lichthöfe und Rauch
## rechnet die Nachbearbeitung analytisch aus Uniforms, die dieses Skript je Bild setzt.
##
## Kamera: 0–CUT_T die Hauptkamera aus shared/3d (fest), dann Schnitt auf eine Stativkamera am Kai, die den
## Dachs mit einem reinen Schwenk (nur Gieren) verfolgt. Die Dither-Koordinaten hängen an der Blickrichtung
## einer Referenzkamera je Einstellung (Ruhelage); so läuft das Muster beim Schwenken mit der Welt mit.
## Alles hängt an der aufsummierten Zeit t und an festen Seeds (deterministische Aufnahme).
##
## Schalter nach "--": --screen-dither (Muster fest im Bildschirm), --bayer, --bluenoise, --nodither, --gray,
## --no-lines, --no-ids, --freeze (nur die Kamera bewegt sich), --mask (nur der Dachs, weiß auf Schwarz),
## --no-parcel (Paket ausblenden, um seine Sichtbarkeit zu messen),
## --measure (Fuß- und Kopfpunkte je Bild ausgeben), --shot2 (gleich in Einstellung 2 beginnen).

# --- Dachs (Werte aus shared/3d/badger_notes.md) -----------------------------------------------
const WALK_SPEED := 0.367        # m/s bei speed_scale 1, dann rutschen die Füße nicht
const WALK_RATE := 2.0
const TURN_T0 := 2.55            # biegt in den letzten Schritten zur Kamera ab (Drehen im Laufen)
const TURN_T1 := 3.6
const TURN_DEG := -72.0
const MAX_TURN_STEP := deg_to_rad(3.0)
const BRAKE_T := 3.46            # Bremsen; bei IDLE_T ist der rechte Fuß gerade oben neben dem linken
const BRAKE_TIME := 0.4          # (Durchgangsphase) und schwingt noch langsam vor
const IDLE_T := 3.73             # Ende des Laufs, ab hier Überblenden (Walk läuft darin mit der Bremskurve aus)
const IDLE_BLEND := 0.35         # Überblenden Walk -> Idle; der Schwungfuß setzt erst an dessen Ende auf
const PIN_TIME := 0.5            # so lange nach IDLE_T bleibt der Standfuß beim Überblenden festgehalten
const WAVE_T := 4.25
const WAVE_LEN := 1.5

# --- Kamera ------------------------------------------------------------------------------------
const CUT_T := 2.4
const FOLLOW := 0.5              # Anteil, mit dem der Schwenk dem Dachs folgt (Rest: er läuft ins Bild)
const VIEW := Vector2(640.0, 360.0)
const FEET_PX := Vector2(150.0, 328.0)   # Füße des Dachses in Einstellung 2 (Ruhelage)
@export var shot2_pos := Vector3(-3.55, 0.9, 4.7)
@export var shot2_fov := 46.0

# --- Umgebung ----------------------------------------------------------------------------------
const SUN_TRAVEL := Vector3(-0.82, -0.52, -0.22)   # Abendlicht von rechts vorn oben (Westen liegt rechts)
const KEY_TRAVEL := Vector3(-0.4, -0.5, -0.75)   # Figurenlicht von rechts vorn oben
const BEAM_PERIOD := 8.0
const BEAM_POSTER_T := 5.0
const BEAM_POSTER_DIR := Vector2(-0.82, 0.57)   # (x, z): quer über den Himmel nach links vorn
const BEAM_TILT := deg_to_rad(4.0)
const SMOKE_PUFFS := 8
const SMOKE_LIFE := 4.4
const SEED := 20261011

const SURFACE := preload("res://shaders/onebit_surface.gdshader")

## Grauwert (linear), Material-ID, Eigenleuchten. Die ID (0..15) steht im Blaukanal: Hafen 1–9, Wasser 15,
## Figur 10–14 (daran erkennt die Nachbearbeitung den Dachs). Gelände (Fels, Sand, Gras) teilt eine ID, sonst
## folgen Materiallinien den Dreieckskanten; dunkle Teile ohne gemeinsame Kante teilen sich ebenfalls IDs.
const VALUES := {
	"Stone": [0.55, 1, 0.0],
	"StoneDark": [0.3, 2, 0.0],
	"Roof": [0.08, 2, 0.0],
	"Wood": [0.3, 3, 0.0],
	"WoodDark": [0.08, 4, 0.0],
	"Metal": [0.05, 4, 0.0],
	"WhitePaint": [0.85, 5, 0.0],
	"RedPaint": [0.1, 6, 0.0],
	"Rope": [0.55, 7, 0.0],
	"Rock": [0.2, 8, 0.0],
	"Sand": [0.45, 8, 0.0],
	"Grass": [0.26, 8, 0.0],
	"Glass": [1.0, 9, 2.5],
}
const BADGER_VALUES := {
	"FurDark": [0.04, 10, 0.0],
	"Nose": [0.02, 10, 0.0],
	"Eye": [0.0, 10, 0.0],
	"FurLight": [0.95, 11, 0.0],
	"Shirt": [0.9, 11, 0.0],
	"Cap": [0.1, 12, 0.0],
	"Vest": [0.1, 12, 0.0],
	"Scarf": [0.14, 13, 0.0],
	"Satchel": [0.22, 14, 0.0],
	"Parcel": [0.65, 14, 0.0],
	"Brass": [0.8, 14, 0.0],
}

@export var water_material: ShaderMaterial

const STEP := 1.0 / 30.0

var frame := 0
var t := 0.0
var ta := 0.0                    # Zeit der Animationen (steht bei --freeze)
var walker: Walker               # der sichtbare Dachs
var boats := {}
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var smoke_jitter: Array[Vector3] = []
var post_mat: ShaderMaterial
var opts := {}
var shot := 0
# Einstellung 2: Bahn des Dachses je Bild, vorab mit einem unsichtbaren zweiten Dachs gerechnet
var plan_path := PackedVector3Array()
var shot2_f := 0.0
var shot2_pitch := 0.0
var shot2_yaw_end := 0.0
var cam_main: Transform3D
var fov_main := 42.0

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var camera: Camera3D = $Camera
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		opts[a.trim_prefix("--")] = true
	cam_main = camera.global_transform
	fov_main = camera.fov
	var sun := $Sun as DirectionalLight3D
	sun.global_transform = Transform3D.IDENTITY.looking_at(SUN_TRAVEL, Vector3.UP)
	($FigureKey as DirectionalLight3D).global_transform = Transform3D.IDENTITY.looking_at(KEY_TRAVEL, Vector3.UP)

	_apply_values(harbor, VALUES)
	_apply_values(badger, BADGER_VALUES)
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.layers = 2   # nur Figurenlicht, keine Sonne (Schatten wirft er trotzdem)
	_attach_to_empties()

	var n := replace_material(harbor, "Water", water_material)
	assert(n == 1, "Material Water nicht gefunden")
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0

	lantern_mat = _own_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _own_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	walker = Walker.new(badger)

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	beam_yaw0 = atan2(-BEAM_POSTER_DIR.x, -BEAM_POSTER_DIR.y) - TAU * BEAM_POSTER_T / BEAM_PERIOD
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in SMOKE_PUFFS:
		smoke_jitter.append(Vector3(rng.randf_range(-0.25, 0.25), rng.randf_range(0.8, 1.2), rng.randf_range(-0.06, 0.06)))

	# Nachbearbeitung je Renderer: Normalen-/Rauheitspuffer gibt es nur in Forward+
	var post := $Camera/Post as MeshInstance3D
	post_mat = post.get_surface_override_material(0) as ShaderMaterial
	var fplus := RenderingServer.get_current_rendering_method() == "forward_plus"
	post_mat.shader = load("res://shaders/onebit_post.gdshader" if fplus else "res://shaders/onebit_post_depth.gdshader")
	post_mat.set_shader_parameter("blue_noise", load("res://textures/bluenoise64.png"))
	_apply_switches()

	_plan_shot2()
	if opts.has("no-parcel"):
		(badger.find_child("Parcel", true, false) as Node3D).visible = false
	if opts.has("mask"):
		_mask_mode()
	if opts.has("measure"):
		RenderingServer.frame_pre_draw.connect(_measure)
	_update(0.0)


## Feste Schritte von 1/30 s je Bild statt des delta von Godot: Auch mit --fixed-fps 30 liefert Godot in den
## ersten Bildern ungleiche Werte (0,025 / 0,033 / 0,042 / 0,029 …). Der Vorlauf der Kamerabahn (_plan_shot2)
## rechnet mit denselben Schritten; nur so laufen sichtbarer Dachs und Vorlauf Bild für Bild gleich.
func _process(_delta: float) -> void:
	frame += 1
	t = frame * STEP
	if not opts.has("freeze"):
		ta += STEP
	_update(STEP)


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("onebit_time", ta)
	if not opts.has("freeze"):
		walker.step(t, delta)
	_update_camera()

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.4) * sin(TAU * ta / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * ta / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * ta / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	# Laterne flackert: Glas, Licht, Lichthof und Glitzern im Wasser gemeinsam
	var f := 0.8 + 0.2 * lantern_noise.get_noise_1d(ta * 7.0) + 0.08 * lantern_noise.get_noise_1d(ta * 31.0 + 50.0)
	lantern_omni.light_energy = 1.6 * f
	lantern_mat.set_shader_parameter("emission", 2.5 * f)

	# Leuchtfeuer: Strahlrichtung dreht sich, Lampe blitzt, wenn der Strahl zur Kamera zeigt
	var lamp_pos := (harbor.find_child("LighthouseLight", true, false) as Node3D).global_position
	var yaw := beam_yaw0 + TAU * ta / BEAM_PERIOD
	var beam_dir := Vector3(-sin(yaw) * cos(BEAM_TILT), -sin(BEAM_TILT), -cos(yaw) * cos(BEAM_TILT))
	var to_cam := camera.global_position - lamp_pos
	var facing := pow(maxf(Vector2(beam_dir.x, beam_dir.z).normalized().dot(Vector2(to_cam.x, to_cam.z).normalized()), 0.0), 16.0)
	lamp_mat.set_shader_parameter("emission", 2.5 + 6.0 * facing)
	lamp_omni.light_energy = 2.0 + 3.0 * facing
	post_mat.set_shader_parameter("beam_origin", lamp_pos)
	post_mat.set_shader_parameter("beam_dir", beam_dir)

	var lantern_pos := (harbor.find_child("LanternLight", true, false) as Node3D).global_position
	var window_pos := (harbor.find_child("CottageWindow", true, false) as Node3D).global_position + Vector3(0.0, 0.0, 0.35)
	post_mat.set_shader_parameter("halo", [
		Vector4(lantern_pos.x, lantern_pos.y, lantern_pos.z, 0.5),
		Vector4(window_pos.x, window_pos.y, window_pos.z, 0.55),
		Vector4(lamp_pos.x, lamp_pos.y, lamp_pos.z, 0.9 + 1.4 * facing)])
	post_mat.set_shader_parameter("halo_power", PackedFloat32Array([0.45 * f, 0.3, 0.45 + 1.2 * facing]))
	water_material.set_shader_parameter("glint_pos", [
		Vector4(lantern_pos.x, lantern_pos.y, lantern_pos.z, 1.6 * f),
		Vector4(lamp_pos.x, lamp_pos.y, lamp_pos.z, 2.5 + 3.0 * facing),
		Vector4(window_pos.x, window_pos.y, window_pos.z, 1.0)])

	_update_smoke()


# --- Einstellung 2: Stativkamera, die dem Dachs mit reinem Gieren folgt --------------------------
## Ein unsichtbarer zweiter Dachs läuft vorab dieselben Schritte (Walker.step mit 30 Bildern/s) und liefert
## die Bahn je Bild. Die Kamera folgt dieser Bahn, nicht der sichtbaren Figur: So steht die Ruhelage (und damit
## die Referenz des Dithermusters) vor dem Schwenk fest, und auch --freeze zeigt denselben Schwenk.
func _plan_shot2() -> void:
	var ghost := (load("res://models/badger.glb") as PackedScene).instantiate() as Node3D
	ghost.visible = false
	add_child(ghost)
	ghost.transform = badger.transform
	var w := Walker.new(ghost)
	plan_path.append(ghost.position)
	for i in range(1, 201):
		w.step(i * STEP, STEP)
		plan_path.append(ghost.position)
	ghost.queue_free()
	var p := plan_path[plan_path.size() - 1]
	shot2_f = (VIEW.y * 0.5) / tan(deg_to_rad(shot2_fov) * 0.5)
	# Neigung und Gieren so, dass die Füße am Ende auf FEET_PX liegen
	var pitch := 0.0
	var yaw := 0.0
	for i in 40:
		yaw = _aim_yaw(pitch, p, FEET_PX.x)
		var s := _project(Basis.from_euler(Vector3(pitch, yaw, 0.0)), p)
		pitch -= atan((s.y - FEET_PX.y) / shot2_f) * 0.9
	shot2_pitch = pitch
	shot2_yaw_end = _aim_yaw(pitch, p, FEET_PX.x)
	print("Einstellung 2: Endpunkt (%.3f | %.3f), Neigung %.2f°, Gieren am Ende %.2f°, f %.1f px" % [
		p.x, p.z, rad_to_deg(shot2_pitch), rad_to_deg(shot2_yaw_end), shot2_f])


## Bahnpunkt zur Zeit t (linear zwischen den vorab gerechneten Bildern)
func _plan_at(time: float) -> Vector3:
	var x := clampf(time * 30.0, 0.0, float(plan_path.size() - 1))
	var i := mini(int(floor(x)), plan_path.size() - 2)
	return plan_path[i].lerp(plan_path[i + 1], x - float(i))


func _project(b: Basis, p: Vector3) -> Vector2:
	var d := b.inverse() * (p - shot2_pos)
	return Vector2(VIEW.x * 0.5 + shot2_f * d.x / -d.z, VIEW.y * 0.5 - shot2_f * d.y / -d.z)


func _aim_yaw(pitch: float, p: Vector3, u: float) -> float:
	var yaw := atan2(-(p.x - shot2_pos.x), -(p.z - shot2_pos.z))
	for i in 30:
		var s := _project(Basis.from_euler(Vector3(pitch, yaw, 0.0)), p)
		yaw -= atan((s.x - u) / shot2_f) * 0.95
	return yaw


func _update_camera() -> void:
	var want := 1 if (t >= CUT_T or opts.has("shot2")) else 0
	if want == 0:
		if shot != 0 or t == 0.0:
			camera.global_transform = cam_main
			camera.fov = fov_main
			_set_reference(cam_main.basis, fov_main)
		shot = 0
		return
	var yaw := shot2_yaw_end + FOLLOW * (_aim_yaw(shot2_pitch, _plan_at(t), FEET_PX.x) - shot2_yaw_end)
	if opts.has("static-cam"):
		yaw = shot2_yaw_end
	camera.global_transform = Transform3D(Basis.from_euler(Vector3(shot2_pitch, yaw, 0.0)), shot2_pos)
	camera.fov = shot2_fov
	if shot != 1:
		_set_reference(Basis.from_euler(Vector3(shot2_pitch, shot2_yaw_end, 0.0)), shot2_fov)
		print("Einstellung 2 ab %.3f s: Gieren beim Schnitt %.2f°, Schwenk bis zur Ruhelage %.2f°" % [
			t, rad_to_deg(yaw), rad_to_deg(yaw - shot2_yaw_end)])
	shot = 1


## Referenzkamera für die Dither-Koordinaten: In dieser Lage fällt das Muster genau auf das Pixelraster.
func _set_reference(b: Basis, fov: float) -> void:
	post_mat.set_shader_parameter("ref_inv", b.inverse())
	post_mat.set_shader_parameter("ref_focal", (VIEW.y * 0.5) / tan(deg_to_rad(fov) * 0.5))


# --- Rauch: Bällchen, die die Nachbearbeitung als Dichte entlang des Sehstrahls rechnet ----------
func _update_smoke() -> void:
	var anchor := (harbor.find_child("ChimneySmoke", true, false) as Node3D).global_position
	var centers: Array[Vector4] = []
	var alphas := PackedFloat32Array()
	for i in SMOKE_PUFFS:
		var j := smoke_jitter[i]
		var age := fposmod(ta / SMOKE_LIFE + float(i) / SMOKE_PUFFS + j.z, 1.0)
		var rise := 1.0 - pow(1.0 - age, 1.5)
		var c := anchor + Vector3(2.2 * age * age + j.x * age, 0.1 + 3.2 * rise, 0.0)
		var r := (0.22 + 0.62 * rise) * j.y
		centers.append(Vector4(c.x, c.y, c.z, r))
		alphas.append(0.9 * smoothstep(0.0, 0.1, age) * (1.0 - smoothstep(0.55, 1.0, age)))
	post_mat.set_shader_parameter("puffs", centers)
	post_mat.set_shader_parameter("puff_alpha", alphas)


# --- Materialien -------------------------------------------------------------------------------
func _surface_material(entry: Array) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SURFACE
	m.set_shader_parameter("value", entry[0])
	m.set_shader_parameter("material_id", entry[1])
	m.set_shader_parameter("emission", entry[2])
	return m


func _apply_values(root: Node, values: Dictionary) -> void:
	var cache := {}
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
			if src == null:
				push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
				continue
			var key := src.resource_name
			if key == "Water":
				continue
			if not values.has(key):
				push_error("Material %s fehlt in der Grauwerttabelle" % key)
				continue
			if not cache.has(key):
				cache[key] = _surface_material(values[key])
			mi.set_surface_override_material(i, cache[key])


func _own_material(mi: MeshInstance3D) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


static func replace_material(root: Node, mat_name: String, mat: Material) -> int:
	var count := 0
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				mi.set_surface_override_material(i, mat)
				count += 1
	return count


# --- Vergleichsschalter ------------------------------------------------------------------------
func _apply_switches() -> void:
	if opts.has("screen-dither"):
		post_mat.set_shader_parameter("dither_mode", 0)
	for pair in [["bayer", 1], ["bluenoise", 2], ["nodither", 3], ["gray", 4], ["ids", 5]]:
		if opts.has(pair[0]):
			post_mat.set_shader_parameter("pattern_mode", pair[1])
	if opts.has("gray") or opts.has("ids"):
		(($Palette/Rect as ColorRect).material as ShaderMaterial).set_shader_parameter("gray_preview", 1.0)
	if opts.has("no-lines"):
		post_mat.set_shader_parameter("lines", 0.0)
	if opts.has("no-ids"):
		post_mat.set_shader_parameter("id_lines", 0.0)
	if opts.has("no-figure-outline"):
		post_mat.set_shader_parameter("figure_outline", 0.0)


# --- Messen ------------------------------------------------------------------------------------
# --mask: nur der Dachs, weiß und unbeleuchtet auf Schwarz (Silhouette für die Bildmessung)
# --measure: je Bild Ferse und Zehe beider Füße sowie Kopf in Welt- und Bildkoordinaten ausgeben
func _mask_mode() -> void:
	harbor.visible = false
	$Camera/Post.visible = false
	$UI.visible = false
	$Palette.visible = false
	var env := ($WorldEnvironment as WorldEnvironment).environment
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color.BLACK
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			mi.set_surface_override_material(i, white)


func _measure() -> void:
	var pp := _plan_at(t)
	var line := "M %.4f shot %d rot %.2f %.4f %.4f plan %.4f %.4f 0 0 0" % [t, shot, rad_to_deg(badger.rotation.y),
		badger.position.x, badger.position.z, pp.x, pp.z]
	for k in ["heel.L", "toe.L", "heel.R", "toe.R", "head"]:
		var w := walker.probe_world(k)
		var sp := camera.unproject_position(w)
		line += " %s %.4f %.4f %.4f %.2f %.2f" % [k, w.x, w.y, w.z, sp.x, sp.y]
	print(line)


# --- Laufen ------------------------------------------------------------------------------------
## Steuert einen Dachs (Instanz von badger.glb): Walk mit Vorschub, Drehen zur Kamera im Laufen, Bremsen,
## Überblenden auf Idle mit festgehaltenem Standfuß, Winken. Der AnimationPlayer läuft von Hand (advance):
## erst Pose, dann Vorschub, dann Drehung um den Standfuß. Gleiche Schritte ergeben dieselbe Bahn; main.gd
## nutzt das für den unsichtbaren Vorlauf (Kamerabahn) und den sichtbaren Dachs.
class Walker:
	var node: Node3D
	var player: AnimationPlayer
	var skel: Skeleton3D
	var probe := {}              # Name -> [Knochenindex, Punkt in Ruhelage des Knochens]
	var phase := 0               # 0 Walk, 1 Idle (anfangs Überblenden), 2 Wave, 3 Idle
	var pin_side := "L"
	var walk_time := 0.0         # Zeit in Walk, läuft beim Überblenden mit der Bremskurve weiter bis zum Stillstand
	var walk_tracks := []        # [Spur, Knochen, Spurtyp] von Walk, zum Abtasten beim Überblenden

	func _init(n: Node3D) -> void:
		node = n
		player = n.get_node("AnimationPlayer") as AnimationPlayer
		skel = n.find_child("Skeleton3D", true, false) as Skeleton3D
		for a in ["Idle", "Walk"]:
			player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
		player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
		player.play("Walk")
		player.speed_scale = WALK_RATE
		# Punkte in Ruhepose (aus badger_notes.md): Ferse unter dem Fußknochen, Zehe an seiner Spitze,
		# beide 3 mm über dem Boden; Kopf = Mützendeckel
		var pts := {
			"heel.L": ["foot.L", Vector3(-0.02, 0.003, -0.125)], "toe.L": ["foot.L", Vector3(0.13, 0.003, -0.125)],
			"heel.R": ["foot.R", Vector3(-0.02, 0.003, 0.125)], "toe.R": ["foot.R", Vector3(0.13, 0.003, 0.125)],
			"head": ["head", Vector3(0.0, 1.011, 0.0)],
		}
		for k in pts:
			var bi := skel.find_bone(pts[k][0])
			probe[k] = [bi, skel.get_bone_global_rest(bi).affine_inverse() * (pts[k][1] as Vector3)]
		var walk := player.get_animation("Walk")
		for i in walk.get_track_count():
			var bone := skel.find_bone(walk.track_get_path(i).get_concatenated_subnames())
			if bone >= 0:
				walk_tracks.append([i, bone, walk.track_get_type(i)])

	func probe_world(k: String) -> Vector3:
		return skel.global_transform * skel.get_bone_global_pose(probe[k][0]) * (probe[k][1] as Vector3)

	func step(t: float, delta: float) -> void:
		if phase == 0:
			var rate := WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
			player.speed_scale = rate
			player.advance(delta)
			var th := node.rotation.y
			node.position += Vector3(cos(th), 0.0, -sin(th)) * WALK_SPEED * rate * delta
			# Drehen nur, solange genau ein Fuß am Boden steht, und um dessen Bodenpunkt.
			var th_goal := deg_to_rad(TURN_DEG) * smoothstep(TURN_T0, TURN_T1, t)
			var pivot: Variant = stance_point()
			var dth := clampf(th_goal - node.rotation.y, -MAX_TURN_STEP, MAX_TURN_STEP)
			if absf(dth) > 0.0 and pivot != null:
				var pv: Vector3 = pivot
				pv.y = 0.0
				node.position = pv + (node.position - pv).rotated(Vector3.UP, dth)
				node.rotation.y += dth
			if t >= IDLE_T:
				# Überblenden selbst rechnen statt player.play("Idle", IDLE_BLEND): Beim Überblenden des
				# AnimationPlayer läuft Walk mit speed_scale 1 weiter; dann setzte der Schwungfuß vor dem Ende auf
				# und rutschte. Hier läuft Walk nur noch mit der Bremskurve aus (Stillstand bei BRAKE_T +
				# BRAKE_TIME), und der Schwungfuß sinkt erst am Ende des Überblendens auf den Boden.
				phase = 1
				walk_time = player.current_animation_position
				player.speed_scale = 1.0
				player.play("Idle")
				pin_side = lowest_foot()
			return
		if phase == 1 and t < IDLE_T + PIN_TIME:
			# Überblenden Walk -> Idle: den Standfuß am Boden festhalten (Wurzel gegen seine Bewegung schieben)
			var before := foot_ground(pin_side)
			player.advance(delta)
			var w := clampf((t - IDLE_T) / IDLE_BLEND, 0.0, 1.0)
			if w < 1.0:
				walk_time += WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t)) * delta
				blend_walk(walk_time, blend_weight(w))
			var after := foot_ground(pin_side)
			node.position += Vector3(before.x - after.x, 0.0, before.z - after.z)
			return
		if phase == 1 and t >= WAVE_T:
			phase = 2
			player.play("Wave", 0.25)
		elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
			phase = 3
			player.play("Idle", 0.3)
		player.advance(delta)

	## Mischt Walk zur Zeit time (Spuren direkt abgetastet) mit der gerade gesetzten Idle-Pose (w = 0: Walk,
	## 1: Idle). Knochen ohne Spur in Walk bleiben, wie Idle sie setzt.
	func blend_walk(time: float, w: float) -> void:
		var walk := player.get_animation("Walk")
		time = fposmod(time, walk.length)
		for tr: Array in walk_tracks:
			var i: int = tr[0]
			var b: int = tr[1]
			match tr[2]:
				Animation.TYPE_POSITION_3D:
					skel.set_bone_pose_position(b, walk.position_track_interpolate(i, time).lerp(skel.get_bone_pose_position(b), w))
				Animation.TYPE_ROTATION_3D:
					skel.set_bone_pose_rotation(b, walk.rotation_track_interpolate(i, time).slerp(skel.get_bone_pose_rotation(b), w))
				Animation.TYPE_SCALE_3D:
					skel.set_bone_pose_scale(b, walk.scale_track_interpolate(i, time).lerp(skel.get_bone_pose_scale(b), w))

	## Verlauf des Überblendens: langsam los, gleichmäßig, weich auf (smoothstep)
	func blend_weight(u: float) -> float:
		return u * u * (3.0 - 2.0 * u)

	func lowest_foot() -> String:
		var l := minf(probe_world("heel.L").y, probe_world("toe.L").y)
		var r := minf(probe_world("heel.R").y, probe_world("toe.R").y)
		return "L" if l <= r else "R"

	func foot_ground(side: String) -> Vector3:
		return (probe_world("heel." + side) + probe_world("toe." + side)) * 0.5

	## Bodenpunkt des Standfußes: Mittel seiner Punkte unter 1 cm; null, wenn beide oder keiner am Boden.
	func stance_point() -> Variant:
		var down := {}
		for side in ["L", "R"]:
			var pts: Array[Vector3] = []
			for k in ["heel.", "toe."]:
				var w := probe_world(k + side)
				if w.y < 0.01:
					pts.append(w)
			if not pts.is_empty():
				var m := Vector3.ZERO
				for w in pts:
					m += w
				down[side] = m / pts.size()
		if down.size() != 1:
			return null
		return down.values()[0]
