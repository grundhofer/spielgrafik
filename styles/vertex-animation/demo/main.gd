extends Node3D
## Vertex-Animation & gebackene Simulationen (Katalogeintrag vertex-animation).
##
## Alles, was sich in der Umgebung bewegt, bewegt der Vertex-Shader:
##   - Meer: fein unterteiltes Gitter (sea_mesh.gd) mit Gerstner-Wellen (shaders/sea.gdshader).
##   - Boote, Treibfässer, Boje: das Skript rechnet dieselbe Wellenfunktion (waves.gd) an Bug, Heck und
##     Seiten und setzt nur die Transformation (Hub, Stampfen, Rollen, gefedert).
##   - Wimpel und Fischernetz: Rauschen und laufende Welle, nach Abstand von der festen Kante gewichtet
##     (shaders/flutter.gdshader).
##   - Fahne: Stoffsimulation aus Blender, als Vertex Animation Texture abgespielt (shaders/vat_flag.gdshader).
##   - Möwen: MultiMeshInstance3D, gebackener Flügelschlag (VAT), Phase/Tempo/Ausschlag je Instanz.
## Der Dachs kommt unverändert aus shared/3d (Skelettanimation), Licht und Himmel aus der Probeszene.
## Alles hängt an der aufsummierten Zeit t und festen Seeds (reproduzierbare Aufnahme).
##
## Benutzerargumente (nach "--"):
##   --t0=SEK    Startzeit verschieben (lange Läufe prüfen)
##   --measure   druckt je Bild Fußpunkte und Mützendeckel des Dachses (Welt und Bild), für
##               scripts/measure_badger.py
##   --mask      Dachs weiß auf Schwarz, alles andere ausgeblendet (Silhouettenmessung)
##   --static    Vergleichsschalter: Zeit der Vertex-Animation bleibt 0 (Wellen, Schwimmer, Fahne, Netz, Wimpel
##               und Möwen stehen; Dachs, Leuchtfeuer und Laterne laufen weiter)
##   --perf      druckt am Ende Median der Bildzeit (Wanduhr; ohne V-Sync starten), Skriptzeit je Bild,
##               GPU-/CPU-Zeit des Viewports (Metal liefert keine GPU-Zeit: 0), Dreiecke und Draw-Calls
##   --variant=coarse   Gerstner auf dem groben Original-Gitter von harbor.glb (1,5-m-Zellen) statt 0,3 m
##   --variant=flat     feines Gitter ohne Wellen (wave_count = 0), Kostenvergleich

# --- Dachs (Werte aus shared/3d/badger_notes.md) -------------------------------------------------
const WALK_SPEED := 0.367
const WALK_RATE := 2.0
const PATH_Z := 2.8
const START_X := -4.6
const TURN_T := 1.85              # biegt im Gehen zur Kamera ab (Drehung um den aufgesetzten Fuß)
const TURN_TIME := 0.8
const BRAKE_T := 2.6              # bremst (Tempo und Animation gemeinsam)
const BRAKE_TIME := 0.4
const IDLE_T := 3.0
const WAVE_T := 3.5
const WAVE_LEN := 1.5

# --- Umgebung --------------------------------------------------------------------------------------
const WIND := Vector3(0.97, 0.0, 0.24)          # Windrichtung (Welt), gleich für Fahne, Wimpel und Netz
const FLAG_POLE := Vector3(-0.35, 0.0, -0.2)
const POLE_H := 4.6
const NET_X := Vector2(-6.0, -4.2)
const NET_Z := 1.45
const NET_TOP := 1.95
const NET_DROP := 1.55
const BEAM_PERIOD := 8.0
const BEAM_FACING_T := 1.2
const GULLS := 11
const FLAG_FPS := 30.0             # Bildrate der Stoffsimulation (blender/build_vat.py)
const FLAG_FRAMES := 120.0         # Bilder in flag_pos.exr / flag_nrm.exr (Schleife 4 s)
const SEED := 20261013

@export var sea_material: ShaderMaterial
@export var flag_material: ShaderMaterial
@export var gull_material: ShaderMaterial
@export var flutter_shader: Shader

