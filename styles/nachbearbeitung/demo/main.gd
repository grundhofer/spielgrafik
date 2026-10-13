extends Node
## Nachbearbeitung & Look-Filter (Spielgrafik-Katalog, Eintrag nachbearbeitung).
##
## Dieselbe 3D-Hafenszene aus shared/3d, darüber sechs umschaltbare Looks, die jede Sekunde wechseln:
## Bloom, Filmkorn & Vignette, Farb-LUT, CRT, Halbton, Paletten-Reduktion. Zwei Stufen:
##   Welt-Stufe   (WorldView, world_post.gdshader) wirkt nur auf das 3D-Bild; Bloom kommt aus dem Glow
##                des Environments (HDR, vor dem Tonemapping), ist also auch Welt-Stufe.
##   Bildschirm-Stufe (Final, screen_post.gdshader) wirkt auf Welt und Oberfläche: CRT.
## Szene, Dachs und Umgebung sind in allen Looks gleich; nur die Nachbearbeitung wechselt.
##
## Kamera: 0–0,6 s die Totale aus shared/3d (Häuschen mit Fenster und Rauch, beide Boote, Kisten; Textbox
## noch ausgeblendet), dann harter Schnitt auf die Nahkamera, in die der Dachs hineinläuft.
##
## Alles hängt an der aufsummierten Zeit t und an festen Seeds (Aufnahme mit --fixed-fps ist reproduzierbar).
## Schalter nach "--": --look=N (Look festhalten, 0–5; -1 = ohne Nachbearbeitung), --t0=SEK (später
## beginnen, die Szene wird in 1/30-s-Schritten vorgespult), --no-badger, --no-ui, --no-label,
## --badger-mask (Dachs unbeleuchtet magenta ohne Schatten), --badger-ids (Mütze grün, Weste blau, Rest
## magenta, unbeleuchtet; für scripts/make_palette.py), --no-flicker (Laterne ruhig, für scripts/measure_lantern.py),
## --cam=total|nah (Einstellung festhalten) und --log-feet (Zehen beider Füße je Bild in Welt- und
## Bildkoordinaten ausgeben, für scripts/measure_badger.py).

# --- Looks -------------------------------------------------------------------------------------
const LOOK_TIME := 1.0           # s je Look; nach dem sechsten beginnt die Reihe von vorn
const LOOKS := [
	{"name": "Bloom", "detail": "Glow im HDR-Puffer · Schwelle 0,7 · 6 Stufen", "world": 0, "crt": false, "bloom": true},
	{"name": "Filmkorn & Vignette", "detail": "Korn je Bild · Halation · Staub · Vignette", "world": 2, "crt": false, "bloom": false},
	{"name": "Farb-LUT", "detail": "32³-LUT „Kalte Nacht“ · 1024×32 px", "world": 3, "crt": false, "bloom": false},
	{"name": "CRT", "detail": "240 Zeilen · Krümmung · Lochmaske", "world": 0, "crt": true, "bloom": false},
	{"name": "Halbton", "detail": "Punktraster 8 px · 45° · Fläche nach Helligkeit", "world": 4, "crt": false, "bloom": false},
	{"name": "Paletten-Reduktion", "detail": "16 Farben · Bayer 4×4 · 320×180", "world": 5, "crt": false, "bloom": false},
]

# --- Kamera (ausgerechnet mit scripts/frame_shot.py) -----------------------------------------------
const CAM_POS := Vector3(-0.3, 1.9, 7.6)
const CAM_TARGET := Vector3(3.0, 2.4, -20.0)
const CAM_FOV := 42.0
const TOTAL_POS := Vector3(-1.8, 3.4, 14.5)    # Hauptkamera aus shared/3d, unverändert
const TOTAL_ROT := Vector3(-3.0, 0.0, 0.0)     # rotation_degrees
const CUT_T := 0.6               # Schnitt Totale -> Nahkamera (Dachs ist dann noch links außerhalb)
const UI_FADE := 0.2             # Textbox blendet nach dem Schnitt ein

