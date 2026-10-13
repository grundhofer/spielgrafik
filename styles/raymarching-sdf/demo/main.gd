extends Node
## Raymarching-Demo „Hafen von Lornholm“ (Katalogeintrag raymarching-sdf).
##
## Die ganze Szene ist ein Fragment-Shader (shaders/harbor_sdf.gdshader) auf einem ColorRect im
## SubViewport "Render" (640×360). Dieses Skript rechnet nur Uniforms: Zeit, Kamera, Laterne,
## Leuchtfeuer und die Gelenkpunkte des Dachses (Schrittplan + Zwei-Knochen-IK). Alles hängt an
## der aufsummierten Zeit t; jeder Zeitpunkt ist eine reine Funktion von t (springen mit --start).
##
## Schalter nach "--":  --start S  (Zeit beim Start), --debug N (0 normal, 1 Schrittzahl,
## 2 ohne Volumen, 3 ohne Schatten/AO, 4 Messmaske Dachs, 5 ohne Sonnenschatten, 6 ohne AO,
## 8 Schattenwerfer), --steps N (Primärstrahl), --lite (sparsame Schrittzahlen), --bench (Bildzeit
## messen und beenden), --measure (Fuß- und Kopfpunkte je Bild als JSON-Zeilen ausgeben),
## --static-cam (Totale bleibt stehen), --cam px,py,pz,tx,ty,tz,fov (feste Kamera), --no-fxaa, --no-ui.

const RES := Vector2i(640, 360)
const BENCH_COPIES := 8

# Kamera: Totale wie shared/3d (Position, Ziel 3° nach unten, fov 42), dann Fahrt zur Halbnahen
const CAM_TOT_POS := Vector3(-1.8, 3.4, 14.5)
const CAM_TOT_TGT := Vector3(-1.8, 2.8759, 4.5137)
const CAM_TOT_FOV := 42.0
const CAM_NEAR_POS := Vector3(2.4, 1.0, 5.5)
const CAM_NEAR_TGT := Vector3(1.0, 2.4, -8.0)
const CAM_NEAR_FOV := 44.0
const CAM_MOVE := Vector2(1.0, 3.7)        # Beginn und Ende der Fahrt (s)

# Dachs: Weg auf z = 1,2 (Laufweg aus shared/3d), Gangart
const WALK_Z := 1.2
const V_WALK := 0.7                        # m/s
const STEP := 0.25                         # s zwischen zwei Aufsetzern (4 Schritte/s)
const SWING := 0.2                         # s Schwungphase je Fuß
const T_STOP := 3.0                        # Körper steht
const DECEL := 0.5                         # Bremsdauer (s)
const X_STOP := 0.7
const TURN := Vector2(3.05, 3.65)          # Drehung zur Kamera
const YAW_END := -1.3                      # rad; lokal +X zeigt dann fast nach +Z
const WAVE := Vector2(3.85, 5.95)          # Winken (Arm ab 5,6 s wieder unten)
const FOOT_SIDE := 0.11
const THIGH := 0.12
const SHIN := 0.12
const ANKLE_H := 0.065
const HIP_H := 0.292

const LAMP_P := Vector3(10.2, 12.58, -25.6)
const BEAM_W := 0.375                      # rad/s
const BEAM_YAW0 := -3.55

var t := 0.0
var frame := 0
var mat: ShaderMaterial
var noise := FastNoiseLite.new()
var steps_plan := []                       # [{t, foot (0 L, 1 R), pos: Vector3, yaw}]
var opts := {"start": 0.0, "debug": 0, "steps": 160, "bench": false, "measure": false, "static_cam": false, "cam": [], "no_fxaa": false, "lite": false, "no_ui": false}
var bench_acc := []
var bench_t0 := 0
var x0 := 0.0


