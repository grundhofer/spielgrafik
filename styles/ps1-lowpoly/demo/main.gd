extends Node3D
## PS1-Look: Hafen (PS1-Fassung harbor_ps1.glb, aus shared/3d per Blender-Skript) und Dachs mit eigenen
## Shadern (Vertex-Snapping, Gouraud-Licht je Eckpunkt mit vorberechneten Vertexfarben, Depth Cueing über
## Vertexfarben, affine 64×64-Texturen ohne Mipmaps, Sortierung nach Polygonen statt Z-Puffer), 320×240,
## 15 Bit mit Dithering.
##
## Ablauf der 6 s wie in der Probeszene von shared/3d: Dachs läuft (Walk), bremst, dreht sich zur Kamera,
## winkt, steht. Zwei Einstellungen wie in Spielen der Zeit: bis 4,0 s die Totale mit langsamer Fahrt und
## leichtem Schwenk (dabei springen alle Kanten), in der sich der Dachs am Ende zur Kamera dreht, dann ein harter
## Schnitt auf eine feste Nahaufnahme (Dachs ca. 76 px hoch, Laterne rechts, Leuchtturm dahinter), in der er
## steht und winkt. Boote schaukeln, Wasser wogt, Laterne flackert, Leuchtfeuer dreht sich, Schornstein raucht.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (capture.py nimmt mit --fixed-fps auf).

# --- Dachs (Werte aus shared/3d/badger_notes.md) ---------------------------------------------
const WALK_SPEED := 0.367
const WALK_RATE := 2.0
const BRAKE_T := 3.1
const BRAKE_TIME := 0.4
const IDLE_T := 3.45
## Drehung noch in der Totale (3,5–3,95 s), damit die Nahaufnahme mit dem stehenden Dachs beginnt: Eine Drehung
## auf der Stelle ohne Schritte lässt die Füße über den Boden wandern (in der Nahaufnahme waren das etwa 15 px).
## Gedreht wird um die Mitte zwischen den Pfoten (FEET_MID), nicht um den Ursprung zwischen den Fußgelenken;
## so bleibt das Fußpaar an seinem Platz und nur die Pfoten schwenken.
const TURN_T := 3.5
const TURN_TIME := 0.45
const FEET_MID := Vector3(0.06, 0.0, 0.0)         # Mitte der Pfoten (Fußgelenk x = 0, Zehen x = 0,12; badger_notes.md)
const WAVE_T := 4.15
const WAVE_LEN := 1.5
const TURN_TO := -90.0                           # Grad (-90 = Blick nach +Z): Dreiviertelprofil zur Nahaufnahme, 12° rechts
                                                 # an der Kamera vorbei (frontal wäre -102°). Verglichen -75/-90/-105/-120
                                                 # in Bild 118/136/150 (erste Fassung): bei -75° liegt die weiße Schnauze vor dem weißen
                                                 # Ärmel des Winkarms und geht darin unter; bei -90° stehen Schnauze mit
                                                 # Nase, Winkarm und Paket getrennt; ab -105° wird das Gesicht zur Maske

# --- Einstellung 1: Totale, von der Hauptkamera aus langsam heran, dabei leichter Schwenk ------
const CAM_FROM := Vector3(-1.8, 3.4, 14.5)       # Position der Hauptkamera aus shared/3d
const CAM_TO := Vector3(-2.3, 2.1, 11.0)
const CAM_PITCH := -6.0                          # Grad; Hauptkamera -3, hier tiefer, damit der Dachs über dem Fenster steht
const CAM_TIME := 6.0                            # Fahrkurve (auslaufend) wie zuvor über 6 s, geschnitten bei CUT_T
const CAM_YAW_FROM := 2.0                        # Grad, positiv = nach links; Schwenk folgt dem Dachs nach rechts
const CAM_YAW_TO := -1.5
const CAM_FOV := 68.61                           # horizontal (Keep Width) = Breite der Hauptkamera bei 16:9