var t := 0.0
var t_offset := 0.0
var walk_rate := WALK_RATE
var phase := 0
var waves := Waves.new()
var floaters: Array[Dictionary] = []
var time_mats: Array[ShaderMaterial] = []    # Wimpel und Netz: Uniform time_s (Meer, Fahne, Möwen: Phasen vom Skript)
var pennants: Array[Node3D] = []
var gull_mm: MultiMesh
var gull_paths: Array[Dictionary] = []
var lantern_mat: StandardMaterial3D
var lamp_mat: StandardMaterial3D
var lantern_noise := FastNoiseLite.new()
var beam_yaw0 := 0.0
var frame := 0

var measure := false
var mask := false
var static_mode := false
var perf := false
var variant := ""
var perf_gpu: Array[float] = []
var perf_cpu: Array[float] = []
var perf_ticks: Array[int] = []
var perf_script: Array[float] = []

@onready var harbor: Node3D = $Harbor
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var camera: Camera3D = $Camera
@onready var sea: MeshInstance3D = $Sea
@onready var rotor: Node3D = $Attach/LighthouseLight/Rotor
@onready var lantern_omni: OmniLight3D = $Attach/LanternLight/Omni
@onready var lamp_omni: OmniLight3D = $Attach/LighthouseLight/Omni
@onready var ui: CanvasLayer = $UI


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--t0="):
			t_offset = float(a.substr(5))
		elif a.begins_with("--variant="):
			variant = a.substr(10)
	measure = "--measure" in OS.get_cmdline_user_args()
	mask = "--mask" in OS.get_cmdline_user_args()
	static_mode = "--static" in OS.get_cmdline_user_args()
	perf = "--perf" in OS.get_cmdline_user_args()
	t = t_offset

	_attach_to_empties()
	_build_sea()
	_build_floaters()
	_build_flag()
	_build_net()
	_build_pennants()
	_build_gulls()

	lantern_mat = unique_material(harbor.find_child("LanternGlass", true, false))
	lamp_mat = unique_material(harbor.find_child("LighthouseLamp", true, false))
	for glass in ["LanternGlass", "LighthouseLamp", "CottageWindow"]:
		(harbor.find_child(glass, true, false) as GeometryInstance3D).cast_shadow = \
			GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lantern_noise.seed = SEED
	lantern_noise.frequency = 1.0
	var to_cam := camera.global_position - rotor.global_position
	beam_yaw0 = atan2(-to_cam.x, -to_cam.z) - TAU * BEAM_FACING_T / BEAM_PERIOD

	for a in ["Idle", "Walk"]:
		player.get_animation(a).loop_mode = Animation.LOOP_LINEAR
	player.play("Walk")
	player.speed_scale = WALK_RATE
	player.advance(0.0)                # Pose sofort setzen, sonst zeigt das erste Bild noch die Ruhepose
	badger.position = Vector3(START_X, 0.0, PATH_Z)

	if mask:
		_apply_mask()
	if perf:
		RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)
	_update(0.0)


func _process(delta: float) -> void:
	t += delta
	frame += 1
	var t_us := Time.get_ticks_usec()
	_update(delta)
	if perf:
		perf_script.append((Time.get_ticks_usec() - t_us) / 1000.0)
	if measure:
		_print_measure()
	if perf and frame > 10:
		var rid := get_viewport().get_viewport_rid()
		perf_gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(rid))
		perf_cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(rid))
		perf_ticks.append(Time.get_ticks_usec())


func _exit_tree() -> void:
	if perf and perf_gpu.size() > 0:
		var g := 0.0
		var c := 0.0
		for v in perf_gpu:
			g += v
		for v in perf_cpu:
			c += v
		# Bildzeit aus der Wanduhr (ohne V-Sync starten: --disable-vsync --max-fps 0); Median der Abstände
		var dts: Array[float] = []
		for i in range(1, perf_ticks.size()):
			dts.append((perf_ticks[i] - perf_ticks[i - 1]) / 1000.0)
		dts.sort()
		var sc := 0.0
		for v in perf_script:
			sc += v
		print("PERF sea_vertices=%d sea_triangles=%d script_ms=%.3f" % [
			(sea.mesh as ArrayMesh).surface_get_array_len(0) if sea.mesh else 0,
			(sea.mesh as ArrayMesh).surface_get_array_index_len(0) / 3 if sea.mesh else 0, sc / perf_script.size()])
		print("PERF variant=%s static=%s frames=%d frame_ms_median=%.3f gpu_ms=%.3f cpu_ms=%.3f prims=%d draws=%d" % [
			variant if variant else "full", static_mode, perf_gpu.size(), dts[dts.size() / 2], g / perf_gpu.size(), c / perf_cpu.size(),
			Performance.get_monitor(Performance.RENDER_TOTAL_PRIMITIVES_IN_FRAME),
			Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)])