# --- Dachs (Werte aus shared/3d/badger_notes.md) ----------------------------------------------------
# Die Wurzel folgt dem aufgesetzten Fuß (Fuß-Sperre in _lock_feet): Laufen, Bremsen, Überblenden und Drehen
# verschieben die Figur so, dass die Zehe des Standfußes am Boden ortsfest bleibt.
const WALK_RATE := 2.4           # Abspieltempo von Walk (0,367 m/s × 2,4 = 0,88 m/s)
const START_X := -4.0            # außerhalb der Nahkamera links
const BRAKE_T := 2.45            # ab hier bremst er (Animationstempo auf 0, mit rechtem Fuß in der Luft)
const BRAKE_TIME := 0.4
const IDLE_BLEND := 0.42         # nach dem Stillstand: eingefrorene Laufpose -> Idle, rechter Fuß setzt auf
const SETTLE_SHIN := 0.6         # rechter Unterschenkel ist schon nach 60 % gestreckt: Fuß setzt fast senkrecht auf
const TURN_T := 2.62             # dreht sich auf dem linken Standfuß zur Kamera, solange der rechte in der Luft ist
const TURN_TIME := 0.56
const WAVE_T := 3.36             # Wave dauert 1,5 s
const WAVE_LEN := 1.5
const PLANT_Y := 0.025           # Zehe tiefer als 2,5 cm = Fuß am Boden (aufgesetzt liegt sie bei 2,0 cm)
const FIRM_Y := 0.021            # Zehe in beiden Bildern tiefer: Fuß steht fest, die Wurzel hängt an ihm
const WALK_SPEED := 0.367        # m/s bei speed_scale 1 (nur für Wechselbilder ohne festen Fuß)
const TOE := Vector3(0.0, 0.128, 0.0)   # Zehenspitze im Fußknochen

# --- Umgebung ------------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0         # s für eine Umdrehung des Leuchtfeuers
const BEAM_FACING_T := 0.7       # Strahl zeigt zur Kamera (Aufblitzen im Bloom-Look)
const SEED := 20261013
const SMOKE_PUFFS := 9           # Rauch wie in shared/3d (nur in der Totale im Bild)
const SMOKE_LIFE := 4.5
const LANTERN_DIM := Color(1.0, 0.42, 0.14)    # Lichtfarbe bei schwacher Flamme
const LANTERN_BRIGHT := Color(1.0, 0.78, 0.48) # Lichtfarbe bei voller Flamme

# Glow-Einstellungen: Grundzustand (dezent, wie shared/3d) und Bloom-Look
const GLOW_BASE := {"intensity": 0.6, "strength": 1.0, "bloom": 0.0, "threshold": 1.0, "scale": 2.0,
	"mode": Environment.GLOW_BLEND_MODE_SOFTLIGHT, "levels": [0.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0]}
const GLOW_BLOOM := {"intensity": 0.95, "strength": 1.1, "bloom": 0.03, "threshold": 0.7, "scale": 2.0,
	"mode": Environment.GLOW_BLEND_MODE_SCREEN, "levels": [0.0, 0.5, 1.0, 0.9, 0.8, 0.55, 0.35]}

@export var water_material: ShaderMaterial

var t := 0.0
var frame := 0
var frozen_look := -2            # -2: Reihe läuft; -1: ohne Nachbearbeitung; 0..5: fest
var show_badger := true
var badger_mask := false
var badger_ids := false
var flicker := true
var log_feet := false
var fixed_cam := ""              # "" Schnitt nach CUT_T; "total" oder "nah" fest
var walk_rate := WALK_RATE
var phase := 0                   # 0 Walk, 1 Idle, 2 Wave, 3 Idle
var turn_target := 0.0
var turn_set := false
var settle_end := -1.0           # Ende des Übergangs Laufpose -> Idle
var skel: Skeleton3D
var stance := ""                 # Fuß, an dem die Wurzel hängt ("foot.L"/"foot.R")
var toe_prev := {}               # Zehen im Bild davor (Koordinaten der Figur)
var boats := {}
var lantern_mat: StandardMaterial3D
var lamp_mat: StandardMaterial3D
var halo_mat: StandardMaterial3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var current_look := -99
var current_cam := ""
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []

@onready var world_vp: SubViewport = $ScreenVP/WorldVP
@onready var screen_vp: SubViewport = $ScreenVP
@onready var harbor: Node3D = $ScreenVP/WorldVP/World/Harbor
@onready var badger: Node3D = $ScreenVP/WorldVP/World/Badger
@onready var player: AnimationPlayer = $ScreenVP/WorldVP/World/Badger/AnimationPlayer
@onready var camera: Camera3D = $ScreenVP/WorldVP/World/Camera
@onready var env: Environment = ($ScreenVP/WorldVP/World/WorldEnvironment as WorldEnvironment).environment
@onready var rotor: Node3D = $ScreenVP/WorldVP/World/Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $ScreenVP/WorldVP/World/Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $ScreenVP/WorldVP/World/Attach/LighthouseLight/Omni
@onready var sky_material: ShaderMaterial = env.sky.sky_material
@onready var world_view: TextureRect = $ScreenVP/WorldView
@onready var final_view: TextureRect = $Final
@onready var ui: Control = $ScreenVP/UI
@onready var label: Control = $LabelLayer/LookLabel
@onready var world_post: ShaderMaterial = world_view.material
@onready var screen_post: ShaderMaterial = final_view.material


func _ready() -> void:
	var t0 := 0.0
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--look="):
			frozen_look = int(arg.get_slice("=", 1))
		elif arg.begins_with("--t0="):
			t0 = float(arg.get_slice("=", 1))
		elif arg == "--no-badger":
			show_badger = false
		elif arg == "--no-ui":
			ui.visible = false
		elif arg == "--no-label":
			label.visible = false
		elif arg == "--badger-mask":
			badger_mask = true
		elif arg == "--badger-ids":
			badger_ids = true
		elif arg == "--no-flicker":
			flicker = false
		elif arg.begins_with("--cam="):
			fixed_cam = arg.get_slice("=", 1)
		elif arg == "--log-feet":
			log_feet = true

	world_view.texture = world_vp.get_texture()
	final_view.texture = screen_vp.get_texture()
	world_post.set_shader_parameter("src_tex", world_view.texture)
	screen_post.set_shader_parameter("src_tex", final_view.texture)
	_load_palette()

	camera.fov = CAM_FOV
	_set_camera("nah")

	_attach_to_empties()

	# Wasser: Material "Water" per Name ersetzen, Farbe und Rauheit aus dem glTF übernehmen.
	var water := find_material(harbor, "Water") as StandardMaterial3D
	water_material.set_shader_parameter("albedo", water.albedo_color)
	water_material.set_shader_parameter("roughness", water.roughness)
	var n := replace_material(harbor, "Water", water_material)
	if n != 1:
		push_error("Material Water %d-mal gefunden (erwartet 1)" % n)
	(harbor.get_node("Sea") as MeshInstance3D).extra_cull_margin = 1.0

	# Leuchtende Teile teilen sich "Glass": je Objekt eine Kopie für eigenes Flackern.
	lantern_mat = unique_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = unique_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	# Animation von Hand weiterschalten (in _update_badger), damit Pose und Wurzel im selben Schritt stehen
	player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	player.play("Walk")
	player.speed_scale = WALK_RATE
	skel = badger.find_child("Skeleton3D", true, false) as Skeleton3D
	badger.position = Vector3(START_X, 0.0, 1.2)
	badger.visible = show_badger
	if badger_mask or badger_ids:
		var mask_mat := StandardMaterial3D.new()
		mask_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		mask_mat.albedo_color = Color(1, 0, 1)
		mask_mat.disable_fog = true
		var cap_mat := mask_mat.duplicate() as StandardMaterial3D
		cap_mat.albedo_color = Color(0, 1, 0)
		var vest_mat := mask_mat.duplicate() as StandardMaterial3D
		vest_mat.albedo_color = Color(0, 0, 1)
		for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
			mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			if badger_mask:
				mi.material_override = mask_mat
				continue
			for i in mi.mesh.get_surface_count():
				var m := mi.mesh.surface_get_material(i)
				var mname := m.resource_name if m else ""
				mi.set_surface_override_material(i, cap_mat if mname == "Cap" else (vest_mat if mname == "Vest" else mask_mat))

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	_build_halo()
	_build_smoke()

	var to_cam_l := CAM_POS - rotor.global_position
	beam_yaw0 = atan2(-to_cam_l.x, -to_cam_l.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	# Bild i der Aufnahme soll t = t0 + i/30 zeigen. _process zählt vor dem ersten Bild einen Schritt weiter,
	# deshalb beginnt t einen Schritt früher (sonst zeigt das letzte der 180 Bilder schon t = 6,0 und damit
	# wieder den ersten Look). Vorspulen für Standbilder und Langlauf-Prüfungen in denselben Schritten.
	var step := 1.0 / 30.0
	t = -step
	_update(0.0)
	while t + step * 0.5 < t0 - step:
		t += step
		frame += 1
		_update(step)


func _process(delta: float) -> void:
	t += delta
	frame += 1
	_update(delta)
	if log_feet:
		_log_feet()


## Zehenspitzen beider Fußknochen (Stand nach _update, also wie gerendert): Welt-x/y/z und Bildpunkt,
## dazu Einstellung und Standfuß der Fuß-Sperre
func _log_feet() -> void:
	var parts := PackedStringArray()
	for bn in ["foot.L", "foot.R"]:
		var toe := badger.to_global(_toe_local(bn))
		var sp := camera.unproject_position(toe)
		parts.append("%s %.4f %.4f %.4f %.2f %.2f" % [bn, toe.x, toe.y, toe.z, sp.x, sp.y])
	print("FEET %d %.4f %s cam=%s stance=%s root %.4f %.4f %.2f" % [frame, t, " ".join(parts), current_cam, stance,
		badger.position.x, badger.position.z, rad_to_deg(badger.rotation.y)])


func _update(delta: float) -> void:
	_update_look()
	_set_camera(fixed_cam if fixed_cam != "" else ("total" if t < CUT_T - 1e-6 else "nah"))
	var ui_a := clampf((t - CUT_T) / UI_FADE, 0.0, 1.0)
	if fixed_cam != "":
		ui_a = 1.0 if fixed_cam == "nah" else 0.0
	ui.modulate.a = ui_a
	_update_badger(delta)
	_update_smoke()

	var k := 0
	for b in boats:
		var ph := 1.7 * k
		var roll := deg_to_rad(2.2) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(0.9) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.035 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		k += 1

	water_material.set_shader_parameter("time_s", t)
	sky_material.set_shader_parameter("time_s", t)

	# Laterne: Flamme f zwischen 0,45 und 1 (Rauschen mit festem Seed); Glas, Licht, Lichtfarbe und Lichthof
	# folgen ihr gemeinsam. Das Glas leuchtet schwächer als in shared/3d (1,7 statt 4), sonst läuft es im
	# Tonemapping in Weiß aus und das Flackern ist nicht zu sehen.
	var f := 0.85
	if flicker:
		var n := lantern_noise.get_noise_1d(t * 5.0) + 0.45 * lantern_noise.get_noise_1d(t * 19.0 + 50.0)
		f = clampf(0.78 + 0.55 * n, 0.45, 1.0)
	var lc := LANTERN_DIM.lerp(LANTERN_BRIGHT, (f - 0.45) / 0.55)
	lantern_omni.light_energy = 2.6 * f
	lantern_omni.light_color = lc
	lantern_mat.emission_energy_multiplier = 1.7 * f
	lantern_mat.emission = lc
	var hk := 0.5 * f * f
	halo_mat.albedo_color = Color(lc.r * hk, lc.g * hk, lc.b * hk, 1.0)

	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 24.0)
	lamp_mat.emission_energy_multiplier = 4.0 + 26.0 * facing
	lamp_omni.light_energy = 2.0 + 4.0 * facing

	world_post.set_shader_parameter("frame", frame)
	screen_post.set_shader_parameter("time_s", t)
	ui.set("t", t)
	ui.queue_redraw()
	label.set("t", t)
	label.queue_redraw()