# --- Einstellung 2: feste Nahaufnahme ab CUT_T (aus scripts/frame_closeup.py berechnet) -----------
const CUT_T := 3.983                             # Bild 120 (halbes Bild vor 4,0 s, damit nicht Rundungsfehler der
                                                 # aufsummierten Zeit entscheiden); Dachs steht und blickt zur Kamera
## frame_closeup.py --angle -12 --dist 2.8 --height 0.5 --fov 80 --feet 84,156: Laternenpfahl ganz im Bild
## (rechts), Leuchtturm ganz im Bild (Mitte, unter dem Ortsfenster), Dachs links vorn.
const CU_OFFSET := Vector3(-0.582, 0.5, 2.739)   # vom Dachs aus: 2,8 m entfernt, 12° links von vorn, 0,5 m hoch
const CU_PITCH := -0.19
const CU_YAW := -33.74
const CU_FOV := 80.0                             # weiter Winkel: Dachs ca. 74 px, Laterne und Leuchtturm im Bild

# --- Sortierung nach Polygonen (kein Z-Puffer) ----------------------------------------------------
## Versatz in der Sortierung (m) je "Objekt/Material" oder Material, wie die Versätze, mit denen Entwickler
## der Zeit vorhersehbare Sortierfehler in festen Szenen behoben: Wände des Häuschens hinter Tür, Fenster und
## Dach, Tür hinter ihren Querbrettern, Glas hinter den Rahmen. Das Meer liegt ganz hinten (ps1_water).
## Die Figur hat keinen Versatz (Augen, Nase und Arme sortieren sich gegen den Körper, wie auf der Konsole).
const OT_BIAS := {
	"Cottage/Stone": 0.4, "Cottage/WoodDark": 0.06, "Cottage/Roof": -0.3, "CottageWindow/Glass": 0.12,
	"Badger/Scarf": -0.04,
	"Paving": 0.3,
}
## Der Kaiboden sortiert nicht als ganzes Polygon, sondern je Pixel (+0,3 m): Seine großen Vierecke würden
## sonst Boote, Steg und Kaimauer dahinter überdecken bzw. von ihnen überdeckt (die Nahaufnahme blickt
## flach über die Kaikante). Alles, was auf dem Boden steht, gewinnt durch den Versatz.
const OT_PER_PIXEL := ["Paving"]
const VC_STRENGTH := 0.8                         # Gewicht der Vertexfarben (Umgebungsverdeckung aus Blender)

# --- Umgebung --------------------------------------------------------------------------------
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 6.2                       # Strahl zeigt bei 6,2 s zur Endposition der Totale (CAM_TO)
const SMOKE_PUFFS := 8
const SMOKE_LIFE := 4.0
const SEED := 20261010
const FLICKER_MIN := 0.55                        # Laterne: Helligkeit schwankt zwischen 55 und 100 %

# --- Licht (sRGB-Farbe, Stärke); main.gd rechnet nach linear um --------------------------------
const AMBIENT := Color(0.42, 0.40, 0.56)
const SUN_COLOR := Color(1.0, 0.72, 0.50)
const SUN_ENERGY := 1.35
const SUN_DIR := Vector3(0.86, -0.24, -0.46)     # Richtung, in die das Licht läuft (wie shared/3d)
const FOG_RANGE := Vector2(30.0, 560.0)
const BADGER_BOOST := Color(0.30, 0.27, 0.30)    # Zusatz-Grundlicht nur für die Figur in der Totale (sRGB)
const BADGER_BOOST_CU := Color(0.15, 0.135, 0.16) # in der Nahaufnahme weniger, damit Gouraud-Verläufe bleiben
const SKY_MARGIN := 16.0                         # Himmelsbild 352 breit: 16 px Rand je Seite für den Schwenk
const SKY_HORIZON_ROW := 143.0                   # Himmelsbild 160 hoch: oben 24 px (Nahaufnahme) bzw. 48 px (Totale) Rand