func _update(delta: float) -> void:
	var ts := 0.0 if static_mode else t
	for m in time_mats:
		m.set_shader_parameter("time_s", ts)
	waves.set_time(sea_material, ts)
	flag_material.set_shader_parameter("frame_pos", fposmod(ts * FLAG_FPS, FLAG_FRAMES))
	_update_floaters(delta, ts)
	_update_pennants()
	_update_gulls(ts)
	_update_badger(delta)

	# Laterne flackert (Rauschen mit festem Seed); Glas und Licht gemeinsam.
	var f := 0.82 + 0.18 * lantern_noise.get_noise_1d(t * 7.0) + 0.06 * lantern_noise.get_noise_1d(t * 31.0 + 50.0)
	lantern_omni.light_energy = 1.6 * f
	lantern_mat.emission_energy_multiplier = 4.0 * f

	# Leuchtfeuer dreht sich; Lampe blitzt auf, wenn der Strahl zur Kamera zeigt.
	rotor.rotation.y = beam_yaw0 + TAU * t / BEAM_PERIOD
	var beam_dir := -rotor.global_basis.z
	var to_cam := (camera.global_position - rotor.global_position).normalized()
	var facing := pow(maxf(beam_dir.dot(Vector3(to_cam.x, 0.0, to_cam.z).normalized()), 0.0), 24.0)
	lamp_mat.emission_energy_multiplier = 4.0 + 26.0 * facing
	lamp_omni.light_energy = 2.0 + 4.0 * facing

	if ui and ui.has_method("set_rows"):
		var rows: Array[float] = []
		for p in gull_paths:
			rows.append(fposmod(ts * float(p.rate) + float(p.phase), 1.0))
		ui.set_rows(fposmod(ts * FLAG_FPS, FLAG_FRAMES) / FLAG_FRAMES, rows)


# --- Meer ------------------------------------------------------------------------------------------
func _build_sea() -> void:
	var old := harbor.get_node("Sea") as MeshInstance3D
	waves.apply(sea_material)
	if variant == "flat":
		sea_material.set_shader_parameter("wave_count", 0)
	if variant == "coarse":
		# Vergleich: Gerstner auf dem groben Gitter aus harbor.glb
		sea.visible = false
		old.material_override = sea_material
		old.extra_cull_margin = 1.0
		return
	old.visible = false
	sea.mesh = SeaMesh.build()
	sea.material_override = sea_material
	sea.position = Vector3(0.0, -0.8, 0.0)       # Wasserlinie wie Sea in harbor.glb


# --- Schwimmende Dinge -----------------------------------------------------------------------------
## Ein Schwimmer folgt der Wasseroberfläche: Höhe an vier Punkten (Bug, Heck, beide Seiten) aus
## waves.surface_at(), daraus Hub, Stampfen und Rollen; eine gedämpfte Feder gibt Trägheit.
func _add_floater(node: Node3D, half_len: float, half_wid: float, omega: float, sway: float, base_y: float) -> void:
	floaters.append({
		"node": node, "rest": node.transform, "hl": half_len, "hw": half_wid, "omega": omega, "sway": sway,
		"base_y": base_y, "x": Vector3.ZERO, "v": Vector3.ZERO, "init": false,
	})


