extends Node2D
## Hafen von Lornholm als Visual-Novel-Szene im Anime-Stil.
## Alles hängt nur von der aufsummierten Zeit t ab; Zufall nur mit festem Seed.
## So ist die Aufnahme mit --fixed-fps Bild für Bild reproduzierbar.
##
## Lage der Lichtquellen und Funkelstellen steht in art/layout.json, Lage, Größe und vorhandene Mimik-Fassungen
## der Figur in art/sprite.json (beides von tools/prep.py gemessen bzw. festgelegt), damit Szene und Skript
## getrennt bleiben. Fehlt eine Fassung (Bildauftrag nicht erledigt), springt FALLBACK ein.

const SPARKLE := preload("res://art/fx/sparkle.png")
const GULL_TEX := preload("res://art/fx/gull.png")
const PUFF_TEX := [preload("res://art/fx/puff1.png"), preload("res://art/fx/puff2.png"), preload("res://art/fx/puff3.png")]
const PUFF_SHADER := preload("res://shaders/puff.gdshader")
const PLATE_SHADER := preload("res://shaders/ui_plate.gdshader")
const FONT_BOLD := preload("res://fonts/ZenMaruGothic-Bold.ttf")

# Mimik-Fassungen (alle gleich groß, gleicher Körper; nur das Gesicht unterscheidet sich). Reihenfolge wichtig:
# eine Ersatzfassung muss vor der Fassung stehen, die sie ersetzt.
const FACE_NAMES := ["neutral", "blink", "talk", "happy", "happy_closed", "surprised"]
const FALLBACK := {"blink": "neutral", "talk": "neutral", "happy": "neutral", "happy_closed": "happy",
		"surprised": "neutral"}

# --- Ablauf (Sekunden) -------------------------------------------------------------------------
const ENTER_T := 0.0          # Figur blendet ein und gleitet 36 px nach rechts
const ENTER_DUR := 0.4
const FPS := 30.0             # Bildrate der Aufnahme: Mimik und Lippen schalten nur an Bildgrenzen
const TYPE_START := 0.5       # = Bild 15
const TYPE_CPS := 32.0
const SENTENCE_PAUSE := 0.32  # Pause nach einem Satzende
# Mimik: [Startzeit, Fassung, Überblendung in s]. Alle Wechsel hart wie im VN (Überblendungen von 0,12–0,15 s
# zeigten 3–4 Bilder lang doppelte Augen und Münder). Startzeiten liegen auf dem 3-Bilder-Raster der Lippen.
const EXPR := [[0.0, "neutral", 0.0], [1.80, "happy", 0.0], [3.40, "surprised", 0.0], [4.50, "neutral", 0.0]]
const BLINKS := [[1.50, 0.1], [5.22, 0.1]]   # [Start, Dauer] Augen zu (3 Bilder bei 30 fps)
const FLAP_FRAMES := 3        # Mund auf/zu je 3 Bilder (0,1 s) während getippt wird
const HOPS := [[1.80, 0.22, 9.0], [3.40, 0.26, 22.0]]  # [Start, Dauer, Höhe in px]
const EMOTE_T := [3.40, 4.30]
const NEAR_GULL_T := [3.0, 3.5]   # nahe Möwe streift über den Kopf (Mitte bei 3,25 s), Schreck 0,15 s danach
const CHOICE_T := [4.2, 4.32, 4.44]
const HOVER_T := 5.0
const CHOICES := ["Zum Leuchtturm gehen", "Das Paket ansehen", "Mit dem Dachs sprechen"]

const BEAM_PERIOD := 8.0
const BEAM_PHASE := 2.2
const SMOKE_LIFE := 4.2
const SMOKE_EVERY := 0.42

var t := 0.0
var L := {}
var S := {}
var faces := {}
var char_t: PackedFloat32Array = PackedFloat32Array()
var sentences: Array = []     # [Start, Ende] je Satz in Sekunden (Lippenbewegung nur beim Tippen)
var smoke: Array = []
var glints: Array = []
var stars: Array = []
var far_gulls: Array = []
var choice_nodes: Array = []
var measure := false