func _ready() -> void:
	_parse_args()
	mat = $Render/Scene.material as ShaderMaterial
	($Display as TextureRect).texture = $Render.get_texture()
	(($Display as TextureRect).material as ShaderMaterial).set_shader_parameter("fxaa", not opts.no_fxaa and int(opts.debug) != 4)
	if int(opts.debug) in [1, 4, 8] or opts.no_ui:
		$UI.visible = false
	noise.seed = 4711
	noise.noise_type = FastNoiseLite.TYPE_SIMPLEX
	noise.frequency = 1.0
	# Startpunkt so, dass der Dachs bei T_STOP genau bei X_STOP steht
	x0 = X_STOP - (V_WALK * (T_STOP - DECEL) + V_WALK * DECEL * 0.5)
	_plan_steps()
	mat.set_shader_parameter("res", Vector2(RES))
	mat.set_shader_parameter("debug_mode", int(opts.debug))
	mat.set_shader_parameter("max_steps", int(opts.steps))
	if opts.lite:
		# sparsame Fassung (Vorschlag für Mobilgeräte): weniger Schritte, Spiegelung nur Himmel
		mat.set_shader_parameter("max_steps", 96)
		mat.set_shader_parameter("shadow_steps", 20)
		mat.set_shader_parameter("refl_steps", 0)
		mat.set_shader_parameter("vol_steps", 6)
		mat.set_shader_parameter("beam_steps", 8)
		mat.set_shader_parameter("cloud_steps", 10)
	t = float(opts.start)
	if opts.bench:
		DisplayServer.window_set_vsync_mode(DisplayServer.VSYNC_DISABLED)
		RenderingServer.viewport_set_measure_render_time($Render.get_viewport_rid(), true)
		Engine.max_fps = 0
		# Der Bildschirm begrenzt auf 120 Bilder/s; damit die Messung darüber hinaus reicht, rendert der
		# Shader je Bild BENCH_COPIES-mal (weitere SubViewports mit demselben Material).
		for k in BENCH_COPIES - 1:
			var vp := SubViewport.new()
			vp.size = RES
			vp.disable_3d = true
			vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
			var cr := ColorRect.new()
			cr.size = Vector2(RES)
			cr.material = mat
			vp.add_child(cr)
			add_child(vp)
	_update()


func _parse_args() -> void:
	var a := OS.get_cmdline_user_args()
	var i := 0
	while i < a.size():
		match a[i]:
			"--start":
				opts.start = float(a[i + 1]); i += 1
			"--debug":
				opts.debug = int(a[i + 1]); i += 1
			"--steps":
				opts.steps = int(a[i + 1]); i += 1
			"--bench":
				opts.bench = true
			"--measure":
				opts.measure = true
			"--static-cam":
				opts.static_cam = true
			"--no-fxaa":
				opts.no_fxaa = true
			"--lite":
				opts.lite = true
			"--no-ui":
				opts.no_ui = true
			"--cam":
				var c := a[i + 1].split(",")
				opts.cam = [Vector3(float(c[0]), float(c[1]), float(c[2])), Vector3(float(c[3]), float(c[4]), float(c[5])), float(c[6])]
				i += 1
		i += 1


func _process(delta: float) -> void:
	if not opts.bench:
		t += delta
	frame += 1
	_update()
	if opts.bench:
		# GPU-Zeit des SubViewports (falls der Treiber Zeitstempel liefert) und Bildzeit bei
		# abgeschaltetem VSync; die Szene steht still (t fest), gemessen werden Bilder 30 bis 330
		var gpu := RenderingServer.viewport_get_measured_render_time_gpu($Render.get_viewport_rid())
		if frame == 30:
			bench_t0 = Time.get_ticks_usec()
		if frame > 30:
			bench_acc.append(gpu)
		if frame == 330:
			var wall := (Time.get_ticks_usec() - bench_t0) / 1000.0 / 300.0
			bench_acc.sort()
			print("BENCH lite=%s t=%.2f steps=%d debug=%d copies=%d frame_ms=%.3f per_render_ms=%.3f gpu_ms_median=%.3f" % [
				str(opts.lite), t, int(mat.get_shader_parameter("max_steps")), int(opts.debug), BENCH_COPIES, wall, wall / BENCH_COPIES, bench_acc[bench_acc.size() / 2]])
			get_tree().quit()


# ---------------------------------------------------------------------------------------------
# Kamera
# ---------------------------------------------------------------------------------------------
func _ease(x: float) -> float:
	x = clampf(x, 0.0, 1.0)
	return x * x * x * (x * (x * 6.0 - 15.0) + 10.0)