func _build_floaters() -> void:
	# Boote: Ursprung auf der Wasserlinie, Bug lokal +x (harbor_notes.md)
	_add_floater(harbor.get_node("BoatA"), 1.9, 0.75, 3.2, 0.35, 0.0)
	_add_floater(harbor.get_node("BoatB"), 1.7, 0.65, 3.6, 0.4, 0.0)
	# Treibfässer: Kopien von Barrel1 (Ursprung am Boden, 0,9 m hoch); liegend, halb eingetaucht
	var barrel := harbor.get_node("Barrel1") as MeshInstance3D
	var spots := [[Vector3(-4.0, -0.8, -7.0), 35.0, 0.0], [Vector3(-3.0, -0.8, -11.0), -60.0, 90.0]]
	for s in spots:
		var holder := Node3D.new()
		holder.name = "DriftBarrel"
		add_child(holder)
		holder.transform = Transform3D(Basis.from_euler(Vector3(0.0, deg_to_rad(s[1]), 0.0)), s[0])
		var mi := MeshInstance3D.new()
		mi.mesh = barrel.mesh           # dieselbe Mesh-Ressource samt Materialien (Wood, Metal)
		# liegend: Fassachse (lokal y) nach x; Mitte 0,45 m über dem Ursprung, Mitte knapp unter Wasser
		mi.transform = Transform3D(Basis.from_euler(Vector3(0.0, 0.0, deg_to_rad(90.0))), Vector3(0.45, -0.12, 0.0))
		if s[2] != 0.0:  # stehendes Fass
			mi.transform = Transform3D(Basis.IDENTITY, Vector3(0.0, -0.62, 0.0))
		holder.add_child(mi)
		_add_floater(holder, 0.42, 0.32, 6.0, 0.9, 0.0)
	# Boje: rot-weiß, aus Grundformen
	var buoy := Node3D.new()
	buoy.name = "Buoy"
	add_child(buoy)
	buoy.position = Vector3(5.4, -0.8, -13.0)
	var red := StandardMaterial3D.new()
	red.albedo_color = Color("b02a22")
	red.roughness = 0.55
	var white := StandardMaterial3D.new()
	white.albedo_color = Color("e8e4da")
	white.roughness = 0.6
	var parts := [[0.36, 0.42, 0.5, -0.12, red], [0.06, 0.25, 0.55, 0.38, white], [0.0, 0.07, 0.22, 0.75, red]]
	for p in parts:
		var cm := CylinderMesh.new()
		cm.top_radius = p[0]
		cm.bottom_radius = p[1]
		cm.height = p[2]
		cm.radial_segments = 16
		var mi := MeshInstance3D.new()
		mi.mesh = cm
		mi.material_override = p[4]
		mi.position.y = p[3]
		buoy.add_child(mi)
	_add_floater(buoy, 0.35, 0.35, 5.0, 0.9, 0.0)


func _update_floaters(delta: float, ts: float) -> void:
	for f in floaters:
		var rest: Transform3D = f.rest
		var b := rest.basis.orthonormalized()
		var o := rest.origin
		var hl: float = f.hl
		var hw: float = f.hw
		var pts := [Vector3(hl, 0, 0), Vector3(-hl, 0, 0), Vector3(0, 0, hw), Vector3(0, 0, -hw)]
		var h: Array[float] = []
		for p in pts:
			var w: Vector3 = o + b * p
			h.append(waves.surface_at(w.x, w.z, ts).y)
		var c := waves.surface_at(o.x, o.z, ts)
		var target := Vector3(0.5 * c.y + 0.125 * (h[0] + h[1] + h[2] + h[3]),
			atan2(h[0] - h[1], 2.0 * hl), -atan2(h[2] - h[3], 2.0 * hw))
		if not f.init or delta <= 0.0:
			f.x = target
			f.v = Vector3.ZERO
			f.init = true
		else:
			# gedämpfte Feder (ζ = 0,7), halbimplizit; feste Schrittweite bei der Aufnahme
			var w0: float = f.omega
			var acc: Vector3 = (target - f.x) * w0 * w0 - f.v * (2.0 * 0.7 * w0)
			f.v += acc * delta
			f.x += f.v * delta
		var x: Vector3 = f.x
		var sway: float = f.sway
		var node: Node3D = f.node
		node.transform = Transform3D(rest.basis * Basis.from_euler(Vector3(x.z, 0.0, x.y)),
			o + Vector3(c.x * sway, x.x + float(f.base_y), c.z * sway))