# --- Looks ---------------------------------------------------------------------------------------
func look_index() -> int:
	if frozen_look >= -1:
		return frozen_look
	# kleiner Zuschlag: 30 × (1/30) ergibt in double 0,99999…, der Wechsel soll genau auf Bild 30, 60 … fallen
	return posmod(int(floor(t / LOOK_TIME + 1e-6)), LOOKS.size())


func _update_look() -> void:
	var i := look_index()
	if i == current_look:
		return
	current_look = i
	var lk: Dictionary = LOOKS[i] if i >= 0 else {"world": 0, "crt": false, "bloom": false}
	world_post.set_shader_parameter("look", lk["world"])
	screen_post.set_shader_parameter("crt", 1.0 if lk["crt"] else 0.0)
	_apply_glow(GLOW_BLOOM if lk["bloom"] else GLOW_BASE)
	label.set("look", i)
	label.set("look_start", floor(t / LOOK_TIME + 1e-6) * LOOK_TIME if frozen_look < -1 else -10.0)


func _apply_glow(g: Dictionary) -> void:
	env.glow_intensity = g["intensity"]
	env.glow_strength = g["strength"]
	env.glow_bloom = g["bloom"]
	env.glow_hdr_threshold = g["threshold"]
	env.glow_hdr_scale = g["scale"]
	env.glow_blend_mode = g["mode"]
	for l in 7:
		env.set_glow_level(l, g["levels"][l])