func _camera(tt: float) -> Array:
	if not opts.cam.is_empty():
		return opts.cam
	var k := 0.0 if opts.static_cam else _ease((tt - CAM_MOVE.x) / (CAM_MOVE.y - CAM_MOVE.x))
	var pos := CAM_TOT_POS.lerp(CAM_NEAR_POS, k)
	var tgt := CAM_TOT_TGT.lerp(CAM_NEAR_TGT, k)
	# Ziel mit leichtem Bogen, damit die Fahrt nicht nur geradeaus zoomt
	var fov := lerpf(CAM_TOT_FOV, CAM_NEAR_FOV, k)
	# nach der Fahrt ganz leichtes Nachschweben
	var drift := clampf(tt - CAM_MOVE.y, 0.0, 3.0)
	pos += Vector3(0.025, 0.01, -0.02) * drift
	return [pos, tgt, fov]


# ---------------------------------------------------------------------------------------------
# Körperweg, Drehung und Schrittplan
# ---------------------------------------------------------------------------------------------
func _body_speed(tt: float) -> float:
	var t_dec := T_STOP - DECEL
	if tt < t_dec:
		return V_WALK
	if tt >= T_STOP:
		return 0.0
	var u := (tt - t_dec) / DECEL
	return V_WALK * (1.0 - u * u * (3.0 - 2.0 * u))


func _body_x(tt: float) -> float:
	var t_dec := T_STOP - DECEL
	if tt < t_dec:
		return x0 + V_WALK * tt
	var u := clampf((tt - t_dec) / DECEL, 0.0, 1.0)
	# Integral von V(1 − smoothstep(u)) = V·D·(u − u³ + u⁴/2)
	return x0 + V_WALK * t_dec + V_WALK * DECEL * (u - u * u * u + 0.5 * u * u * u * u)


func _body_yaw(tt: float) -> float:
	var u := clampf((tt - TURN.x) / (TURN.y - TURN.x), 0.0, 1.0)
	return YAW_END * u * u * (3.0 - 2.0 * u)


func _body_root(tt: float) -> Vector3:
	return Vector3(_body_x(tt), 0.0, WALK_Z)


func _foot_target(tt: float, foot: int) -> Dictionary:
	var yaw := _body_yaw(tt + 0.08)
	var lead := _body_speed(tt) * (2.0 * STEP - SWING) * 0.5
	var side := FOOT_SIDE if foot == 1 else -FOOT_SIDE
	var b := Basis(Vector3.UP, yaw)
	return {"pos": _body_root(tt) + b * Vector3(lead, 0.0, side), "yaw": yaw}


func _plan_steps() -> void:
	# Aufsetzer alle STEP Sekunden, abwechselnd rechts (gerade k) und links; vor t = 0 beginnen
	steps_plan.clear()
	var last := [{}, {}]
	var k := -6
	while true:
		var tl := 0.02 + k * STEP
		if tl > 8.0:
			break
		var foot := 1 if (k % 2 == 0) else 0
		var tgt := _foot_target(tl, foot)
		var moving := tl < T_STOP + 0.05 or (tl > TURN.x - 0.1 and tl < TURN.y + STEP * 2.0)
		var prev: Dictionary = last[foot]
		var need: bool = moving or prev.is_empty() or prev.pos.distance_to(tgt.pos) > 0.012 or absf(prev.yaw - tgt.yaw) > 0.05
		if need:
			var s := {"t": tl, "foot": foot, "pos": tgt.pos, "yaw": tgt.yaw}
			steps_plan.append(s)
			last[foot] = s
		k += 1


## Fußlage (Welt) und Hub zum Zeitpunkt tt
func _foot_state(tt: float, foot: int) -> Dictionary:
	var prev := {}
	var next := {}
	for s in steps_plan:
		if s.foot != foot:
			continue
		if s.t <= tt:
			prev = s
		elif next.is_empty():
			next = s
	if prev.is_empty():
		prev = next
	if next.is_empty() or tt < next.t - SWING:
		return {"pos": prev.pos, "yaw": prev.yaw, "lift": 0.0, "swing": false}
	var u := clampf((tt - (next.t - SWING)) / SWING, 0.0, 1.0)
	var e := u * u * (3.0 - 2.0 * u)
	var pos: Vector3 = prev.pos.lerp(next.pos, e)
	var lift := 0.065 * sin(PI * u) * clampf(prev.pos.distance_to(next.pos) / 0.12, 0.35, 1.0)
	return {"pos": pos, "yaw": lerpf(prev.yaw, next.yaw, e), "lift": lift, "swing": true}