# --- Fahne (VAT) -----------------------------------------------------------------------------------
func _build_flag() -> void:
	var root := Node3D.new()
	root.name = "FlagPole"
	add_child(root)
	root.position = FLAG_POLE
	var wood := find_material(harbor, "WhitePaint") as StandardMaterial3D
	var metal := find_material(harbor, "Metal")
	var stone := find_material(harbor, "StoneDark")
	var pole := CylinderMesh.new()
	pole.top_radius = 0.035
	pole.bottom_radius = 0.05
	pole.height = POLE_H
	pole.radial_segments = 12
	var pmi := MeshInstance3D.new()
	pmi.mesh = pole
	pmi.material_override = wood
	pmi.position.y = POLE_H * 0.5
	root.add_child(pmi)
	var knob := SphereMesh.new()
	knob.radius = 0.06
	knob.height = 0.12
	var kmi := MeshInstance3D.new()
	kmi.mesh = knob
	kmi.material_override = metal
	kmi.position.y = POLE_H + 0.05
	root.add_child(kmi)
	var foot := BoxMesh.new()
	foot.size = Vector3(0.36, 0.22, 0.36)
	var fmi := MeshInstance3D.new()
	fmi.mesh = foot
	fmi.material_override = stone
	fmi.position.y = 0.11
	root.add_child(fmi)

	var flag_scene := (load("res://models/flag.glb") as PackedScene).instantiate() as Node3D
	var holder := Node3D.new()
	holder.name = "FlagHolder"
	root.add_child(holder)
	# Fahne weht nach +x (Blender-Wind); Halter so drehen, dass +x in Windrichtung zeigt
	holder.position = Vector3(0.04, POLE_H - 0.12, 0.0)
	holder.rotation.y = atan2(-WIND.z, WIND.x)
	holder.add_child(flag_scene)
	var mi := flag_scene.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D
	mi.material_override = flag_material
	mi.extra_cull_margin = 1.6         # Ruhelage ist flach; die Simulation weicht bis 1,5 m davon ab


# --- Fischernetz (Shader) --------------------------------------------------------------------------
func _build_net() -> void:
	var root := Node3D.new()
	root.name = "NetRack"
	add_child(root)
	var wood := find_material(harbor, "WoodDark")
	for x in [NET_X.x, NET_X.y]:
		var post := BoxMesh.new()
		post.size = Vector3(0.1, NET_TOP + 0.12, 0.1)
		var mi := MeshInstance3D.new()
		mi.mesh = post
		mi.material_override = wood
		mi.position = Vector3(x, (NET_TOP + 0.12) * 0.5, NET_Z)
		root.add_child(mi)
	var bar := CylinderMesh.new()
	bar.top_radius = 0.035
	bar.bottom_radius = 0.035
	bar.height = NET_X.y - NET_X.x + 0.3
	var bmi := MeshInstance3D.new()
	bmi.mesh = bar
	bmi.material_override = wood
	bmi.transform = Transform3D(Basis.from_euler(Vector3(0, 0, PI / 2)), Vector3((NET_X.x + NET_X.y) * 0.5, NET_TOP, NET_Z))
	root.add_child(bmi)

	# Netz: Gitter in der lokalen x/y-Ebene, Oberkante bei y = 0 (an der Stange), hängt nach unten
	var w := NET_X.y - NET_X.x - 0.14
	var nx := 36
	var ny := 30
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for j in ny + 1:
		for i in nx + 1:
			var u := float(i) / nx
			var v := float(j) / ny
			# gerafft an der Stange: senkrechte Falten, nach unten weiter; Unterkante leicht durchhängend
			var fold := 0.035 * sin(u * TAU * 5.0) * (0.3 + 0.7 * v)
			var sag := 0.06 * sin(u * PI) * v
			st.set_uv(Vector2(u * w, v * NET_DROP))
			st.set_normal(Vector3(0, 0, 1))
			st.add_vertex(Vector3(u * w, -v * NET_DROP - sag, fold))
	for j in ny:
		for i in nx:
			var a := j * (nx + 1) + i
			st.add_index(a)
			st.add_index(a + 1)
			st.add_index(a + nx + 1)
			st.add_index(a + 1)
			st.add_index(a + nx + 2)
			st.add_index(a + nx + 1)
	var net := MeshInstance3D.new()
	net.name = "Net"
	net.mesh = st.commit()
	net.position = Vector3(NET_X.x + 0.07, NET_TOP - 0.03, NET_Z)
	net.extra_cull_margin = 1.0
	var m := ShaderMaterial.new()
	m.shader = flutter_shader
	m.set_shader_parameter("mode", 1)
	m.set_shader_parameter("wind_world", WIND)
	m.set_shader_parameter("length_m", NET_DROP)
	m.set_shader_parameter("weight_power", 1.5)
	m.set_shader_parameter("amp", 0.32)
	m.set_shader_parameter("noise_scale", 1.4)
	m.set_shader_parameter("noise_speed", 1.3)
	m.set_shader_parameter("seed", 3.0)
	m.set_shader_parameter("albedo", Color("b39a6c"))
	m.set_shader_parameter("albedo2", Color("6f5e40"))
	m.set_shader_parameter("mesh_size", 0.11)
	m.set_shader_parameter("twine", 0.14)
	net.material_override = m
	root.add_child(net)
	time_mats.append(m)
	# Korkschwimmer an der Oberleine
	var cork := StandardMaterial3D.new()
	cork.albedo_color = Color("c9a46a")
	cork.roughness = 0.9
	var cm := CylinderMesh.new()
	cm.top_radius = 0.045
	cm.bottom_radius = 0.045
	cm.height = 0.07
	for k in 7:
		var c := MeshInstance3D.new()
		c.mesh = cm
		c.material_override = cork
		c.transform = Transform3D(Basis.from_euler(Vector3(0, 0, PI / 2)),
			Vector3(NET_X.x + 0.16 + k * (w - 0.18) / 6.0, NET_TOP - 0.06, NET_Z + 0.03))
		root.add_child(c)