## Textur je Material: [Datei, Meter je Kachel]. Besonderheiten je Objekt in tex_for().
const TEX := {
	"Paving": ["flagstone", 6.0],                # Kaiboden aus großen Vierecken (harbor_ps1.glb): 9,4 cm je Texel
	"BarrelSide": ["barrel", 1.0],               # eigene Fass-Textur, UV 0..1 einmal herum
	"Railing": ["railing", 1.0],                 # Ausschnitt-Textur, eine Kachel je Seite des Geländers
	"CrateSide": ["crate", 1.0],                 # Kiste: eine Textur je Würfelseite (Bretter und Rahmen gemalt)
	"Stone": ["granite", 6.0],
	"StoneDark": ["darkstone", 2.0],
	"Wood": ["wood", 1.2],
	"WoodDark": ["wooddark", 1.2],
	"WhitePaint": ["plaster", 2.5],
	"RedPaint": ["redplaster", 2.0],
	"Roof": ["slate", 2.0],
	"Rope": ["rope", 0.6],
	"Metal": ["iron", 1.0],
	"Rock": ["rock", 5.0],
	"Sand": ["sand", 4.0],
	"Grass": ["grass", 5.0],
}

const LIT_SHADER := preload("res://shaders/ps1_lit.gdshader")
const SPRITE_SHADER := preload("res://shaders/ps1_sprite.gdshader")
const SMOKE_TEX := preload("res://textures/smoke.png")

@export var water_material: ShaderMaterial

var t := 0.0
var walk_rate := WALK_RATE
var phase := 0
var boats := {}
var smoke: Array[MeshInstance3D] = []
var smoke_mats: Array[ShaderMaterial] = []
var smoke_jitter: Array[Vector3] = []
var lantern_mat: ShaderMaterial
var lamp_mat: ShaderMaterial
var window_mat: ShaderMaterial
var lantern_noise := FastNoiseLite.new()
var flicker_range := Vector2(0.0, 1.0)
var turn_to := TURN_TO
var measure_cam := false                         # Messansicht für scripts/measure_feet.py
var beam_yaw0 := 0.0
var _cache := {}
var figure_mats: Array[ShaderMaterial] = []
var _boost := Color(-1, -1, -1)
var stop_pos := Vector3.ZERO                     # Standort, an dem der Dachs anhält (Drehpunkt-Ausgleich)

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var shadow: Node3D = $BlobShadow
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_glow: MeshInstance3D = $Attach/LanternLight/Glow
@onready var lamp_glow: MeshInstance3D = $Attach/LighthouseLight/Glow
@onready var sky_rect: TextureRect = $SkyLayer/Sky


func _ready() -> void:
	_attach_to_empties()

	# Alle glTF-Materialien durch PS1-Materialien ersetzen (nach Name, je Objekt eigene Textur möglich).
	# Vorher jedes Mesh für die Sortierung nach Polygonen aufbereiten (Mittelpunkt je Dreieck in CUSTOM0).
	for root: Node in [harbor, badger]:
		for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
			if mi.material_override != null:
				continue    # eigene Knoten aus "Attach" (Lichthof, Lichtkegel)
			if mi.name != "Sea":
				mi.mesh = _ot_mesh(mi.mesh)
			for i in mi.mesh.get_surface_count():
				var src := mi.mesh.surface_get_material(i) as StandardMaterial3D
				if src == null:
					push_error("%s: Fläche %d ohne glTF-Material" % [mi.name, i])
					continue
				mi.set_surface_override_material(i, style_material(mi, src))

	# Leuchtende Teile teilen sich "Glass"; für eigenes Flackern je Objekt eine Kopie.
	lantern_mat = _unique(harbor.find_child("LanternGlass", true, false))
	lamp_mat = _unique(harbor.find_child("LighthouseLamp", true, false))
	window_mat = _unique(harbor.find_child("CottageWindow", true, false))

	var sea := harbor.get_node("Sea") as MeshInstance3D
	sea.extra_cull_margin = 1.0

	for b in ["BoatA", "BoatB"]:
		boats[b] = (harbor.get_node(b) as Node3D).transform

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.play("Walk")
	player.speed_scale = WALK_RATE

	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	# Spannweite des Flackerns über die 6 s messen und auf FLICKER_MIN..1 abbilden (deterministisch)
	flicker_range = Vector2(INF, -INF)
	for k in 181:
		var r := _flicker_raw(k / 30.0)
		flicker_range = Vector2(minf(flicker_range.x, r), maxf(flicker_range.y, r))

	var to_cam := CAM_TO - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	_setup_globals()
	_apply_debug_switches()
	_build_smoke()
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	_update(delta)


