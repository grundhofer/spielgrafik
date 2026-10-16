extends Node3D
## Standalone HD fixed-camera scene. Time and animation poses depend only on frame number.
const WALK_SPEED := 0.367
const WALK_RATE := 2.0
const BRAKE_TIME := 0.45
const CORNER_R := 0.8
const CUT_T := 2.1
const TURN_TIME := 0.5
const WAVE_LEN := 1.5
const SEED := 20261010
const SMOKE_PUFFS := 9
const SMOKE_LIFE := 6.0
var t := 0.0
var frame := -1
var t0 := 0.0
var fixed_t := -1.0
var flags := {}
var shots := {}
var cur := ""
var path: Array[Vector2] = []
var path_s: Array[float] = []
var path_len := 0.0
var brake_t := 0.0
var stop_t := 0.0
var wave_t := 0.0
var face_cam_yaw := 0.0
var stop_yaw := 0.0
var foot_bones := []
var smoke: Array[MeshInstance3D] = []
var smoke_jitter: Array[Vector3] = []
var rotor := Node3D.new()
var lantern_noise := FastNoiseLite.new()
@onready var camera: Camera3D = $Camera
@onready var bg_mat: ShaderMaterial = $Camera/Background.get_surface_override_material(0)
@onready var badger: Node3D = $Badger
@onready var player: AnimationPlayer = $Badger/AnimationPlayer
@onready var skel: Skeleton3D = $Badger.find_child("Skeleton3D", true, false)
@onready var ui: Control = $UI/Box

func _ready() -> void:
    for arg in OS.get_cmdline_user_args():
        if arg.begins_with("--shot="):
            flags["shot"] = arg.substr(7)
        elif arg.begins_with("--t0="):
            t0 = float(arg.substr(5))
        elif arg.begins_with("--at="):
            fixed_t = float(arg.substr(5))
        else:
            flags[arg.trim_prefix("--")] = true
    var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://shots.json"))
    _build_path(data["path"])
    for name in ["totale", "nah"]:
        var folder := "res://bg/%s/" % name
        shots[name] = {"camera": JSON.parse_string(FileAccess.get_file_as_string(folder + "camera.json")),
            "base": load(folder + "base.exr"), "depth": load(folder + "depth.png")}
    bg_mat.set_shader_parameter("use_depth", not flags.has("no-depth"))
    bg_mat.set_shader_parameter("key_mode", flags.has("key"))
    ui.visible = not (flags.has("key") or flags.has("no-ui"))
    badger.visible = not flags.has("only-bg")
    var env: Environment = $WorldEnvironment.environment
    env.tonemap_mode = Environment.TONE_MAPPER_AGX
    var sky := Sky.new()
    sky.radiance_size = Sky.RADIANCE_SIZE_256
    var panorama := PanoramaSkyMaterial.new()
    panorama.panorama = load("res://bg/panorama.exr")
    sky.sky_material = panorama
    env.sky = sky
    env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
    env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
    if flags.has("no-panorama"):
        env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
        env.ambient_light_color = Color.BLACK
        env.reflected_light_source = Environment.REFLECTION_SOURCE_DISABLED
    # Exact geometry remains as invisible shadow proxies. Only the quay draws shadow opacity.
    var catcher := ShaderMaterial.new()
    catcher.shader = preload("res://shaders/catcher.gdshader")
    for mesh: MeshInstance3D in $Proxy.find_children("*", "MeshInstance3D", true, false):
        if mesh.name == "Quay":
            mesh.layers = 4
            mesh.material_override = catcher
            mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
            mesh.position.y += 0.012
            mesh.visible = not (flags.has("no-catcher") or flags.has("key"))
        elif mesh.name in ["CottageWindow", "LanternGlass", "LighthouseLamp", "Sea"]:
            mesh.visible = false
        else:
            mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
    ($Dusk as Node3D).basis = Basis.looking_at(Vector3(-0.25, -0.06, 1.0).normalized(), Vector3.UP)
    for mesh: MeshInstance3D in badger.find_children("*", "MeshInstance3D", true, false):
        mesh.layers = 2
        for i in mesh.mesh.get_surface_count():
            var src := mesh.mesh.surface_get_material(i) as StandardMaterial3D
            var material := src.duplicate() as StandardMaterial3D
            var texture_name := ""
            if src.resource_name in ["Vest", "Cap", "Shirt"]:
                texture_name = "cloth"
                material.roughness = 0.85
            elif src.resource_name == "Scarf":
                texture_name = "knit"
                material.roughness = 0.95
            elif src.resource_name == "Satchel":
                texture_name = "leather"
                material.roughness = 0.6
            elif src.resource_name in ["Eye", "Nose"]:
                material.roughness = 0.2
            if not texture_name.is_empty():
                material.albedo_texture = load("res://textures/%s.png" % texture_name)
                material.normal_enabled = true
                material.normal_texture = load("res://textures/%s_normal.png" % texture_name)
                material.normal_scale = 0.35
                material.uv1_scale = Vector3(4, 4, 4)
            mesh.set_surface_override_material(i, material)
    for light: Light3D in [$Dusk, $WindowSide, $WindowFront, $Lantern]:
        light.light_cull_mask = 2
        light.shadow_caster_mask = 3
    # Receiver-only sun: catches the character, without duplicating the environment's baked shadows.
    var shadow_sun := DirectionalLight3D.new()
    shadow_sun.name = "CatcherSun"
    shadow_sun.light_cull_mask = 4
    shadow_sun.shadow_caster_mask = 2
    shadow_sun.light_energy = 1.5
    shadow_sun.shadow_enabled = true
    shadow_sun.directional_shadow_max_distance = 60
    add_child(shadow_sun)
    shadow_sun.basis = $Dusk.basis
    for name in ["Idle", "Walk"]:
        player.get_animation(name).loop_mode = Animation.LOOP_LINEAR
    player.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
    brake_t = path_len / (WALK_SPEED * WALK_RATE) - BRAKE_TIME * 0.5
    stop_t = brake_t + BRAKE_TIME
    wave_t = stop_t + 0.1 + TURN_TIME + 0.05
    lantern_noise.seed = SEED
    lantern_noise.frequency = 1.0
    for bone in ["foot.L", "foot.R"]:
        var bi := skel.find_bone(bone)
        var rest := skel.get_bone_global_rest(bi)
        foot_bones.append([bi, rest.affine_inverse() * (rest.origin + Vector3(0.07, -0.062, 0))])
    _build_smoke()
    _build_beam()
    _set_shot(flags.get("shot", "totale"))
    _update()

