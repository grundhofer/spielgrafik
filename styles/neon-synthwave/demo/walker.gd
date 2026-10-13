extends RefCounted
## Dachs-Kurier als reine Funktion der Zeit: Laufen, Bremsen bis zur Durchgangsphase, Überblenden auf Idle mit
## festgehaltenem Standfuß, Drehung zur Kamera um die Mitte der Pfoten, Winken.
##
## Die Animationen aus badger.glb laufen über einen AnimationTree im manuellen Modus: Jede Animation hängt an
## einem TimeSeek-Knoten mit Zeitmaßstab 0, main.gd setzt in jedem Bild die Zeitpunkte und Mischanteile und ruft
## advance(0). So hängt die Pose nur von t ab (Sprung mit --t0 möglich, Aufnahmen bitgleich), und der
## AnimationPlayer lässt beim Überblenden nichts mit eigener Geschwindigkeit weiterlaufen.

const WALK_SPEED := 0.367        # m/s bei Abspieltempo 1 (badger_notes.md)
const RATE := 2.0                # Abspieltempo beim Laufen: 0,734 m/s
const PHASE0 := 0.1              # Laufphase bei t = 0
const BRAKE_T := 3.1             # Beginn des Bremsens
const BRAKE_LEN := 0.5           # lineares Abbremsen; Phase am Ende = PHASE0 + RATE·BRAKE_T + RATE·BRAKE_LEN/2
const STOP_T := BRAKE_T + BRAKE_LEN   # 3,6 s, Phase 6,8 ≡ 0,8: linker Fuß schwingt durch, rechter steht
const BLEND_LEN := 0.4           # Überblenden Walk -> Idle
const TURN_T := 4.05
const TURN_LEN := 0.45
const TURN_DEG := -62.0          # Dreiviertelansicht zur Kamera (Paket und Winkhand sichtbar)
const WAVE_T := 4.4
const WAVE_LEN := 1.5
const PATH_Z := 2.2
const STOP_X := -0.75

var node: Node3D
var tree: AnimationTree
var skel: Skeleton3D
var armature: Node3D
var foot_r := -1
var foot_l := -1
var start_x := 0.0
var stance_ref := Vector3.ZERO   # rechter Fuß (Standfuß) im Stand der Laufpose bei STOP_T, Figurenkoordinaten
var pivot := Vector3.ZERO        # Mitte der Pfoten in der Idle-Pose (Figurenkoordinaten, nach Korrektur)
var corr := Vector3.ZERO


func _init(badger: Node3D) -> void:
	node = badger
	var player: AnimationPlayer = badger.get_node("AnimationPlayer")
	player.stop()
	armature = badger.get_node("Armature")
	skel = badger.get_node("Armature/Skeleton3D")
	foot_r = skel.find_bone("foot.R")
	foot_l = skel.find_bone("foot.L")

	var bt := AnimationNodeBlendTree.new()
	var x := 0
	for a in ["Walk", "Idle", "Wave"]:
		var an := AnimationNodeAnimation.new()
		an.animation = a
		var seek := AnimationNodeTimeSeek.new()
		var scale := AnimationNodeTimeScale.new()
		bt.add_node("A" + a, an, Vector2(x, 0))
		bt.add_node("Seek" + a, seek, Vector2(x, 100))
		bt.add_node("Scale" + a, scale, Vector2(x, 200))
		bt.connect_node("Seek" + a, 0, "A" + a)
		bt.connect_node("Scale" + a, 0, "Seek" + a)
		x += 200
	bt.add_node("WalkIdle", AnimationNodeBlend2.new(), Vector2(200, 300))
	bt.connect_node("WalkIdle", 0, "ScaleWalk")
	bt.connect_node("WalkIdle", 1, "ScaleIdle")
	bt.add_node("PlusWave", AnimationNodeBlend2.new(), Vector2(300, 400))
	bt.connect_node("PlusWave", 0, "WalkIdle")
	bt.connect_node("PlusWave", 1, "ScaleWave")
	bt.connect_node("output", 0, "PlusWave")

	tree = AnimationTree.new()
	tree.tree_root = bt
	tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	badger.add_child(tree)
	tree.root_node = NodePath("..")
	tree.anim_player = NodePath("../AnimationPlayer")
	for a in ["Walk", "Idle", "Wave"]:
		tree.set("parameters/Scale%s/scale" % a, 0.0)
	tree.active = true

	# Bezugspunkte aus den Posen messen (unabhängig von t, deshalb auch mit --t0 gleich)
	_pose(_phase_at(STOP_T), 0.0, 0.0, 0.0, 0.0)
	stance_ref = _foot_local(foot_r)
	_pose(0.0, 0.0, 1.0, 0.0, 0.0)
	corr = stance_ref - _foot_local(foot_r)
	corr.y = 0.0
	pivot = (_foot_local(foot_r) + _foot_local(foot_l)) * 0.5 + corr
	pivot.y = 0.0
	start_x = STOP_X - WALK_SPEED * (_phase_at(STOP_T) - PHASE0)


func _phase_at(t: float) -> float:
	if t <= BRAKE_T:
		return PHASE0 + RATE * t
	var tau := minf(t - BRAKE_T, BRAKE_LEN)
	return PHASE0 + RATE * BRAKE_T + RATE * (tau - tau * tau / (2.0 * BRAKE_LEN))


func _pose(walk_phase: float, idle_t: float, idle_amt: float, wave_t: float, wave_amt: float) -> void:
	tree.set("parameters/SeekWalk/seek_request", fposmod(walk_phase, 1.0))
	tree.set("parameters/SeekIdle/seek_request", fposmod(idle_t, 2.0))
	tree.set("parameters/SeekWave/seek_request", clampf(wave_t, 0.0, WAVE_LEN))
	tree.set("parameters/WalkIdle/blend_amount", idle_amt)
	tree.set("parameters/PlusWave/blend_amount", wave_amt)
	tree.advance(0.0)


func _foot_local(bone: int) -> Vector3:
	return armature.transform * (skel.get_bone_global_pose(bone).origin)


## Setzt Pose und Lage für die Zeit t. Gibt die Laufphase zurück (für Messungen).
func update(t: float) -> float:
	var ph := _phase_at(t)
	var blend := smoothstep(STOP_T, STOP_T + BLEND_LEN, t)
	var idle_t := maxf(t - STOP_T, 0.0)
	var wt := t - WAVE_T
	var wave_amt := smoothstep(0.0, 0.12, wt) * (1.0 - smoothstep(WAVE_LEN - 0.12, WAVE_LEN, wt))
	_pose(ph, idle_t, blend, wt, wave_amt)

	var x := start_x + WALK_SPEED * (ph - PHASE0)
	var base := Vector3(x, 0.0, PATH_Z)
	var c := Vector3.ZERO
	if t >= STOP_T:
		# Standfuß festhalten: Verschiebung, die den rechten Fuß an seiner Lage aus der Laufpose hält
		c = stance_ref - _foot_local(foot_r)
		c.y = 0.0
	var ang := deg_to_rad(TURN_DEG) * smoothstep(TURN_T, TURN_T + TURN_LEN, t)
	var rot := Basis(Vector3.UP, ang)
	# Drehung um die Mitte der Pfoten (pivot, schon um corr verschoben), nicht um den Ursprung:
	# bei Winkel 0 ist der Ursprung base + c; die Pfotenmitte (pivot - corr in Figurenkoordinaten) bleibt fest.
	node.transform = Transform3D(rot, base + pivot - rot * (pivot - c))
	return ph