@onready var badger: Sprite2D = $World/Badger
@onready var bmat: ShaderMaterial = badger.material
@onready var emote: Sprite2D = $World/Emote
@onready var near_gull: Sprite2D = $World/NearGull
@onready var beam: Node2D = $World/Beam
@onready var beam_sprite: Sprite2D = $World/Beam/BeamSprite
@onready var lamp_glow: Sprite2D = $World/LampGlow
@onready var lamp_flare: Sprite2D = $World/LampFlare
@onready var window_glow: Sprite2D = $World/WindowGlow
@onready var lantern_glow: Sprite2D = $World/LanternGlow
@onready var lantern_flare: Sprite2D = $World/LanternFlare
@onready var add_mat: Material = beam_sprite.material
@onready var card: ColorRect = $UI/LocCard
@onready var line: Label = $UI/Line
@onready var ctc: Label = $UI/CTC


func _ready() -> void:
	L = JSON.parse_string(FileAccess.get_file_as_string("res://art/layout.json"))
	S = JSON.parse_string(FileAccess.get_file_as_string("res://art/sprite.json"))
	for k in FACE_NAMES:
		var path := "res://art/badger_%s.png" % k
		if k in S["variants"] and ResourceLoader.exists(path):
			faces[k] = load(path)
		else:
			faces[k] = faces[FALLBACK[k]]
			print("Fassung %s fehlt, ersetzt durch %s" % [k, FALLBACK[k]])
	var rng := RandomNumberGenerator.new()
	rng.seed = 20261010
	_build_typing()
	_build_smoke(rng)
	_build_glints(rng)
	_build_stars(rng)
	_build_far_gulls()
	_build_choices()
	var lamp := _v("lamp")
	beam.position = lamp
	lamp_glow.position = lamp
	lamp_flare.position = lamp
	window_glow.position = _v("window")
	lantern_glow.position = _v("lantern")
	lantern_flare.position = _v("lantern")
	if "--measure" in OS.get_cmdline_user_args():
		# Messmodus für tools/measure.py: nur die Figur vor Magenta, ohne Kantenlicht und Oberfläche
		RenderingServer.set_default_clear_color(Color(1, 0, 1))
		for c in $World.get_children():
			c.visible = c == badger
		$UI.visible = false
		measure = true
	_apply(0.0)


func _process(delta: float) -> void:
	t += delta
	_apply(t)


func _v(key: String, d: Dictionary = L) -> Vector2:
	var a: Array = d[key]
	return Vector2(a[0], a[1])


# --- Aufbau -----------------------------------------------------------------------------------

func _build_typing() -> void:
	# Zeitpunkt, zu dem jedes Zeichen erscheint; nach Satzenden eine kurze Pause.
	var text := line.text
	var tt := TYPE_START
	var s0 := tt
	char_t.resize(text.length())
	for i in text.length():
		char_t[i] = tt
		tt += 1.0 / TYPE_CPS
		if text[i] == "." and i < text.length() - 2:
			sentences.append([s0, tt])
			tt += SENTENCE_PAUSE
			s0 = tt
	sentences.append([s0, tt])


func _build_smoke(rng: RandomNumberGenerator) -> void:
	var n := int(ceil((6.0 + SMOKE_LIFE) / SMOKE_EVERY)) + 1
	for i in n:
		var s := Sprite2D.new()
		s.texture = PUFF_TEX[i % PUFF_TEX.size()]
		var m := ShaderMaterial.new()
		m.shader = PUFF_SHADER
		m.set_shader_parameter("lit_color", Vector3(1.0, 0.80, 0.74))
		m.set_shader_parameter("shade_color", Vector3(0.50, 0.47, 0.68))
		s.material = m
		s.flip_h = rng.randf() < 0.5
		$World/Smoke.add_child(s)
		smoke.append({
			"node": s, "spawn": -SMOKE_LIFE + i * SMOKE_EVERY, "period": n * SMOKE_EVERY,
			"wob": rng.randf_range(0.0, TAU), "end": rng.randf_range(0.42, 0.55),
			"drift": rng.randf_range(22.0, 26.0),
		})