func _process(_delta: float) -> void:
    frame += 1
    t = fixed_t if fixed_t >= 0 else t0 + float(frame) / 30.0
    _update()

func _update() -> void:
    var want: String = flags.get("shot", "totale" if t < CUT_T else "nah")
    if want != cur:
        _set_shot(want)
    _update_badger()
    if not flags.has("no-anim"):
        _update_smoke()
        rotor.rotation.y = TAU * (t - 1.0) / 6.0
    $Lantern.light_energy = 1.6 * (0.8 + 0.4 * lantern_noise.get_noise_1d(t * 6.0))
    ui.set("t", t)
    ui.set("shot", cur)
    ui.queue_redraw()
    if flags.has("feet-log"):
        _log_feet()

func _set_shot(name: String) -> void:
    cur = name
    var cam: Dictionary = shots[name]["camera"]
    var c: Array = cam["basis_columns"]
    var o: Array = cam["origin"]
    camera.transform = Transform3D(Basis(Vector3(c[0][0], c[0][1], c[0][2]),
        Vector3(c[1][0], c[1][1], c[1][2]), Vector3(c[2][0], c[2][1], c[2][2])), Vector3(o[0], o[1], o[2]))
    camera.fov = float(cam["fov"])
    bg_mat.set_shader_parameter("base_tex", shots[name]["base"])
    bg_mat.set_shader_parameter("depth_tex", shots[name]["depth"])
    var nah: Array = shots["nah"]["camera"]["origin"]
    var end := path[path.size() - 1]
    face_cam_yaw = atan2(-(float(nah[2]) - end.y), float(nah[0]) - end.x)

func _update_badger() -> void:
    var u := clampf((t - brake_t) / BRAKE_TIME, 0.0, 1.0)
    var progress := minf(t, brake_t) + BRAKE_TIME * (u - u * u * u + 0.5 * pow(u, 4))
    var distance := minf(WALK_SPEED * WALK_RATE * progress, path_len)
    var pd := _path_at(distance)
    var pos: Vector2 = pd[0]
    var dir: Vector2 = pd[1]
    badger.position = Vector3(pos.x, 0.012, pos.y)
    var yaw := atan2(-dir.y, dir.x)
    if t < stop_t:
        stop_yaw = yaw
        badger.rotation.y = yaw
        player.play("Walk")
        player.seek(progress * WALK_RATE, true)
    else:
        var final: Vector2 = _path_at(path_len)[1]
        stop_yaw = atan2(-final.y, final.x)
        badger.rotation.y = lerp_angle(stop_yaw, face_cam_yaw, smoothstep(stop_t + 0.1, stop_t + 0.6, t))
        if t >= wave_t and t < wave_t + WAVE_LEN:
            player.play("Wave")
            player.seek(t - wave_t, true)
        else:
            player.play("Idle")
            player.seek(fposmod(t - stop_t, 2.0), true)

func _build_beam() -> void:
    add_child(rotor)
    rotor.position = ($Proxy.find_child("LighthouseLight", true, false) as Node3D).global_position
    var mesh := CylinderMesh.new()
    mesh.top_radius = 3.2
    mesh.bottom_radius = 0.12
    mesh.height = 30.0
    mesh.cap_top = false
    mesh.cap_bottom = false
    var cone := MeshInstance3D.new()
    cone.mesh = mesh
    cone.rotation.x = -PI / 2
    cone.position.z = -15
    var mat := ShaderMaterial.new()
    mat.shader = preload("res://shaders/beam.gdshader")
    mat.set_shader_parameter("intensity", 0.13)
    cone.material_override = mat
    cone.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
    rotor.add_child(cone)
    rotor.visible = not (flags.has("key") or flags.has("no-anim"))

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


func _log_feet() -> void:
    var parts := ["t=%.4f" % t, "shot=" + cur]
    for fb in foot_bones:
        var bi: int = fb[0]
        var w: Vector3 = skel.global_transform * skel.get_bone_global_pose(bi) * (fb[1] as Vector3)
        var sp := camera.unproject_position(w)
        parts.append("%s=(%.4f,%.4f,%.4f)|(%.2f,%.2f)" % [skel.get_bone_name(bi), w.x, w.y, w.z, sp.x, sp.y])
    print("FEET ", " ".join(parts))

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
    var anchor := $Proxy.find_child("ChimneySmoke", true, false) as Node3D
    for i in SMOKE_PUFFS:
        var p := MeshInstance3D.new()
        p.mesh = quad
        p.material_override = mat
        p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
        anchor.add_child(p)
        p.visible = not (flags.has("key") or flags.has("no-anim"))
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