## Palette (16×1 PNG) als Uniform-Felder: sRGB und OKLab (für den Farbabstand im Shader)
func _load_palette() -> void:
	var img := (load("res://textures/palette16.png") as Texture2D).get_image()
	var rgb := PackedVector3Array()
	var lab := PackedVector3Array()
	for x in img.get_width():
		var c := img.get_pixel(x, 0)
		rgb.append(Vector3(c.r, c.g, c.b))
		lab.append(srgb_to_oklab(Vector3(c.r, c.g, c.b)))
	while rgb.size() < 16:
		rgb.append(rgb[rgb.size() - 1])
		lab.append(lab[lab.size() - 1])
	world_post.set_shader_parameter("pal_rgb", rgb)
	world_post.set_shader_parameter("pal_lab", lab)
	world_post.set_shader_parameter("pal_count", img.get_width())
	label.set("palette", rgb.slice(0, img.get_width()))


static func srgb_to_oklab(c: Vector3) -> Vector3:
	var l := Vector3.ZERO
	for i in 3:
		var v := c[i]
		l[i] = v / 12.92 if v <= 0.04045 else pow((v + 0.055) / 1.055, 2.4)
	var lm := 0.4122214708 * l.x + 0.5363325363 * l.y + 0.0514459929 * l.z
	var mm := 0.2119034982 * l.x + 0.6806995451 * l.y + 0.1073969566 * l.z
	var sm := 0.0883024619 * l.x + 0.2817188376 * l.y + 0.6299787005 * l.z
	lm = pow(lm, 1.0 / 3.0)
	mm = pow(mm, 1.0 / 3.0)
	sm = pow(sm, 1.0 / 3.0)
	return Vector3(
		0.2104542553 * lm + 0.7936177850 * mm - 0.0040720468 * sm,
		1.9779984951 * lm - 2.4285922050 * mm + 0.4505937099 * sm,
		0.0259040371 * lm + 0.7827717662 * mm - 0.8086757660 * sm)


# --- Kamera --------------------------------------------------------------------------------------
func _set_camera(which: String) -> void:
	if which == current_cam:
		return
	current_cam = which
	if which == "total":
		camera.position = TOTAL_POS
		camera.rotation_degrees = TOTAL_ROT
	else:
		camera.look_at_from_position(CAM_POS, CAM_TARGET, Vector3.UP)


# --- Dachs ---------------------------------------------------------------------------------------
## Ablauf: Walk (2,4-fach) -> ab BRAKE_T Animationstempo auf 0 (die Pose bleibt mit dem rechten Fuß in der
## Luft stehen) -> eingefrorene Pose blendet auf Idle über (rechter Fuß setzt auf) -> Wave -> Idle.
## Gleichzeitig dreht sich die Figur ab TURN_T auf dem linken Standfuß zur Kamera. Die Wurzel folgt dem
## Standfuß: _lock_feet() verschiebt sie so, dass dessen Zehe liegen bleibt (nur in Wechselbildern beim Laufen,
## in denen kein Fuß fest steht, mit dem Lauftempo).
func _update_badger(delta: float) -> void:
	var rot_prev := badger.rotation.y
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		if t >= BRAKE_T + BRAKE_TIME:
			phase = 1
			settle_end = t + IDLE_BLEND
			_settle_to_idle()
			player.speed_scale = 1.0
	elif phase == 1 and settle_end > 0.0 and t >= settle_end:
		settle_end = -1.0
		player.play("Idle")
	elif phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	if t >= TURN_T and not turn_set:
		# Blickrichtung zur Kamera vom Standfuß aus (Figur blickt lokal nach +X)
		turn_set = true
		var to_cam := CAM_POS - badger.to_global(toe_prev.get(stance, Vector3.ZERO))
		turn_target = atan2(-to_cam.z, to_cam.x)
	badger.rotation.y = turn_target * smoothstep(TURN_T, TURN_T + TURN_TIME, t)
	player.advance(delta)
	_lock_feet(rot_prev, delta)