# --- Wimpel (Shader) -------------------------------------------------------------------------------
func _build_pennants() -> void:
	var specs := [["BoatA", Color("e2b84a"), Color("2f5a33"), 0.0], ["BoatB", Color("b02a22"), Color("e8e4da"), 2.0]]
	for s in specs:
		var boat := harbor.get_node(s[0]) as MeshInstance3D
		var top := _highest_point(boat)
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		var n := 20
		var length := 1.15
		for i in n + 1:
			var u := float(i) / n
			var hh := lerpf(0.15, 0.01, u)
			for j in 3:
				var v := float(j) / 2.0
				st.set_uv(Vector2(u, v))
				st.set_normal(Vector3(0, 0, 1))
				st.add_vertex(Vector3(u * length, hh * (1.0 - 2.0 * v) - 0.15, 0.0))
		for i in n:
			for j in 2:
				var a := i * 3 + j
				st.add_index(a)
				st.add_index(a + 3)
				st.add_index(a + 1)
				st.add_index(a + 3)
				st.add_index(a + 4)
				st.add_index(a + 1)
		var holder := Node3D.new()
		holder.name = "Pennant"
		boat.add_child(holder)
		holder.position = top + Vector3(0.0, -0.02, 0.0)
		var mi := MeshInstance3D.new()
		mi.mesh = st.commit()
		mi.extra_cull_margin = 0.5
		var m := ShaderMaterial.new()
		m.shader = flutter_shader
		m.set_shader_parameter("mode", 0)
		m.set_shader_parameter("wind_world", WIND)
		m.set_shader_parameter("length_m", length)
		m.set_shader_parameter("weight_power", 1.1)
		m.set_shader_parameter("amp", 0.09)
		m.set_shader_parameter("wave_len", 0.6)
		m.set_shader_parameter("wave_speed", 11.0)
		m.set_shader_parameter("seed", s[3])
		m.set_shader_parameter("albedo", s[1])
		m.set_shader_parameter("albedo2", s[2])
		mi.material_override = m
		holder.add_child(mi)
		pennants.append(holder)
		time_mats.append(m)


## Höchster Punkt eines Meshes in dessen lokalen Koordinaten (Mastspitze).
func _highest_point(mi: MeshInstance3D) -> Vector3:
	var best := Vector3(0, -INF, 0)
	for v in mi.mesh.get_faces():
		if v.y > best.y:
			best = v
	return best