func _build_glints(rng: RandomNumberGenerator) -> void:
	for g in L["glints"]:
		var s := Sprite2D.new()
		s.texture = SPARKLE
		s.material = add_mat
		s.position = Vector2(g[0], g[1])
		$World/Glints.add_child(s)
		glints.append({
			"node": s, "size": float(g[2]), "period": rng.randf_range(1.1, 2.3), "phase": rng.randf(),
			"peak": rng.randf_range(0.6, 1.0), "warm": float(g[3]) if g.size() > 3 else 0.0,
		})


func _build_stars(rng: RandomNumberGenerator) -> void:
	for g in L["stars"]:
		var s := Sprite2D.new()
		s.texture = SPARKLE
		s.material = add_mat
		s.position = Vector2(g[0], g[1])
		$World/Stars.add_child(s)
		stars.append({"node": s, "size": float(g[2]), "period": rng.randf_range(2.0, 3.6), "phase": rng.randf()})


func _build_far_gulls() -> void:
	# [Start-x, y, Geschwindigkeit, Maßstab, Phase]
	for g in L["far_gulls"]:
		var s := Sprite2D.new()
		s.texture = GULL_TEX
		s.hframes = 4
		s.scale = Vector2(g[3], g[3])
		$World/FarGulls.add_child(s)
		far_gulls.append({"node": s, "x0": float(g[0]), "y": float(g[1]), "v": float(g[2]), "ph": float(g[4])})


func _build_choices() -> void:
	var c: Dictionary = L["choices"]
	for i in CHOICES.size():
		var r := ColorRect.new()
		var m := ShaderMaterial.new()
		m.shader = PLATE_SHADER
		var size := Vector2(c["w"], c["h"])
		m.set_shader_parameter("size", size)
		m.set_shader_parameter("radius", 15.0)
		m.set_shader_parameter("pad", 6.0)
		# Grundzustand: helles, leicht durchscheinendes Feld; Hervorhebung: Abendverlauf wie das Namensfeld
		m.set_shader_parameter("left_a", Color(1.0, 0.98, 0.97, 0.88))
		m.set_shader_parameter("right_a", Color(0.93, 0.91, 1.0, 0.88))
		m.set_shader_parameter("left_b", Color(0.95, 0.47, 0.47, 0.97))
		m.set_shader_parameter("right_b", Color(0.99, 0.70, 0.42, 0.97))
		m.set_shader_parameter("edge_color", Color(1.0, 1.0, 1.0, 1.0))
		m.set_shader_parameter("shadow", 0.3)
		r.material = m
		r.size = size
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		var lb := Label.new()
		lb.text = CHOICES[i]
		lb.add_theme_font_override("font", FONT_BOLD)
		lb.add_theme_font_size_override("font_size", 20)
		lb.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		lb.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		lb.position = Vector2(6, 5)
		lb.size = size - Vector2(12, 12)
		r.add_child(lb)
		$UI/Choices.add_child(r)
		choice_nodes.append({"rect": r, "label": lb, "mat": m, "y": float(c["y"]) + i * float(c["step"])})


# --- Animation --------------------------------------------------------------------------------

func _flicker(time: float) -> float:
	# Laternenflackern: Summe unharmonischer Sinusschwingungen plus kurze Einbrüche, Bereich etwa -1..1
	var f := 0.5 * sin(time * 11.0) + 0.3 * sin(time * 23.7 + 1.1) + 0.2 * sin(time * 41.3 + 2.3)
	var dip := pow(maxf(0.0, sin(time * 2.9 + 0.7)), 24.0)
	return clampf(f - 1.2 * dip, -1.0, 1.0)