## Zehenspitze eines Fußknochens in Koordinaten der Figur (Wurzel = Boden zwischen den Füßen)
func _toe_local(bn: String) -> Vector3:
	var pose := skel.get_bone_global_pose(skel.find_bone(bn))
	return badger.to_local(skel.global_transform * (pose * TOE))


## Fuß-Sperre: Standfuß ist der bisherige, solange seine Zehe am Boden bleibt; sonst der Fuß, der in diesem
## Schritt am tiefsten war. Die Wurzel wird waagerecht so gesetzt, dass dessen Zehe in der Welt dort bleibt,
## wo sie im Bild davor war: X_neu = X_alt + R_alt · p_alt − R_neu · p_neu. Das deckt Laufen, Bremsen,
## Überblenden und Drehen ab; gedreht wird damit automatisch um die Zehe des Standfußes.
func _lock_feet(rot_prev: float, delta: float) -> void:
	var toe_now := {}
	for bn in ["foot.L", "foot.R"]:
		toe_now[bn] = _toe_local(bn)
	if toe_prev.is_empty():
		toe_prev = toe_now
		stance = "foot.L" if toe_now["foot.L"].y <= toe_now["foot.R"].y else "foot.R"
		return
	var low := func(bn: String) -> float: return maxf(toe_prev[bn].y, toe_now[bn].y)
	if low.call(stance) >= PLANT_Y:
		var other := "foot.R" if stance == "foot.L" else "foot.L"
		if low.call(other) < low.call(stance):
			stance = other
	var d := Vector3.ZERO
	# Im Stehen (Idle, Wave) rollt die Zehe bis 2,2 cm hoch, ohne dass der Fuß abhebt: dort nur PLANT_Y prüfen,
	# sonst wandert die Figur in Wechselbildern ohne Sperre langsam weg (gemessen 11 mm in 34 s).
	if low.call(stance) < (FIRM_Y if walk_rate > 0.0 else PLANT_Y):
		var p_old: Vector3 = toe_prev[stance]
		var p_new: Vector3 = toe_now[stance]
		d = Basis(Vector3.UP, rot_prev) * p_old - Basis(Vector3.UP, badger.rotation.y) * p_new
	else:
		# Wechselbild (Zehe hebt ab bzw. setzt gerade auf): kein Fuß steht fest, Wurzel mit dem Lauftempo
		# schieben. Sonst stockt die Figur in diesem Bild um bis zu 10 mm (gemessen).
		d = Basis(Vector3.UP, badger.rotation.y) * Vector3(WALK_SPEED * walk_rate * delta, 0.0, 0.0)
	badger.position += Vector3(d.x, 0.0, d.z)
	toe_prev = toe_now


## Übergang Laufpose -> Idle als eigene Animation "Settle": Schlüssel alle 1/30 s von der eingefrorenen
## Walk-Pose zur ersten Idle-Pose, über smoothstep verteilt, damit der rechte Fuß ohne Restgeschwindigkeit
## aufsetzt. Ein Überblenden mit play("Idle", Zeit) mischt dagegen linear (der Fuß landet in voller Fahrt),
## und die ausgeblendete Walk liefe mit dem neuen Tempo 1,0 weiter und schöbe die Füße.
func _settle_to_idle() -> void:
	var walk := player.get_animation("Walk")
	var idle := player.get_animation("Idle")
	var at := player.current_animation_position
	var a := Animation.new()
	a.length = IDLE_BLEND
	var n := maxi(2, roundi(IDLE_BLEND * 30.0))
	for i in walk.get_track_count():
		var tt := walk.track_get_type(i)
		if tt not in [Animation.TYPE_POSITION_3D, Animation.TYPE_ROTATION_3D, Animation.TYPE_SCALE_3D]:
			continue
		var path := walk.track_get_path(i)
		var k := idle.find_track(path, tt)
		var j := a.add_track(tt)
		a.track_set_path(j, path)
		# Der rechte Unterschenkel ist früher am Ziel als der Rest; so setzt der Fuß fast senkrecht auf, statt
		# beim Aufsetzen noch 2 cm zu wandern (gemessen: 8 mm in den letzten beiden Bildern statt 24 mm).
		var w_end := 1.0
		if String(path).ends_with(":shin.R"):
			w_end = SETTLE_SHIN
		for step in n + 1:
			var w := smoothstep(0.0, w_end, float(step) / n)
			var kt := IDLE_BLEND * step / n
			match tt:
				Animation.TYPE_POSITION_3D:
					var p0 := walk.position_track_interpolate(i, at)
					var p1 := idle.position_track_interpolate(k, 0.0) if k >= 0 else p0
					a.position_track_insert_key(j, kt, p0.lerp(p1, w))
				Animation.TYPE_ROTATION_3D:
					var q0 := walk.rotation_track_interpolate(i, at)
					var q1 := idle.rotation_track_interpolate(k, 0.0) if k >= 0 else q0
					a.rotation_track_insert_key(j, kt, q0.slerp(q1, w))
				Animation.TYPE_SCALE_3D:
					var s0 := walk.scale_track_interpolate(i, at)
					var s1 := idle.scale_track_interpolate(k, 0.0) if k >= 0 else s0
					a.scale_track_insert_key(j, kt, s0.lerp(s1, w))
	var lib := player.get_animation_library("")
	if lib.has_animation("Settle"):
		lib.remove_animation("Settle")
	lib.add_animation("Settle", a)
	player.play("Settle")


