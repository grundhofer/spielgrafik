class_name Cycler
extends RefCounted
## Palettenmaschine: drei Grundpaletten (Abend, Nacht, Regen) mit je 256 Einträgen aus art/palette.json.
## Je Bild:
##  1. Zyklus-Bereiche rotieren (Liste "cycles": Start, Länge, Schritte/s, Richtung) – für alle Paletten gleich,
##     wie die Farbzyklus-Bereiche der Malprogramme der späten 80er.
##  2. Überblenden: Abend -> Nacht (w_night), dann Nacht -> Regen (w_rain). Kein neues Bild, nur andere Farben.
##  3. Berechnete Einträge: Lichtkegel (Stärke je Abstandsstufe aus dem Drehwinkel), Laterne und Fenster
##     (Flackern aus festem Zufallsrauschen).
## Ergebnis: 256x1-Palettentextur, die alle Shader (Hintergrund, Dachs, Titel) lesen.

var texture: ImageTexture
var image: Image
var colors := PackedColorArray()
var pal: Array = []                 # [PackedColorArray Abend, Nacht, Regen]
var cycles: Array = []
var beam: Dictionary = {}
var flicker: Dictionary = {}
var timeline: Dictionary = {}
var rain_front: Dictionary = {}
var alpha := PackedFloat32Array()
var noise := PackedFloat32Array()
var w_night := 0.0
var w_rain := 0.0
var beam_angle := 0.0


func _init(path: String) -> void:
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(path))
	for key in ["evening", "night", "rain"]:
		var arr := PackedColorArray()
		for h in meta["palettes"][key]:
			arr.append(Color.html(h))
		pal.append(arr)
	cycles = meta["cycles"]
	beam = meta["beam"]
	flicker = meta["flicker"]
	timeline = meta["timeline"]
	rain_front = meta.get("rain_front", {})
	alpha.resize(256)
	var rng := RandomNumberGenerator.new()
	rng.seed = 3
	for i in 512:
		noise.append(rng.randf())
	colors.resize(256)
	image = Image.create(256, 1, false, Image.FORMAT_RGBA8)
	texture = ImageTexture.create_from_image(image)


static func _smooth(a: float, b: float, x: float) -> float:
	var t := clampf((x - a) / (b - a), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


func _flick(t: float, rate: float, off: float) -> float:
	var x := t * rate + off
	var i := int(floor(x))
	var f := x - float(i)
	var a := noise[posmod(i, 512)]
	var b := noise[posmod(i + 1, 512)]
	return lerpf(a, b, f * f * (3.0 - 2.0 * f))


func update(t: float) -> void:
	var src := PackedInt32Array()
	src.resize(256)
	for i in 256:
		src[i] = i
	beam_angle = float(timeline["beam_angle0"]) + TAU * t / float(timeline["beam_period"])
	for c in cycles:
		var n := int(c["len"])
		var s := int(c["start"])
		var d := int(c["dir"])
		var steps := 0
		if typeof(c["rate"]) == TYPE_STRING:      # "beam": Drehlinse synchron zum Lichtkegel
			steps = int(floor(beam_angle / TAU * float(n) * 2.0))
		else:
			steps = int(floor(t * float(c["rate"])))
		for j in n:
			src[s + j] = s + posmod(j - d * steps, n)
	w_night = _smooth(timeline["night"][0], timeline["night"][1], t)
	w_rain = _smooth(timeline["rain"][0], timeline["rain"][1], t)
	var pe: PackedColorArray = pal[0]
	var pn: PackedColorArray = pal[1]
	var pr: PackedColorArray = pal[2]
	for i in 256:
		var k := src[i]
		colors[i] = pe[k].lerp(pn[k], w_night).lerp(pr[k], w_rain)
	_beam()
	var f1 := _flick(t, 9.0, 0.0)
	var f2 := _flick(t, 4.0, 100.0)
	_scale(flicker["lantern_core"], 0.86 + 0.22 * f1)
	_scale(flicker["lantern_halo"], 0.70 + 0.42 * f1)
	_scale(flicker["window"], 0.94 + 0.08 * f2)
	# Alphakanal der Palette: 1 für alle Einträge, nur die Regen-Einträge tragen die Deckkraft der Regenebene vor
	# dem Dachs (1 im hellen Tropfenkopf, sonst 0, mal Regenstärke). Hintergrund und Figur lesen nur RGB.
	alpha.fill(1.0)
	if not rain_front.is_empty():
		var a0 := int(rain_front["start"])
		var pl := int(rain_front["phase_len"])
		var lit: Array = rain_front["lit"]
		for e in range(a0, int(rain_front["end"])):
			alpha[e] = float(lit[posmod(src[e] - a0, pl)]) * w_rain
	for i in 256:
		image.set_pixel(i, 0, Color(colors[i].r, colors[i].g, colors[i].b, alpha[i]))
	texture.update(image)


func _scale(ids: Array, k: float) -> void:
	for e in ids:
		var c: Color = colors[int(e)]
		colors[int(e)] = Color(clampf(c.r * k, 0.0, 1.0), clampf(c.g * k, 0.0, 1.0), clampf(c.b * k, 0.0, 1.0))


func _beam() -> void:
	var le: Array = beam["light_evening"]
	var ln: Array = beam["light_night"]
	var light := Color(le[0] / 255.0, le[1] / 255.0, le[2] / 255.0).lerp(Color(ln[0] / 255.0, ln[1] / 255.0, ln[2] / 255.0), w_night)
	var gain := (0.42 + 0.58 * w_night) * (1.0 + 0.3 * w_rain) * float(beam["gain"])
	var c := cos(beam_angle)
	var s := sin(beam_angle)
	# Lampe blitzt auf, wenn der Strahl zur Kamera zeigt
	var flash := pow(maxf(s, 0.0), 4.0) * 0.6
	for e in beam.get("lamp", []):
		var lc: Color = colors[int(e)]
		colors[int(e)] = Color(clampf(lc.r + light.r * flash, 0.0, 1.0), clampf(lc.g + light.g * flash, 0.0, 1.0),
				clampf(lc.b + light.b * flash, 0.0, 1.0))
	for bn in beam["bins"]:
		if int(bn.get("n", 0)) == 0:
			continue
		var I := 0.0
		if bn["side"] == "halo":
			I = pow(maxf(s, 0.0), 4.0) + 0.15
		else:
			var L := float(beam["left"]) if bn["side"] == "left" else float(beam["right"])
			var dirv := -c if bn["side"] == "left" else c
			if dirv <= 0.0:
				continue
			var vis := L * dirv
			var u := minf(float(bn["d"]) / L, 1.0)
			I = (1.0 - _smooth(vis - 0.18 * L, vis, float(bn["d"]))) * (0.45 + 0.55 * dirv) * pow(1.0 - u, float(beam["falloff"]))
		for k in int(bn["n"]):
			var e := int(bn["start"]) + k
			var col: Color = colors[e]
			colors[e] = Color(clampf(col.r + light.r * I * gain, 0.0, 1.0), clampf(col.g + light.g * I * gain, 0.0, 1.0),
					clampf(col.b + light.b * I * gain, 0.0, 1.0))