func _update(delta: float) -> void:
	RenderingServer.global_shader_parameter_set("ps1_time", t)

	_update_badger(delta)
	shadow.position = Vector3(badger.position.x, 0.008, badger.position.z)

	if t < CUT_T:
		# Einstellung 1: langsame Fahrt mit auslaufender Geschwindigkeit und linearer Schwenk
		var k := clampf(t / CAM_TIME, 0.0, 1.0)
		camera.position = CAM_FROM.lerp(CAM_TO, 1.0 - (1.0 - k) * (1.0 - k))
		var yaw := lerpf(CAM_YAW_FROM, CAM_YAW_TO, t / CUT_T)
		camera.basis = Basis.from_euler(Vector3(deg_to_rad(CAM_PITCH), deg_to_rad(yaw), 0.0))
		camera.fov = CAM_FOV
	else:
		# Einstellung 2: harter Schnitt auf eine feste Kamera (der Dachs steht ab hier auf der Stelle)
		camera.position = Vector3(badger.position.x, 0.0, badger.position.z) + CU_OFFSET
		camera.basis = Basis.from_euler(Vector3(deg_to_rad(CU_PITCH), deg_to_rad(CU_YAW), 0.0))
		camera.fov = CU_FOV
	if measure_cam:
		# feste Kamera 3,4 m vor der Laufstrecke, senkrecht dazu, Dachs ca. 68 px hoch
		camera.position = Vector3(-4.6, 0.5, 4.6)
		camera.basis = Basis()
		camera.fov = 70.0
	_set_badger_boost(BADGER_BOOST if t < CUT_T else BADGER_BOOST_CU)
	_place_sky()

	var n := 0
	for b in boats:
		var ph := 1.7 * n
		var roll := deg_to_rad(2.6) * sin(TAU * t / 3.4 + ph)
		var pitch := deg_to_rad(1.0) * sin(TAU * t / 4.6 + 0.8 + ph)
		var heave := 0.04 * sin(TAU * t / 3.9 + 2.1 + ph)
		var local := Transform3D(Basis.from_euler(Vector3(roll, 0.0, pitch)), Vector3(0.0, heave, 0.0))
		(harbor.get_node(b) as Node3D).transform = boats[b] * local
		n += 1

	# Laterne flackert zwischen 55 und 100 %: Glas, Lichthof (Helligkeit und Größe) und Punktlicht gemeinsam.
	var f := lantern_flicker(t)
	lantern_mat.set_shader_parameter("emit_scale", 0.62 * f)
	(lantern_glow.material_override as ShaderMaterial).set_shader_parameter("strength", 1.0 * f)
	lantern_glow.scale = Vector3.ONE * 1.6 * f
	_toward_camera(lantern_glow, 0.25)
	_set_light(0, "LanternLight", Color(1.0, 0.62, 0.30), 2.6 * f, 6.5)
	var w := 0.92 + 0.08 * lantern_noise.get_noise_1d(t * 3.0 + 200.0)
	window_mat.set_shader_parameter("emit_scale", 0.45 * w)

	# Leuchtfeuer dreht sich; Lampe und Lichthof blitzen, wenn der Strahl zur Kamera zeigt.
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position)
	to_cam.y = 0.0
	var facing := pow(clampf(beam_dir.dot(to_cam.normalized()), 0.0, 1.0), 16.0)
	lamp_mat.set_shader_parameter("emit_scale", 0.5 + 1.5 * facing)
	(lamp_glow.material_override as ShaderMaterial).set_shader_parameter("strength", 0.35 + 1.2 * facing)
	lamp_glow.scale = Vector3.ONE * (3.5 + 5.0 * facing)
	_toward_camera(lamp_glow, 0.8)

	_update_smoke()


