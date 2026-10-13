extends Node2D
## Lebendes Porträt: Parameter wie in Live2D (Kopfwinkel, Atem, Augen, Mund) steuern Bone2D-Knoten
## eines Skeleton2D und die Lid-/Mund-Verformung im Kopf-Shader. Die Szene portrait.tscn erzeugt
## tools/prep.py aus dem KI-Porträt; dieses Skript ist für jede so erzeugte Figur gleich.

# Parameter, von außen gesetzt (z. B. main.gd); Bereich −1..1 bzw. 0..1
var angle_x := 0.0   # Kopf drehen (+ = zur rechten Bildseite)
var angle_y := 0.0   # nicken (+ = nach unten)
var angle_z := 0.0   # neigen (+ = im Uhrzeigersinn)
var body_x := 0.0    # Oberkörper wiegen
var breath := 0.0    # 0 = ausgeatmet, 1 = eingeatmet
var eye_l := 1.0     # 1 = offen, 0 = geschlossen
var eye_r := 1.0
var mouth := 0.0     # 0 = zu, 1 = weit offen (KI-Bearbeitung)
var ear_l := 0.0     # Ohrzucken −1..1
var ear_r := 0.0
var wind := 0.0      # seitliche Kraft auf das Schalende (Pixel/s² in Schalgröße)
var gaze := Vector2.ZERO  # Blickrichtung −1..1 (nur wenn die Augen Augenweiß haben)
const GAZE_PX := Vector2(3.0, 1.5)

# Ausschläge in Pixeln bzw. Grad bei Parameter 1
const FACE_SHIFT := Vector2(16.0, 9.0)   # Gesicht gegen Umriss (Parallaxe)
const HEAD_SHIFT := Vector2(4.0, 3.0)
const HEAD_TILT := 5.0
const NECK_TILT := 1.2
const EAR_SHIFT := Vector2(-5.0, -2.0)
const EAR_TWITCH := 9.0
const BODY_TILT := 0.9
const BODY_SHIFT := 3.0
const BREATH_LIFT := 2.4

@onready var bones := {
	"Huefte": $Skelett/Huefte, "Brust": $Skelett/Huefte/Brust, "Hals": $Skelett/Huefte/Brust/Hals,
	"Kopf": $Skelett/Huefte/Brust/Hals/Kopf, "Gesicht": $Skelett/Huefte/Brust/Hals/Kopf/Gesicht,
	"Ohr_L": $Skelett/Huefte/Brust/Hals/Kopf/Ohr_L, "Ohr_R": $Skelett/Huefte/Brust/Hals/Kopf/Ohr_R,
}
var scarf: Array[Bone2D] = []
var rest := {}
var head_mat: ShaderMaterial
# Schalende: gedämpfte Feder je Glied (Winkel in Grad), fester Zeitschritt für Determinismus
var s_ang := [0.0, 0.0, 0.0]
var s_vel := [0.0, 0.0, 0.0]
var prev_body := Vector2.ZERO


func _ready() -> void:
	for n in bones:
		rest[n] = bones[n].position
	var s1 := get_node_or_null("Skelett/Huefte/Brust/Hals/Schal_1") as Bone2D
	if s1:
		scarf = [s1, s1.get_node("Schal_2"), s1.get_node("Schal_2/Schal_3")]
		for b in scarf:
			rest[b.name] = b.position
	head_mat = $Kopf.material as ShaderMaterial


func step(dt: float) -> void:
	bones["Huefte"].rotation = deg_to_rad(body_x * BODY_TILT)
	bones["Huefte"].position = rest["Huefte"] + Vector2(body_x * BODY_SHIFT, 0.0)
	bones["Brust"].position = rest["Brust"] + Vector2(0.0, -breath * BREATH_LIFT)
	bones["Hals"].rotation = deg_to_rad(angle_z * NECK_TILT)
	bones["Hals"].position = rest["Hals"] + Vector2(angle_x * 1.5, angle_y * 0.8)
	bones["Kopf"].rotation = deg_to_rad(angle_z * HEAD_TILT)
	bones["Kopf"].position = rest["Kopf"] + Vector2(angle_x * HEAD_SHIFT.x, angle_y * HEAD_SHIFT.y)
	bones["Gesicht"].position = rest["Gesicht"] + Vector2(angle_x * FACE_SHIFT.x, angle_y * FACE_SHIFT.y)
	bones["Ohr_L"].position = rest["Ohr_L"] + Vector2(angle_x * EAR_SHIFT.x, angle_y * EAR_SHIFT.y)
	bones["Ohr_R"].position = rest["Ohr_R"] + Vector2(angle_x * EAR_SHIFT.x, angle_y * EAR_SHIFT.y)
	bones["Ohr_L"].rotation = deg_to_rad(-ear_l * EAR_TWITCH)
	bones["Ohr_R"].rotation = deg_to_rad(ear_r * EAR_TWITCH)
	if head_mat:
		head_mat.set_shader_parameter("eye_open_l", clampf(eye_l, 0.0, 1.0))
		head_mat.set_shader_parameter("eye_open_r", clampf(eye_r, 0.0, 1.0))
		head_mat.set_shader_parameter("mouth_open", clampf(mouth, 0.0, 1.0))
		head_mat.set_shader_parameter("gaze", gaze * GAZE_PX)
	_scarf(dt)


## Schalende in die Gleichgewichtslage für den Wind w setzen, ohne Schwung. Vor dem ersten step() aufrufen
## (nach dem Setzen der Parameter), sonst schwingt es aus der Senkrechten in die Windlage.
func settle(w: float) -> void:
	wind = w
	prev_body = _body()
	for i in range(3):
		s_ang[i] = clampf(w * (0.35 + 0.25 * i), -14.0, 14.0)
		s_vel[i] = 0.0
		if i < scarf.size():
			scarf[i].rotation = deg_to_rad(s_ang[i])


func _body() -> Vector2:
	return Vector2(body_x * BODY_SHIFT + angle_x * 1.5, -breath * BREATH_LIFT)


func _scarf(dt: float) -> void:
	if scarf.is_empty():
		return
	# Antrieb: Wind und Trägheit gegen die Körperbewegung (Glieder hängen nach)
	var body := _body()
	var acc_body := (body - prev_body) / maxf(dt, 1e-4)
	prev_body = body
	for i in range(3):
		var stiff := 60.0 - i * 14.0
		var damp := 5.5 - i * 1.0
		var target := wind * (0.35 + 0.25 * i)
		var a: float = -stiff * (s_ang[i] - target) - damp * s_vel[i] - acc_body.x * (0.9 + 0.5 * i)
		s_vel[i] += a * dt
		s_ang[i] += s_vel[i] * dt
		s_ang[i] = clampf(s_ang[i], -14.0, 14.0)
		scarf[i].rotation = deg_to_rad(s_ang[i])