func _ik(hip: Vector3, ankle: Vector3, fwd: Vector3) -> Vector3:
	var d := hip.distance_to(ankle)
	d = clampf(d, 0.05, THIGH + SHIN - 0.001)
	var dir := (ankle - hip).normalized()
	var a := (d * d + THIGH * THIGH - SHIN * SHIN) / (2.0 * d)
	var h := sqrt(maxf(THIGH * THIGH - a * a, 0.0))
	var perp := (fwd - dir * fwd.dot(dir)).normalized()
	return hip + dir * a + perp * h


# ---------------------------------------------------------------------------------------------
# Gelenkpunkte (lokaler Raum des Dachses: Blick +X, rechte Seite +Z, Ursprung am Boden)
# ---------------------------------------------------------------------------------------------
func _badger(tt: float) -> Dictionary:
	var root := _body_root(tt)
	var yaw := _body_yaw(tt)
	var binv := Basis(Vector3.UP, yaw).inverse()
	var vfac := _body_speed(tt) / V_WALK
	var turning := clampf(1.0 - absf((tt - (TURN.x + TURN.y) * 0.5) / ((TURN.y - TURN.x) * 0.5)), 0.0, 1.0)
	var gait := maxf(vfac, turning * 0.5)
	var ph := (tt - 0.02) / STEP                    # 0 bei jedem Aufsetzer
	var bob := 0.5 + 0.5 * cos(TAU * ph)
	var breathe := sin(TAU * tt / 2.2)
	var wave_k := _ease((tt - WAVE.x) / 0.35) * (1.0 - _ease((tt - WAVE.y + 0.35) / 0.35))

	var j := PackedVector3Array()
	j.resize(24)
	var sway := 0.014 * gait * sin(PI * ph)
	var pel := Vector3(0.0, HIP_H - 0.016 * gait * bob + 0.003 * breathe * (1.0 - gait), sway)
	var che := pel + Vector3(0.012 + 0.03 * vfac, 0.245 + 0.006 * breathe, -sway * 0.4)
	che.x -= 0.015 * wave_k
	var head := che + Vector3(0.04, 0.3, 0.0)
	j[0] = pel
	j[1] = che
	j[2] = head
	# Beine
	var feet := []
	for foot in [0, 1]:
		var fs := _foot_state(tt, foot)
		var side := FOOT_SIDE if foot == 1 else -FOOT_SIDE
		var hip := pel + Vector3(0.0, -0.02, side)
		var fpos: Vector3 = binv * (fs.pos - root)
		var fyaw: float = fs.yaw - yaw
		var ffwd := Vector3(cos(fyaw), 0.0, -sin(fyaw))
		var ankle := fpos + Vector3(0.0, ANKLE_H + fs.lift, 0.0) - ffwd * 0.01
		var knee := _ik(hip, ankle, ffwd)
		var toe := ankle + ffwd * 0.105 + Vector3(0.0, -0.04 - 0.02 * fs.lift / 0.065, 0.0)
		var o: int = 3 + foot * 4
		j[o] = hip
		j[o + 1] = knee
		j[o + 2] = ankle
		j[o + 3] = toe
		feet.append({"world": fs.pos, "lift": fs.lift, "swing": fs.swing})
	# linker Arm (frei): schwingt gegen das linke Bein, beim Winken hoch
	var sh_l := che + Vector3(-0.005, 0.06, -0.185)
	var swing_a := 0.55 * gait * sin(PI * (ph + 0.5))
	var el_l := sh_l + Vector3(sin(swing_a) * 0.14, -cos(swing_a) * 0.14, -0.035)
	var ha_l := el_l + Vector3(sin(swing_a + 0.35) * 0.13, -cos(swing_a + 0.35) * 0.13, -0.01)
	var wb := 0.45 * sin(TAU * (tt - WAVE.x) * 1.6)
	var el_w := sh_l + Vector3(0.04, 0.1, -0.12)
	var ha_w := el_w + Vector3(0.03, 0.15 * cos(wb - 0.2), -0.15 * sin(wb - 0.2))
	el_l = el_l.lerp(el_w, wave_k)
	ha_l = ha_l.lerp(ha_w, wave_k)
	j[11] = sh_l
	j[12] = el_l
	j[13] = ha_l
	# rechter Arm hält das Paket
	var sh_r := che + Vector3(-0.005, 0.06, 0.185)
	j[14] = sh_r
	j[15] = che + Vector3(-0.07, -0.07, 0.29)
	j[16] = che + Vector3(0.1, -0.15, 0.315)
	# Schal: vorderes Ende, hinteres Ende (Kontrollpunkt, Spitze)
	var flut := sin(TAU * tt * 1.7)
	j[17] = che + Vector3(0.13 + 0.015 * flut * gait, -0.21, 0.11)
	j[18] = che + Vector3(-0.17 - 0.03 * gait, 0.04 + 0.02 * gait, 0.09)
	j[19] = che + Vector3(-0.2 - 0.1 * gait, -0.15 + 0.07 * gait + 0.02 * flut, 0.09 + 0.02 * sin(TAU * tt * 1.3))
	# Schwanz, Paket (Mitte und Längsachse)
	j[20] = pel + Vector3(-0.27, -0.06, 0.03 * sin(TAU * tt * 2.0))
	j[21] = che + Vector3(0.03, -0.12, 0.255)
	j[22] = Vector3(1.0, 0.12, 0.0)
	j[23] = Vector3.ZERO
	# Kopf: nickt im Laufen, schaut nach der Drehung zur Kamera und neigt sich beim Winken
	var cam: Array = _camera(tt)
	var to_cam: Vector3 = binv * (cam[0] - (root + Basis(Vector3.UP, yaw) * head))
	var look := atan2(-to_cam.z, to_cam.x)
	var look_k := _ease((tt - TURN.x - 0.2) / 0.6)
	var hyaw := clampf(look, -0.6, 0.6) * look_k
	var hpitch := -0.04 * gait * cos(TAU * ph) + 0.05 * look_k + 0.02 * breathe
	var hroll := 0.12 * wave_k * sin(TAU * (tt - WAVE.x) * 0.8)
	var hb := Basis(Vector3.UP, hyaw) * Basis(Vector3(0, 0, 1), hpitch) * Basis(Vector3(1, 0, 0), hroll)
	return {"joints": j, "root": root, "yaw": yaw, "head_inv": hb.inverse(), "feet": feet, "head": head}