## Lichthof vor das Glas setzen, und zwar zur jeweiligen Kamera hin (in der Nahaufnahme blickt sie von links
## auf die Laterne); sonst säße er seitlich neben der Lampe.
func _toward_camera(glow: Node3D, dist: float) -> void:
	var c := (glow.get_parent() as Node3D).global_position
	glow.global_position = c + (camera.global_position - c).normalized() * dist


func _flicker_raw(time: float) -> float:
	return lantern_noise.get_noise_1d(time * 6.0) + 0.6 * lantern_noise.get_noise_1d(time * 19.0 + 50.0)


## Helligkeit der Laterne 0,55..1,0 (über die 6 s gemessene Spannweite der Rauschsumme).
func lantern_flicker(time: float) -> float:
	var u := clampf((_flicker_raw(time) - flicker_range.x) / (flicker_range.y - flicker_range.x), 0.0, 1.0)
	return lerpf(FLICKER_MIN, 1.0, u)


func _update_badger(delta: float) -> void:
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		badger.position.x += WALK_SPEED * walk_rate * delta
		if t >= IDLE_T:
			phase = 1
			stop_pos = badger.position
			player.speed_scale = 1.0
			player.play("Idle", 0.3)
	elif phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)
	var ang := deg_to_rad(turn_to) * smoothstep(TURN_T, TURN_T + TURN_TIME, t)
	badger.rotation.y = ang
	if phase >= 1:
		# um die Mitte der Pfoten drehen: Ursprung so verschieben, dass FEET_MID an seinem Platz bleibt
		badger.position = stop_pos + FEET_MID - FEET_MID.rotated(Vector3.UP, ang)


# --- Materialien --------------------------------------------------------------------------------
func tex_for(mesh_name: String, mat_name: String) -> Array:
	var boat := mesh_name.begins_with("Boat")
	match mat_name:
		"Stone":
			return ["fieldstone", 2.5] if mesh_name == "Cottage" else ["granite", 2.0]
		"WhitePaint":
			return ["boatwhite", 1.5] if boat else TEX[mat_name]
		"RedPaint":
			return ["boatred", 1.5] if boat else TEX[mat_name]
		"Rock", "Sand", "Grass":
			# ferne Inseln (185–320 m): sehr große Kacheln, sonst wird die Textur zu Pixelrauschen
			var e: Array = TEX[mat_name].duplicate()
			if mesh_name == "IslandsFar":
				e[1] = e[1] * 8.0
			return e
	return TEX.get(mat_name, [])


func style_material(mi: MeshInstance3D, src: StandardMaterial3D) -> Material:
	var mat_name := src.resource_name
	if mat_name == "Water":
		return water_material
	var tx := tex_for(String(mi.name), mat_name)
	var key: String = mat_name
	var bias_key := "%s/%s" % [mi.name, mat_name]
	var bias: float = OT_BIAS.get(bias_key, OT_BIAS.get(mat_name, 0.0))
	if OT_BIAS.has(bias_key):
		key = bias_key
	if mi.get_parent() is Skeleton3D:
		key = "figure/" + key
	if tx.size() > 0:
		key += "/%s/%s" % [tx[0], tx[1]]
	if not _cache.has(key):
		var m := ShaderMaterial.new()
		m.shader = LIT_SHADER
		m.set_shader_parameter("albedo", src.albedo_color)
		if tx.size() > 0:
			var tex := load("res://textures/%s.png" % tx[0]) as Texture2D
			m.set_shader_parameter("tex", tex)
			m.set_shader_parameter("tex_mip", tex)
			m.set_shader_parameter("use_tex", true)
			m.set_shader_parameter("uv_scale", Vector2.ONE / float(tx[1]))
		m.set_shader_parameter("cutout", mat_name == "Railing")
		m.set_shader_parameter("ot_bias", bias)
		m.set_shader_parameter("ot_per_pixel", mat_name in OT_PER_PIXEL)
		if mi.get_parent() is Skeleton3D:   # Figur (Badger, Parcel); Zusatzlicht setzt _set_badger_boost()
			figure_mats.append(m)
		if src.emission_enabled:
			m.set_shader_parameter("emission", src.emission)
			m.set_shader_parameter("emit_scale", 0.5)
			m.set_shader_parameter("lit", 0.0)
		_cache[key] = m
	return _cache[key]