func _update_pennants() -> void:
	# Wimpel stehen im Wind: Halter in Weltrichtung drehen, Lage des Bootes (Rollen) bleibt
	var yaw := atan2(-WIND.z, WIND.x)
	for p in pennants:
		var up := (p.get_parent() as Node3D).global_basis.y.normalized()
		var fwd := Vector3(cos(yaw), 0.0, -sin(yaw))
		fwd = (fwd - up * fwd.dot(up)).normalized()
		var side := fwd.cross(up).normalized()
		p.global_basis = Basis(fwd, up, side)


# --- Möwen (MultiMesh + VAT) -----------------------------------------------------------------------
func _build_gulls() -> void:
	var scene := (load("res://models/gull.glb") as PackedScene).instantiate() as Node3D
	var mesh := (scene.find_children("*", "MeshInstance3D", true, false)[0] as MeshInstance3D).mesh
	scene.free()
	gull_mm = MultiMesh.new()
	gull_mm.transform_format = MultiMesh.TRANSFORM_3D
	gull_mm.use_custom_data = true
	gull_mm.use_colors = true          # Compatibility-Renderer: ohne Instanzfarbe wird COLOR schwarz
	gull_mm.instance_count = GULLS
	for i in GULLS:
		gull_mm.set_instance_color(i, Color.WHITE)
	gull_mm.mesh = mesh
	var mmi := $Gulls as MultiMeshInstance3D
	mmi.multimesh = gull_mm
	mmi.material_override = gull_material
	mmi.extra_cull_margin = 1.0
	var rng := RandomNumberGenerator.new()
	rng.seed = SEED
	for i in GULLS:
		var cw := 1.0 if i % 3 != 0 else -1.0
		gull_paths.append({
			"c": Vector3(rng.randf_range(-2.5, 5.0), rng.randf_range(5.8, 9.0), rng.randf_range(-11.0, -3.5)),
			"r": rng.randf_range(2.5, 5.5), "speed": rng.randf_range(3.4, 4.8) * cw,
			"a0": rng.randf_range(0.0, TAU), "bob": rng.randf_range(0.2, 0.6), "bob_f": rng.randf_range(0.15, 0.3),
			"phase": rng.randf(), "rate": rng.randf_range(2.4, 3.2), "glide": rng.randf_range(0.0, TAU),
		})


func _gull_xform(p: Dictionary, ts: float) -> Transform3D:
	var r: float = p.r
	var a: float = float(p.a0) + float(p.speed) / r * ts
	var c: Vector3 = p.c
	var pos := c + Vector3(r * cos(a), float(p.bob) * sin(TAU * float(p.bob_f) * ts + float(p.a0)), r * sin(a))
	var sgn := signf(float(p.speed))
	var fwd := Vector3(-sin(a), 0.0, cos(a)) * sgn
	var bank := atan(float(p.speed) * float(p.speed) / (9.81 * r)) * 0.8
	var inward := Vector3(-cos(a), 0.0, -sin(a))
	var up := (Vector3.UP * cos(bank) + inward * sin(bank)).normalized()    # in die Kurve legen
	# Möwe blickt lokal nach -z
	var b := Basis.looking_at(fwd, up)
	return Transform3D(b, pos)


func _update_gulls(ts: float) -> void:
	for i in gull_paths.size():
		var p := gull_paths[i]
		gull_mm.set_instance_transform(i, _gull_xform(p, ts))
		# Wechsel zwischen Schlagen und Gleiten (langsam, je Möwe versetzt)
		var g := 0.5 + 0.5 * sin(0.5 * ts + float(p.glide))
		var amp := lerpf(0.12, 1.0, smoothstep(0.25, 0.75, g))
		var cycle := fposmod(float(p.phase) + ts * float(p.rate), 1.0)
		gull_mm.set_instance_custom_data(i, Color(cycle, float(p.rate), amp, 0.0))