# ---------------------------------------------------------------------------------------------
func _update() -> void:
	var cam := _camera(t)
	mat.set_shader_parameter("t_sec", t)
	mat.set_shader_parameter("frame_no", float(frame % 64))
	mat.set_shader_parameter("cam_pos", cam[0])
	mat.set_shader_parameter("cam_tgt", cam[1])
	mat.set_shader_parameter("cam_fov", cam[2])
	# Laterne: Rauschen mit festem Seed, kurze Einbrüche
	var fl := 0.88 + 0.1 * noise.get_noise_1d(t * 9.0) + 0.06 * noise.get_noise_1d(t * 23.0 + 50.0)
	fl -= 0.25 * maxf(noise.get_noise_1d(t * 3.0 + 120.0) - 0.45, 0.0) * 4.0
	mat.set_shader_parameter("lantern_k", fl)
	# Leuchtfeuer dreht sich; Aufblitzen, wenn der Strahl waagerecht zur Kamera zeigt
	var by := BEAM_YAW0 + BEAM_W * t
	mat.set_shader_parameter("beam_yaw", by)
	var bdir := Vector3(sin(by), 0.0, cos(by))
	var to_cam: Vector3 = (cam[0] - LAMP_P)
	to_cam.y = 0.0
	var flash := pow(maxf(bdir.dot(to_cam.normalized()), 0.0), 60.0)
	mat.set_shader_parameter("lamp_flash", flash)
	# Dachs
	var b := _badger(t)
	mat.set_shader_parameter("b_pos", b.root)
	mat.set_shader_parameter("b_yaw", b.yaw)
	mat.set_shader_parameter("bj", b.joints)
	mat.set_shader_parameter("b_head_inv", b.head_inv)
	$UI.set_time(t)
	if opts.measure:
		var rec := {"frame": frame, "t": snappedf(t, 0.0001)}
		var bb := Basis(Vector3.UP, b.yaw)
		rec["feet"] = []
		for f in b.feet:
			rec["feet"].append([snappedf(f.world.x, 0.0001), snappedf(f.world.y + f.lift, 0.0001), snappedf(f.world.z, 0.0001), f.swing])
		var hw: Vector3 = b.root + bb * b.head
		rec["head"] = [snappedf(hw.x, 0.0001), snappedf(hw.y, 0.0001), snappedf(hw.z, 0.0001)]
		rec["cam"] = [cam[0].x, cam[0].y, cam[0].z, cam[1].x, cam[1].y, cam[1].z, cam[2]]
		print("MEASURE " + JSON.stringify(rec))