## Eigenes Zusatzlicht der Figur je Einstellung (Spiele der Zeit setzten Lichtmatrizen je Objekt und Kamera).
func _set_badger_boost(c: Color) -> void:
	if c == _boost:
		return
	_boost = c
	var b := lin(c)
	for m in figure_mats:
		m.set_shader_parameter("light_boost", Vector3(b.x, b.y, b.z))


func _unique(mi: MeshInstance3D) -> ShaderMaterial:
	var m := (mi.get_surface_override_material(0) as ShaderMaterial).duplicate() as ShaderMaterial
	mi.set_surface_override_material(0, m)
	return m


## Vergleichsschalter (nur zum Nachmessen): godot --path demo -- --no-snap --no-affine --no-dither
## --zbuffer (Z-Puffer statt Sortierung nach Polygonen) --mipmaps (Texturen mit Mipmaps) --no-vc (ohne Vertexfarben)
## --no-shadow (ohne Rundschatten) --no-affine-vc (Vertexfarben perspektivisch korrekt statt linear im Bildraum)
## Messung der Figur: --figure-only (nur der Dachs vor Schwarz) --measure-cam (feste Kamera nah am Laufweg)
func _apply_debug_switches() -> void:
	var args := OS.get_cmdline_user_args()
	if "--zbuffer" in args:
		RenderingServer.global_shader_parameter_set("ps1_ot", 0.0)
	if "--mipmaps" in args:
		RenderingServer.global_shader_parameter_set("ps1_mip", 1.0)
	for a in args:
		if a.begins_with("--turn="):          # nur zum Ausprobieren des Drehwinkels
			turn_to = float(a.substr(7))
	if "--figure-only" in args:               # nur der Dachs vor Schwarz (Messung, scripts/measure_feet.py)
		harbor.visible = false
		shadow.visible = false
		for n in ["SkyLayer", "UILayer", "PostLayer"]:
			(get_node(n) as CanvasLayer).visible = false
	measure_cam = "--measure-cam" in args
	if "--no-shadow" in args:                 # ohne Rundschatten (Messung, wie stark er abdunkelt)
		shadow.visible = false
	if "--no-vc" in args:
		RenderingServer.global_shader_parameter_set("ps1_vc_strength", 0.0)
	if "--no-snap" in args:
		RenderingServer.global_shader_parameter_set("ps1_snap_res", Vector2(65536.0, 65536.0))
	if "--no-affine" in args:
		RenderingServer.global_shader_parameter_set("ps1_affine", 0.0)
	if "--no-affine-vc" in args:
		RenderingServer.global_shader_parameter_set("ps1_affine_vc", 0.0)
	if "--no-dither" in args:
		($PostLayer/Dither.material as ShaderMaterial).set_shader_parameter("enabled", false)


# --- Licht als globale Shader-Werte -----------------------------------------------------------
static func lin(c: Color, e := 1.0) -> Vector4:
	var l := c.srgb_to_linear()
	return Vector4(l.r * e, l.g * e, l.b * e, 1.0)