func _ease_out(u: float) -> float:
	u = clampf(u, 0.0, 1.0)
	return 1.0 - (1.0 - u) * (1.0 - u) * (1.0 - u)


func _visible_chars(time: float) -> int:
	var n := 0
	for i in char_t.size():
		if char_t[i] <= time:
			n = i + 1
	return n


func _face(time: float) -> Array:
	# Liefert [Fassung A, Fassung B, Mischung]
	# Zeit auf das aktuelle Bild runden (die aufsummierte Zeit liegt sonst knapp unter k/30, und ein Wechsel
	# rutschte ein Bild später als das Lippenraster)
	var fr := roundf(time * FPS)
	var q := (fr + 0.01) / FPS
	var cur: String = EXPR[0][1]
	var prev := cur
	var mixv := 1.0
	for e in EXPR:
		if q >= e[0]:
			prev = cur
			cur = e[1]
			mixv = 1.0 if e[2] <= 0.0 else clampf((q - e[0]) / e[2], 0.0, 1.0)
	if mixv < 1.0:
		return [prev, cur, mixv]
	# Blinzeln nur in der neutralen Fassung (freudig hat geschlossene Augen, überrascht ist kurz)
	if cur == "neutral":
		for b in BLINKS:
			if q >= b[0] and q < b[0] + b[1]:
				return ["blink", "blink", 0.0]
	# Lippen: während ein Satz getippt wird, im 3-Bilder-Takt wechseln; bei Leerzeichen/Satzzeichen Mund in Ruhe.
	# Offen oder zu wird nur einmal je Phase entschieden (Zeichen am Phasenbeginn), sonst schlossen Leerzeichen
	# den Mund mitten in einer Phase (Haltezeiten von 1–2 Bildern).
	# neutral: Ruhe = neutral, offen = talk. freudig: Ruhe = happy_closed (Lächeln), offen = happy (Lachen).
	var ph := int(floor((fr - TYPE_START * FPS) / FLAP_FRAMES))
	var ts := (TYPE_START * FPS + ph * FLAP_FRAMES + 0.01) / FPS
	if cur in ["neutral", "happy"] and _typing(ts):
		var i := _visible_chars(ts) - 1
		var ch := line.text[i] if i >= 0 else " "
		var open := ph % 2 == 0 and not (ch in [" ", ".", ",", "„", "“"])
		if cur == "neutral" and open:
			return ["talk", "talk", 0.0]
		if cur == "happy" and not open:
			return ["happy_closed", "happy_closed", 0.0]
	return [cur, cur, 0.0]


func _typing(time: float) -> bool:
	for s in sentences:
		if time >= s[0] and time < s[1]:
			return true
	return false