# --- Lichter an die Empties hängen ---------------------------------------------------------------
func _attach_to_empties() -> void:
	var attach := $ScreenVP/WorldVP/World/Attach
	for holder in attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Materialien nach Namen ----------------------------------------------------------------------
static func find_material(root: Node, mat_name: String) -> Material:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				return m
	return null


static func replace_material(root: Node, mat_name: String, mat: Material) -> int:
	var count := 0
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				mi.set_surface_override_material(i, mat)
				count += 1
	return count


static func unique_material(mi: MeshInstance3D) -> StandardMaterial3D:
	var m := (mi.mesh.surface_get_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
	mi.set_surface_override_material(0, m)
	return m


# --- Lichthof der Laterne: Billboard, additiv, Stärke setzt _update() mit dem Flackern ------------
func _build_halo() -> void:
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.25, 1.0])
	grad.colors = PackedColorArray([Color(1, 1, 1, 1), Color(0.45, 0.45, 0.45, 1), Color(0, 0, 0, 1)])
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.width = 128
	tex.height = 128
	halo_mat = StandardMaterial3D.new()
	halo_mat.albedo_texture = tex
	halo_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	halo_mat.blend_mode = BaseMaterial3D.BLEND_MODE_ADD
	halo_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	halo_mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	halo_mat.no_depth_test = true
	halo_mat.disable_fog = true
	var quad := QuadMesh.new()
	quad.size = Vector2(1.5, 1.5)
	var halo := MeshInstance3D.new()
	halo.name = "LanternHalo"
	halo.mesh = quad
	halo.material_override = halo_mat
	halo.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	(harbor.find_child("LanternLight", true, false) as Node3D).add_child(halo)


# --- Rauch: Billboards mit festem Ablauf (aus shared/3d/demo übernommen) --------------------------
func _build_smoke() -> void:
	var grad := Gradient.new()
	grad.offsets = PackedFloat32Array([0.0, 0.55, 1.0])
	grad.colors = PackedColorArray([Color(1, 1, 1, 0.9), Color(1, 1, 1, 0.45), Color(1, 1, 1, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.width = 64
	tex.height = 64
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = tex
	mat.albedo_color = Color(0.72, 0.72, 0.76)
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_ENABLED
	mat.roughness = 1.0
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		p.material_override = mat
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(p)
		smoke.append(p)
		smoke_jitter.append(Vector3(rng.randf_range(-0.15, 0.15), rng.randf_range(0.8, 1.2), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE  # 0..1
		var j := smoke_jitter[i]
		var p := smoke[i]
		# steigt auf und treibt mit dem Wind nach rechts (+X)
		p.position = Vector3(1.4 * age * age + j.x * age, 2.2 * age * j.y, j.z * age)
		var s := lerpf(0.35, 1.5, sqrt(age))
		p.scale = Vector3(s, s, s)
		p.transparency = 1.0 - 0.55 * smoothstep(0.0, 0.12, age) * (1.0 - smoothstep(0.45, 1.0, age))