func _setup_globals() -> void:
	RenderingServer.global_shader_parameter_set("ps1_ambient", lin(AMBIENT))
	RenderingServer.global_shader_parameter_set("ps1_sun_dir", SUN_DIR.normalized())
	RenderingServer.global_shader_parameter_set("ps1_sun_color", lin(SUN_COLOR, SUN_ENERGY))
	RenderingServer.global_shader_parameter_set("ps1_fog_range", FOG_RANGE)
	RenderingServer.global_shader_parameter_set("ps1_vc_strength", VC_STRENGTH)
	RenderingServer.global_shader_parameter_set("ps1_ot", 1.0)
	RenderingServer.global_shader_parameter_set("ps1_mip", 0.0)
	# Nebelfarbe = Horizontfarbe des Himmelsbildes (Zeilen direkt über dem Horizont), damit das Meer
	# am Horizont nahtlos in den Himmel übergeht.
	var sky := sky_rect.texture.get_image()
	var acc := Color(0, 0, 0)
	var cnt := 0
	for y in range(int(SKY_HORIZON_ROW) - 4, int(SKY_HORIZON_ROW)):
		for x in range(0, sky.get_width(), 4):
			acc += sky.get_pixel(x, y)
			cnt += 1
	var fog := Color(acc.r / cnt, acc.g / cnt, acc.b / cnt)
	RenderingServer.global_shader_parameter_set("ps1_fog_color", lin(fog))
	_set_light(1, "CottageWindow", Color(1.0, 0.66, 0.36), 1.5, 4.5, Vector3(0, 0, 0.6))
	_set_light(2, "LighthouseLight", Color(1.0, 0.86, 0.6), 2.0, 5.0)


func _set_light(slot: int, target: String, c: Color, energy: float, range_m: float, offset := Vector3.ZERO) -> void:
	var n := harbor.find_child(target, true, false) as Node3D
	var p := n.global_position + offset
	RenderingServer.global_shader_parameter_set("ps1_light%d_pos" % slot, Vector4(p.x, p.y, p.z, range_m))
	RenderingServer.global_shader_parameter_set("ps1_light%d_color" % slot, lin(c, energy))


# --- Himmel: 2D-Bild, nach Neigung und Gieren der Kamera verschoben -------------------------------
## Horizontzeile = 120 + f·tan(Neigung), seitlich f·tan(Gieren − Grundrichtung der Einstellung),
## f = 160 / tan(Bildwinkel/2) (Keep Width). Wie bei festen Kameras der Zeit gehört das Himmelsbild zur
## Einstellung: Die Nahaufnahme blickt 34° weiter rechts, zeigt aber denselben Himmelsausschnitt.
## Ganze Pixel, wie ein Hintergrund-Sprite der Zeit; bei der Fahrt springt der Himmel in 1-px-Schritten.
func _place_sky() -> void:
	var f := 160.0 / tan(deg_to_rad(camera.fov) * 0.5)
	var e := camera.basis.get_euler()     # YXZ: x = Neigung, y = Gieren
	var yaw0 := 0.0 if t < CUT_T else deg_to_rad(CU_YAW)
	sky_rect.position = Vector2(roundf(-SKY_MARGIN + f * tan(e.y - yaw0)), roundf(120.0 + f * tan(e.x) - SKY_HORIZON_ROW))