func _apply(time: float) -> void:
	var fl := _flicker(time)

	# --- Figur ---------------------------------------------------------------------------------
	var f := _face(time)
	badger.texture = faces[f[0]]
	bmat.set_shader_parameter("tex_b", faces[f[1]])
	bmat.set_shader_parameter("mix_b", f[2])
	var base: Vector2 = _v("pos", S)
	var u := _ease_out((time - ENTER_T) / ENTER_DUR)
	var hop := 0.0
	for h in HOPS:
		var k: float = (time - h[0]) / h[1]
		if k >= 0.0 and k < 1.0:
			hop = h[2] * sin(PI * k)
	badger.position = Vector2(roundf(base.x - 36.0 * (1.0 - u)), roundf(base.y - hop))
	badger.modulate.a = smoothstep(0.0, 0.85, u)
	# Abendlicht: warme helle Töne, kühle Schatten; warmes Kantenlicht von rechts oben (Himmelsglut)
	bmat.set_shader_parameter("tint", Vector3(1.04, 0.97, 0.93))
	bmat.set_shader_parameter("shadow_tint", Vector3(0.86, 0.86, 1.02))
	bmat.set_shader_parameter("rim", 0.0 if measure else 0.34 + 0.03 * fl)

	# Schreck-Zeichen am Kopf (sprite.json: Punkt oben rechts am Kopf, relativ zur Sprite-Ecke)
	var head: Vector2 = _v("emote", S)
	var on := (roundf(time * FPS) + 0.01) / FPS >= EMOTE_T[0] and time < EMOTE_T[1]
	emote.visible = on and not measure
	if on:
		var a := time - EMOTE_T[0]
		var pop := 0.6 + 0.4 * _ease_out(a / 0.08) + 0.06 * sin(a * 40.0) * exp(-a * 8.0)
		emote.scale = Vector2(pop, pop)
		emote.position = badger.position + head
		emote.modulate.a = 1.0 - smoothstep(EMOTE_T[1] - 0.15, EMOTE_T[1], time)

	# Möwe fliegt dicht vor der Kamera über den Kopf hinweg (Anlass für den Schreck): von rechts unten nach links
	# oben, ~440 px Spannweite, in 0,5 s quer durchs Bild; das Gesicht bleibt frei, nur die Mütze wird gestreift.
	var gk := (time - NEAR_GULL_T[0]) / (NEAR_GULL_T[1] - NEAR_GULL_T[0])
	near_gull.visible = gk >= 0.0 and gk <= 1.0 and not measure
	if near_gull.visible:
		near_gull.position = Vector2(roundf(lerpf(1560.0, -360.0, gk)), roundf(lerpf(150.0, 10.0, gk) - 25.0 * sin(gk * PI)))
		near_gull.scale = Vector2(1.15, 1.15)
		near_gull.flip_h = true
		near_gull.frame = [0, 1, 2, 1][int(floor(time * 15.0)) % 4]   # 15 Bilder/s (auf Zweien)

	# --- Leuchtturm: Strahl dreht sich um die senkrechte Achse ----------------------------------
	var th := TAU * time / BEAM_PERIOD + BEAM_PHASE
	var side := cos(th)
	var front := sin(th)
	beam_sprite.scale = Vector2(side * float(L["beam_len"]) / 640.0, lerpf(0.35, 0.55, absf(side)))
	beam_sprite.modulate = Color(1.0, 0.93, 0.75, clampf(0.12 + 0.4 * absf(side), 0.0, 1.0) * (0.55 if front < 0.0 else 1.0))
	var flare := pow(maxf(0.0, front), 5.0)
	lamp_glow.scale = Vector2.ONE * (0.32 + 0.35 * flare)
	lamp_glow.modulate = Color(1.0, 0.86, 0.6, 0.55 + 0.4 * flare)
	lamp_flare.scale = Vector2.ONE * (0.22 + 0.55 * flare)
	lamp_flare.rotation = time * 0.15
	lamp_flare.modulate = Color(1.0, 0.92, 0.75, 0.35 + 0.65 * flare)

	# --- Laterne und Fenster -------------------------------------------------------------------
	lantern_glow.scale = Vector2.ONE * (0.55 + 0.04 * fl)
	lantern_glow.modulate = Color(1.0, 0.7, 0.4, 0.5 + 0.16 * fl)
	lantern_flare.scale = Vector2.ONE * (0.16 + 0.02 * fl)
	lantern_flare.modulate = Color(1.0, 0.85, 0.6, 0.45 + 0.2 * fl)
	var wf := 0.5 * sin(time * 5.3) + 0.5 * sin(time * 8.9 + 0.4)
	window_glow.scale = Vector2(float(L["window_r"]) / 128.0, float(L["window_r"]) / 128.0)
	window_glow.modulate = Color(1.0, 0.68, 0.38, 0.30 + 0.05 * wf)

	# --- Rauch: Cel-Wolken steigen auf und werden vom Wind nach rechts gedrückt (bleibt unter der Ortskarte) ---
	var chim := _v("chimney")
	for p in smoke:
		var s: Sprite2D = p["node"]
		var age: float = fposmod(time - p["spawn"], p["period"])
		if age > SMOKE_LIFE:
			s.visible = false
			continue
		s.visible = true
		var k := age / SMOKE_LIFE
		s.position = (chim + Vector2(p["drift"] * age + 2.5 * age * age + 3.0 * sin(age * 1.4 + p["wob"]),
				-(24.0 * age - 2.6 * age * age))).round()
		s.scale = Vector2.ONE * lerpf(0.12, p["end"], sqrt(k))
		s.modulate = Color(1, 1, 1, smoothstep(0.0, 0.25, age) * (1.0 - smoothstep(0.35, 1.0, k)) * 0.85)

	# --- Glitzern auf dem Wasser: Funkelsterne blühen auf und vergehen ----------------------------
	for g in glints:
		var s: Sprite2D = g["node"]
		var ph: float = fposmod(time / g["period"] + g["phase"], 1.0)
		var a: float = pow(maxf(0.0, sin(ph * PI)), 4.0) * g["peak"]
		var sz: float = g["size"] * (0.5 + 0.5 * a)
		s.scale = Vector2(sz, sz)
		s.modulate = Color(1.0, lerpf(1.0, 0.86, g["warm"]), lerpf(1.0, 0.66, g["warm"]), a)

	for g in stars:
		var s: Sprite2D = g["node"]
		var ph: float = fposmod(time / g["period"] + g["phase"], 1.0)
		var a: float = 0.35 + 0.65 * pow(0.5 + 0.5 * sin(ph * TAU), 3.0)
		s.scale = Vector2.ONE * g["size"] * (0.7 + 0.3 * a)
		s.modulate = Color(0.95, 0.95, 1.0, a)

	for g in far_gulls:
		var s: Sprite2D = g["node"]
		s.position = Vector2(roundf(g["x0"] + g["v"] * time), roundf(g["y"] + 4.0 * sin(time * 1.3 + g["ph"] * 5.0)))
		# Flügelschlag in Schüben, dazwischen Gleiten (Bild 1 = Flügel waagerecht)
		var cyc := fposmod(time + g["ph"] * 3.0, 2.4)
		s.frame = [0, 1, 2, 1][int(floor(cyc * 10.0)) % 4] if cyc < 1.2 else 1

	# --- Oberfläche ----------------------------------------------------------------------------
	card.material.set_shader_parameter("reveal", _ease_out((time - 0.1) / 0.45))
	card.get_node("LocLabel").modulate.a = smoothstep(0.25, 0.55, time)
	card.get_node("LocSub").modulate.a = smoothstep(0.35, 0.65, time)
	var nvis := _visible_chars(time)
	line.visible_characters = nvis
	var done := nvis >= line.text.length()
	ctc.visible = done and time < CHOICE_T[0]
	ctc.position.y = 646.0 - roundf(3.0 * absf(sin(time * 5.0)))
	var c: Dictionary = L["choices"]
	for i in choice_nodes.size():
		var n: Dictionary = choice_nodes[i]
		var r: ColorRect = n["rect"]
		var k := _ease_out((time - CHOICE_T[i]) / 0.25)
		r.visible = time >= CHOICE_T[i]
		r.position = Vector2(roundf(float(c["x"]) + 40.0 * (1.0 - k)), n["y"])
		r.modulate.a = k
		var hv := clampf((time - HOVER_T) / 0.12, 0.0, 1.0) if i == 1 else 0.0
		(n["mat"] as ShaderMaterial).set_shader_parameter("hover", hv)
		var lb: Label = n["label"]
		lb.add_theme_color_override("font_color", Color(0.16, 0.14, 0.36).lerp(Color(1, 1, 1), hv))
		lb.add_theme_color_override("font_outline_color", Color(0.6, 0.2, 0.2, 0.6 * hv))
		lb.add_theme_constant_override("outline_size", 4 if hv > 0.0 else 0)