# --- Dachs -----------------------------------------------------------------------------------------
func _update_badger(delta: float) -> void:
	if phase == 0:
		walk_rate = WALK_RATE * (1.0 - smoothstep(BRAKE_T, BRAKE_T + BRAKE_TIME, t))
		player.speed_scale = walk_rate
		# Vorschub entlang der Blickrichtung (Figur blickt lokal nach +x), passend zum Laufzyklus
		var yaw := badger.rotation.y
		badger.position += Vector3(cos(yaw), 0.0, -sin(yaw)) * WALK_SPEED * walk_rate * delta
		# Abbiegen: um den aufgesetzten Fuß drehen, damit er nicht über den Boden rutscht
		var new_yaw := -PI / 2.0 * smoothstep(TURN_T, TURN_T + TURN_TIME, t)
		var dyaw := new_yaw - yaw
		if absf(dyaw) > 0.0:
			var pivot := _planted_foot()
			var rel := (badger.position - pivot).rotated(Vector3.UP, dyaw)
			badger.position = pivot + rel
			badger.rotation.y = new_yaw
		if t >= IDLE_T:
			phase = 1
			player.speed_scale = 1.0
			player.play("Idle", 0.3)
	elif phase == 1 and t >= WAVE_T:
		phase = 2
		player.play("Wave", 0.25)
	elif phase == 2 and t >= WAVE_T + WAVE_LEN - 0.1:
		phase = 3
		player.play("Idle", 0.3)


## Mitte des tieferen Fußes (Knöchel bis Zehe) auf dem Boden, aus der Pose des letzten Bildes.
func _planted_foot() -> Vector3:
	var sk := badger.find_child("Skeleton3D", true, false) as Skeleton3D
	var best := Vector3.ZERO
	var best_y := INF
	for bn in ["foot.L", "foot.R"]:
		var gp := sk.global_transform * sk.get_bone_global_pose(sk.find_bone(bn))
		var toe := gp.origin + gp.basis.y.normalized() * 0.128
		if toe.y < best_y:
			best_y = toe.y
			best = (gp.origin + toe) * 0.5
	best.y = badger.position.y
	return best


func _print_measure() -> void:
	var sk := badger.find_child("Skeleton3D", true, false) as Skeleton3D
	var vals: Array[String] = []
	for bn in ["foot.L", "foot.R", "head"]:
		var i := sk.find_bone(bn)
		var gp := sk.global_transform * sk.get_bone_global_pose(i)
		var pts := [gp.origin]
		if bn == "head":
			pts = [gp.origin + gp.basis.y.normalized() * 0.2]
		else:
			pts.append(gp.origin + gp.basis.y.normalized() * 0.128)
		for p: Vector3 in pts:
			var s := camera.unproject_position(p)
			vals.append("%.5f %.5f %.5f %.2f %.2f" % [p.x, p.y, p.z, s.x, s.y])
	print("M %d %.4f %d %.3f %s" % [frame, t, phase, walk_rate, " ".join(vals)])


func _apply_mask() -> void:
	var white := StandardMaterial3D.new()
	white.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	white.albedo_color = Color.WHITE
	for mi: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
		mi.material_override = white
	for n in get_children():
		if n is Node3D and n != badger and n != camera:
			(n as Node3D).visible = false
	$WorldEnvironment.environment = Environment.new()
	$WorldEnvironment.environment.background_mode = Environment.BG_COLOR
	$WorldEnvironment.environment.background_color = Color.BLACK
	ui.visible = false
	($Sun as DirectionalLight3D).visible = false


# --- Lichter an die Empties hängen (Muster aus shared/3d/demo) --------------------------------------
func _attach_to_empties() -> void:
	for holder in $Attach.get_children():
		var target := harbor.find_child(holder.name, true, false) as Node3D
		if target == null:
			push_error("Ziel %s fehlt in harbor.glb" % holder.name)
			continue
		for c in holder.get_children():
			c.reparent(target, false)


# --- Materialien nach Namen ------------------------------------------------------------------------
static func find_material(root: Node, mat_name: String) -> Material:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for i in mi.mesh.get_surface_count():
			var m := mi.mesh.surface_get_material(i)
			if m and m.resource_name == mat_name:
				return m
	return null


static func unique_material(mi: MeshInstance3D) -> StandardMaterial3D:
	var m := (mi.mesh.surface_get_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
	mi.set_surface_override_material(0, m)
	return m