# --- Sortierung nach Polygonen: Mittelpunkt je Dreieck ---------------------------------------------
## Kein Z-Puffer: Der Shader braucht für jedes Dreieck dessen Mittelpunkt, um ihm eine einzige Tiefe zu geben
## (wie der Eintrag in der Ordering Table der Konsole). Dazu werden die Dreiecke entflochten (jede Ecke ein
## eigener Eckpunkt) und CUSTOM0 = Mittelpunkt − Eckpunkt gesetzt. Bei der geriggten Figur ist das der Versatz
## aus der Ruhepose; nach dem Skinning liegt der Punkt dann nur ungefähr in der Mitte (Dreiecke sind klein).
## Fehlen Vertexfarben (Dachs), werden sie weiß ergänzt.
static func _ot_mesh(src: ArrayMesh) -> ArrayMesh:
	var dst := ArrayMesh.new()
	for s in src.get_surface_count():
		var a := src.surface_get_arrays(s)
		var fmt: int = src.surface_get_format(s)
		var verts: PackedVector3Array = a[Mesh.ARRAY_VERTEX]
		var idx := PackedInt32Array()
		if a[Mesh.ARRAY_INDEX] != null:
			idx = a[Mesh.ARRAY_INDEX]
		else:
			idx.resize(verts.size())
			for i in verts.size():
				idx[i] = i
		var n := idx.size()
		var bone_n := 8 if fmt & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS else 4
		var out := []
		out.resize(Mesh.ARRAY_MAX)
		for k: int in [Mesh.ARRAY_VERTEX, Mesh.ARRAY_NORMAL, Mesh.ARRAY_COLOR, Mesh.ARRAY_TEX_UV, Mesh.ARRAY_TEX_UV2]:
			if a[k] != null:
				out[k] = _expand(a[k], idx, 1)
		for k: int in [Mesh.ARRAY_BONES, Mesh.ARRAY_WEIGHTS]:
			if a[k] != null:
				out[k] = _expand(a[k], idx, bone_n)
		if out[Mesh.ARRAY_COLOR] == null:
			var white := PackedColorArray()
			white.resize(n)
			white.fill(Color.WHITE)
			out[Mesh.ARRAY_COLOR] = white
		var pos: PackedVector3Array = out[Mesh.ARRAY_VERTEX]
		var off := PackedFloat32Array()
		off.resize(n * 4)
		for t3 in range(0, n, 3):
			var c := (pos[t3] + pos[t3 + 1] + pos[t3 + 2]) / 3.0
			for j in 3:
				var d := c - pos[t3 + j]
				off[(t3 + j) * 4] = d.x
				off[(t3 + j) * 4 + 1] = d.y
				off[(t3 + j) * 4 + 2] = d.z
		out[Mesh.ARRAY_CUSTOM0] = off
		var flags: int = (Mesh.ARRAY_CUSTOM_RGBA_FLOAT << Mesh.ARRAY_FORMAT_CUSTOM0_SHIFT) | (fmt & Mesh.ARRAY_FLAG_USE_8_BONE_WEIGHTS)
		dst.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, out, [], {}, flags)
		dst.surface_set_material(s, src.surface_get_material(s))
		dst.surface_set_name(s, src.surface_get_name(s))
	return dst


static func _expand(arr: Variant, idx: PackedInt32Array, stride: int) -> Variant:
	var out: Variant = arr.duplicate()
	out.resize(idx.size() * stride)
	for i in idx.size():
		var j := idx[i] * stride
		for k in stride:
			out[i * stride + k] = arr[j + k]
	return out


# --- Knoten unter "Attach" an die Empties hängen ----------------------------------------------
func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Rauch: 16×16-Sprites, 50/50-Mischung, Ausblenden per Raster ----------------------------------
func _build_smoke() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	var anchor := harbor.find_child("ChimneySmoke", true, false) as Node3D
	for i in SMOKE_PUFFS:
		var p := MeshInstance3D.new()
		p.mesh = quad
		var m := ShaderMaterial.new()
		m.shader = SPRITE_SHADER
		m.render_priority = 1
		m.set_shader_parameter("tex", SMOKE_TEX)
		# Abendgrau mit Stich ins Violette, 50/50 gemischt; nicht beleuchtet (sonst zu dunkel vor dem Himmel)
		m.set_shader_parameter("tint", Color(0.70, 0.66, 0.76, 0.5))
		m.set_shader_parameter("lit", false)
		p.material_override = m
		p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		anchor.add_child(p)
		smoke.append(p)
		smoke_mats.append(m)
		smoke_jitter.append(Vector3(rng.randf_range(-0.15, 0.15), rng.randf_range(0.85, 1.15), rng.randf_range(-0.1, 0.1)))


func _update_smoke() -> void:
	for i in smoke.size():
		var age := fposmod(t + float(i) * SMOKE_LIFE / SMOKE_PUFFS, SMOKE_LIFE) / SMOKE_LIFE
		var j := smoke_jitter[i]
		smoke[i].position = Vector3(1.3 * age * age + j.x * age, 2.0 * age * j.y, j.z * age)
		var s := lerpf(0.45, 1.7, sqrt(age))
		smoke[i].scale = Vector3(s, s, s)
		smoke_mats[i].set_shader_parameter("visible", smoothstep(0.0, 0.1, age) * (1.0 - smoothstep(0.45, 1.0, age)))
