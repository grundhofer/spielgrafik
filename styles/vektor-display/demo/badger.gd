extends RefCounted
## Der Dachs-Kurier als Linienfigur im Profil (Blick nach rechts), Einheiten: 1 = 1 cm, Füße auf y = 0,
## Mütze oben bei y = 100. Laufzyklus prozedural: Der Standfuß bleibt in der Welt fest stehen, der
## Schwungfuß folgt einem Bogen; die Phase hängt am zurückgelegten Weg, nicht an der Zeit, damit beim
## Abbremsen nichts rutscht. Nach dem Halt zieht der hintere Fuß nach (halber Schritt).

const GREEN := Color(0.25, 1.0, 0.35)
const RED := Color(1.0, 0.16, 0.12)
const WHITE := Color(0.82, 0.9, 1.0)
const YELLOW := Color(1.0, 0.82, 0.22)

const X_START := -3.85     # Welt-x des Körperursprungs bei t = 0 (m)
const V := 0.85            # Lauftempo (m/s)
const T1 := 3.0            # ab hier abbremsen
const T2 := 3.9            # steht
const SETTLE := 0.27       # Dauer des Nachziehschritts
const CREEP := 0.05        # Körper rückt beim Nachziehen noch etwas vor (m)
const BETA := 0.55         # Anteil Standphase
const LIFT := 6.0          # Schritthöhe (cm)
const HIP_NEAR := 3.0      # Hüftgelenke (cm, lokal)
const HIP_FAR := -5.0
const HIP_Y := 18.0
const HEAD_SCALE := 1.28  # Kopf größer als im Referenzblatt, damit Maske und Schnauze in 170 px lesbar bleiben

var stride := 0.42
var s_end := 0.0


func _init() -> void:
	s_end = V * T1 + V * (T2 - T1) * 0.5
	# Schrittlänge so wählen, dass der Halt genau in eine Doppelstütze fällt (Phase k + 0,025)
	var cycles := roundf(s_end / 0.42 - 0.025)
	stride = s_end / (cycles + 0.025)


func dist(t: float) -> float:
	if t <= T1:
		return V * t
	if t <= T2:
		var u := (t - T1) / (T2 - T1)
		return V * T1 + V * (T2 - T1) * 0.5 * (1.0 - (1.0 - u) * (1.0 - u))
	var w := clampf((t - T2) / SETTLE, 0.0, 1.0)
	return s_end + CREEP * smoothstep(0.0, 1.0, w)


func speed(t: float) -> float:
	if t <= T1:
		return V
	if t <= T2:
		return V * (1.0 - (t - T1) / (T2 - T1))
	return 0.0


## Welt-x (m) und Hub (cm) eines Fußes. j = 0 vorderer (naher) Fuß, 1 hinterer (ferner) Fuß.
func foot(t: float, j: int) -> Vector2:
	var hip := HIP_NEAR if j == 0 else HIP_FAR
	var s := minf(dist(t), s_end)
	var ph := s / stride + 0.5 * float(j)
	var k := floorf(ph)
	var f := ph - k
	var off := 0.5 * float(j)
	var x_k := X_START + (k + BETA * 0.5 - off) * stride + hip * 0.01
	var res: Vector2
	if f < BETA:
		res = Vector2(x_k, 0.0)
	else:
		var u := (f - BETA) / (1.0 - BETA)
		var x_n := x_k + stride
		res = Vector2(lerpf(x_k, x_n, smoothstep(0.0, 1.0, u)), LIFT * sin(PI * u))
	if t > T2 and j == 1:
		# Nachziehschritt: hinterer Fuß setzt neben den vorderen
		var front := foot(T2, 0).x
		var target := front - 0.075
		var w := clampf((t - T2) / SETTLE, 0.0, 1.0)
		var start := foot(T2, 1).x
		res = Vector2(lerpf(start, target, smoothstep(0.0, 1.0, w)), LIFT * 0.8 * sin(PI * w))
	return res


func body_x(t: float) -> float:
	return X_START + dist(t)


# ---------------------------------------------------------------------------
# Zeichnung
# ---------------------------------------------------------------------------

static func P(a: Array) -> PackedVector2Array:
	var p := PackedVector2Array()
	for q in a:
		p.append(Vector2(q[0], q[1]))
	return p


static func _scale(p: PackedVector2Array, pivot: Vector2, k: float) -> PackedVector2Array:
	var o := PackedVector2Array()
	for q in p:
		o.append(pivot + (q - pivot) * k)
	return o


static func _xf(p: PackedVector2Array, pivot: Vector2, ang: float, off: Vector2) -> PackedVector2Array:
	var o := PackedVector2Array()
	var c := cos(ang)
	var s := sin(ang)
	for q in p:
		var d := q - pivot
		o.append(pivot + Vector2(d.x * c - d.y * s, d.x * s + d.y * c) + off)
	return o


## Catmull-Rom durch Stützpunkte; ein doppelt angegebener Punkt ergibt eine Ecke.
static func smooth(a: Array, closed := false, sub := 4) -> PackedVector2Array:
	var p := P(a)
	var n := p.size()
	var o := PackedVector2Array()
	if n < 3:
		return p
	var segs := n if closed else n - 1
	for i in segs:
		var p0 := p[(i - 1 + n) % n] if (closed or i > 0) else p[0]
		var p1 := p[i]
		var p2 := p[(i + 1) % n]
		var p3 := p[(i + 2) % n] if (closed or i + 2 < n) else p[n - 1]
		if p1.distance_squared_to(p2) < 0.0001:
			continue
		for k in sub:
			var u := float(k) / float(sub)
			var u2 := u * u
			var u3 := u2 * u
			o.append(0.5 * ((2.0 * p1) + (-p0 + p2) * u + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2
				+ (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3))
	if not closed:
		o.append(p[n - 1])
	return o


func _leg(hip: Vector2, f: Vector2) -> PackedVector2Array:
	# Stummelbein mit Pfote: hinten Hüfte -> Ferse -> Sohle -> Zehen -> vorn Hüfte
	var fx := f.x
	var fy := f.y
	var tilt := clampf(fy / LIFT, 0.0, 1.0) * 1.8
	return smooth([[hip.x - 7.5, hip.y + 2.0], [fx - 5.0, fy + 8.0], [fx - 6.6, fy + 3.0], [fx - 4.6, fy + 0.2],
		[fx - 4.6, fy + 0.2], [fx + 7.0, fy - tilt], [fx + 7.0, fy - tilt], [fx + 10.0, fy + 2.0 - tilt],
		[fx + 7.4, fy + 5.4], [fx + 4.0, fy + 8.0], [hip.x + 6.5, hip.y + 2.0]])


## Liefert Ebenen von vorn nach hinten: [{lines:[[PackedVector2Array, Farbe, closed, cap]], occ:[PackedVector2Array]}]
## in lokalen Einheiten (y nach oben) sowie die Fußpunkte für die Messung.
func build(t: float, solo := false) -> Dictionary:
	var sp := speed(t) / V
	var bx := body_x(t)
	var s := minf(dist(t), s_end)
	var ph := s / stride
	var settle := clampf((t - T2) / SETTLE, 0.0, 1.0) if t > T2 else 0.0
	# Wippen: am höchsten in der Mitte der Standphase
	var bob := 1.3 * cos(TAU * 2.0 * (ph - BETA * 0.5)) * sp
	if t > T2:
		bob = 0.8 * sin(PI * settle)
	var breathe := 0.0
	if t > T2 + SETTLE:
		breathe = 0.6 * sin(TAU * (t - T2) / 1.7)
	var lean := deg_to_rad(-3.0) * sp + deg_to_rad(-1.2) * cos(TAU * 2.0 * ph) * sp
	var nod := 0.0
	var tn := t - 4.55
	if tn > 0.0 and tn < 0.8:
		nod = deg_to_rad(-9.0) * sin(PI * tn / 0.8)
	var off := Vector2(0.0, bob + breathe * 0.3)
	var hip_pivot := Vector2(0.0, HIP_Y)
	var neck := Vector2(2.0, 74.0)

	var fn := foot(t, 0)
	var ff := foot(t, 1)
	var fn_l := Vector2((fn.x - bx) * 100.0, fn.y)
	var ff_l := Vector2((ff.x - bx) * 100.0, ff.y)

	# U: Rumpfteile (Neigung um die Hüfte), H: Kopfteile (zusätzlich Nicken um den Hals); S = geglättet
	var U := func(a: Array) -> PackedVector2Array:
		return _xf(P(a), hip_pivot, lean, off)
	var US := func(a: Array, closed: bool) -> PackedVector2Array:
		return _xf(smooth(a, closed), hip_pivot, lean, off)
	var H := func(a: Array) -> PackedVector2Array:
		return _xf(_xf(_scale(P(a), neck, HEAD_SCALE), neck, nod, Vector2()), hip_pivot, lean, off)
	var HS := func(a: Array, closed: bool) -> PackedVector2Array:
		return _xf(_xf(_scale(smooth(a, closed), neck, HEAD_SCALE), neck, nod, Vector2()), hip_pivot, lean, off)

	var fur := WHITE * 0.5
	var light := WHITE * 1.0
	var layers := []

	if solo:
		var leg_n := _leg(Vector2(HIP_NEAR, HIP_Y + bob), fn_l)
		var leg_f := _leg(Vector2(HIP_FAR, HIP_Y + bob), ff_l)
		layers.append({"lines": [[leg_n, Color(1, 0, 0), false, 1.0]], "occ": []})
		layers.append({"lines": [[leg_f, Color(0, 1, 0), false, 1.0]], "occ": []})
		var cap_top := H.call([[-3.0, 101.5]]) as PackedVector2Array
		layers.append({"lines": [[cap_top, Color(0, 0, 1), false, 1.0]], "occ": []})
		return {"layers": layers, "feet": [fn, ff], "body_x": bx}

	# --- Schalende vorn (hängt vor der Weste, schwingt im Gehen) ---
	var sw := 1.5 * sin(TAU * 1.3 * t) * (0.35 + 0.65 * sp)
	var scarf_end := US.call([[15.6, 66.0], [17.6 + sw * 0.3, 55.0], [18.4 + sw, 45.0], [18.4 + sw, 45.0],
		[23.6 + sw, 45.6], [23.6 + sw, 45.6], [22.6 + sw * 0.4, 56.0], [20.4, 66.0]], false) as PackedVector2Array
	var l0 := [[scarf_end, RED, false, 0.5]]
	for k in 3:
		var fx := 19.4 + 1.8 * k + sw
		l0.append([U.call([[fx, 45.2], [fx - 0.4 + sw * 0.25, 41.0]]), RED * 0.8, false, 0.7])
	var scarf_occ := PackedVector2Array(scarf_end)
	layers.append({"lines": l0, "occ": [scarf_occ]})

	# --- Unterarm mit Pfote (hält das Paket) ---
	var arm := US.call([[-8.0, 46.8], [-13.6, 47.6], [-15.8, 40.0], [-14.4, 32.0], [-8.0, 27.4], [2.0, 25.6],
		[10.0, 26.0], [14.6, 28.2], [14.4, 31.6], [10.6, 31.8], [2.0, 30.2], [-6.6, 31.6], [-9.8, 36.0],
		[-10.2, 42.0], [-8.0, 46.8]], false) as PackedVector2Array
	var claws := U.call([[14.8, 29.4], [16.8, 28.6]]) as PackedVector2Array
	layers.append({"lines": [[arm, fur * 1.1, false, 0.5], [claws, fur * 0.9, false, 0.6]], "occ": [arm]})

	# --- Paket unter dem Arm ---
	var parcel := U.call([[-15.0, 46.0], [11.0, 41.5], [13.0, 28.5], [-13.0, 33.0]]) as PackedVector2Array
	var parcel_top := U.call([[-15.0, 46.0], [-12.5, 49.2], [13.6, 44.6], [11.0, 41.5]]) as PackedVector2Array
	var string_v := U.call([[-1.6, 43.6], [0.4, 30.7]]) as PackedVector2Array
	var string_h := U.call([[-14.0, 39.4], [12.0, 34.9]]) as PackedVector2Array
	var parcel_occ := U.call([[-15.0, 46.0], [-12.5, 49.2], [13.6, 44.6], [13.0, 28.5], [-13.0, 33.0]]) as PackedVector2Array
	layers.append({"lines": [[parcel, YELLOW * 0.95, true, 0.5], [parcel_top, YELLOW * 0.7, false, 0.5],
		[string_v, WHITE * 0.4, false, 0.4], [string_h, WHITE * 0.4, false, 0.4]], "occ": [parcel_occ]})

	# --- Kopf: Mütze, Kopfumriss, Augenbinde (Maske), Auge, Nase ---
	var crown := HS.call([[-15.5, 86.8], [-15.5, 86.8], [-18.0, 91.0], [-13.0, 98.0], [-3.0, 101.5], [8.0, 100.5],
		[15.0, 96.5], [17.2, 91.6], [17.2, 91.6]], false) as PackedVector2Array
	var brim := H.call([[17.2, 91.6], [24.5, 89.8], [28.8, 88.2], [26.2, 86.4], [15.0, 87.4], [-15.5, 86.8]]) as PackedVector2Array
	var band := H.call([[-16.8, 89.4], [16.6, 90.4]]) as PackedVector2Array
	var button := H.call([[12.6, 92.4]]) as PackedVector2Array
	var nape := HS.call([[-15.0, 86.6], [-17.6, 80.5], [-16.6, 74.5]], false) as PackedVector2Array
	var face := HS.call([[15.0, 87.4], [21.5, 85.2], [27.4, 82.6], [30.6, 80.8], [30.6, 80.8], [29.8, 77.8],
		[25.0, 76.0], [18.0, 74.4], [12.0, 73.6]], false) as PackedVector2Array
	var mask := HS.call([[28.0, 81.0], [28.0, 81.0], [19.0, 83.4], [9.0, 85.6], [0.0, 86.4], [-7.0, 85.0],
		[-10.4, 81.4], [-6.5, 78.4], [2.0, 78.8], [12.0, 79.4], [21.0, 79.4], [28.0, 81.0]], false) as PackedVector2Array
	var blink := t > 5.25 and t < 5.38
	var eye: PackedVector2Array
	if blink:
		eye = H.call([[12.8, 82.3], [16.2, 82.3]]) as PackedVector2Array
	else:
		eye = H.call([[14.6, 82.4]]) as PackedVector2Array
	var nose := H.call([[30.4, 80.4]]) as PackedVector2Array
	var mouth := HS.call([[25.0, 77.3], [22.0, 77.6], [19.5, 77.2]], false) as PackedVector2Array
	var head_occ := PackedVector2Array(crown)
	head_occ.append_array(H.call([[24.5, 89.8], [28.8, 88.2], [26.2, 86.4]]) as PackedVector2Array)
	head_occ.append_array(face)
	var nape_r := nape.duplicate()
	nape_r.reverse()
	head_occ.append_array(nape_r)
	# Schal um den Hals
	var wrap := US.call([[-17.0, 75.6], [-5.0, 77.8], [8.0, 77.0], [17.0, 74.2], [20.6, 70.0], [20.2, 65.4],
		[11.0, 63.4], [-4.0, 62.9], [-18.6, 64.6], [-19.8, 70.2]], true) as PackedVector2Array
	var l3 := [[crown, GREEN * 1.05, false, 0.5], [brim, GREEN * 1.05, false, 0.5], [band, YELLOW * 0.45, false, 0.4],
		[button, YELLOW * 1.3, false, 1.0], [nape, fur * 1.4, false, 0.5], [face, light * 0.95, false, 0.6],
		[mask, light * 0.5, false, 0.4], [eye, WHITE * 1.5, false, 1.0], [nose, WHITE * 1.0, false, 1.0],
		[mouth, fur * 0.8, false, 0.3], [wrap, RED, true, 0.5]]
	for k in 4:
		var kx := -12.0 + 7.5 * k
		l3.append([U.call([[kx, 66.0], [kx + 1.8, 75.2]]), RED * 0.4, false, 0.3])
	layers.append({"lines": l3, "occ": [head_occ, wrap]})

	# --- Rumpf: Ärmel, Weste, Riemen, Bauch, Rücken, Schwanz ---
	var sleeve := US.call([[-12.0, 62.5], [-15.4, 56.0], [-14.6, 49.6], [-12.6, 46.6], [-4.0, 46.0], [1.6, 46.6],
		[3.6, 52.0], [3.0, 58.0], [0.4, 62.5]], true) as PackedVector2Array
	var cuff := US.call([[-14.8, 50.6], [-5.0, 49.8], [3.0, 50.4]], false) as PackedVector2Array
	var vest := US.call([[16.6, 64.4], [20.6, 56.0], [22.6, 45.0], [22.2, 35.0], [19.6, 28.0], [19.6, 28.0],
		[8.0, 26.8], [-6.0, 27.8], [-19.6, 30.6], [-19.6, 30.6], [-22.6, 40.0], [-22.2, 52.0], [-19.2, 61.0],
		[-16.6, 64.6]], false) as PackedVector2Array
	var pocket := U.call([[10.0, 39.4], [19.2, 39.9]]) as PackedVector2Array
	var btn1 := U.call([[21.0, 36.0]]) as PackedVector2Array
	var btn2 := U.call([[20.2, 30.6]]) as PackedVector2Array
	var strap := US.call([[-20.6, 47.0], [-15.0, 55.0], [-11.0, 63.0]], false) as PackedVector2Array
	var belly := US.call([[19.6, 28.0], [20.8, 22.0], [17.8, 16.6], [11.0, 14.0]], false) as PackedVector2Array
	var back := US.call([[-19.6, 30.6], [-22.2, 24.0], [-19.8, 17.2], [-13.0, 14.0]], false) as PackedVector2Array
	var tail := US.call([[-21.4, 23.0], [-26.0, 21.4], [-26.6, 17.6], [-21.8, 17.6]], false) as PackedVector2Array
	var body_occ := US.call([[20.4, 66.0], [20.6, 56.0], [22.6, 45.0], [22.2, 35.0], [20.8, 22.0], [17.8, 16.6],
		[11.0, 13.8], [-13.0, 13.8], [-19.8, 17.2], [-22.4, 24.0], [-22.6, 40.0], [-22.2, 52.0], [-19.8, 70.2],
		[-16.6, 74.5]], true) as PackedVector2Array
	layers.append({"lines": [[sleeve, light * 0.8, true, 0.5], [cuff, light * 0.5, false, 0.4],
		[vest, GREEN * 0.9, false, 0.5], [pocket, GREEN * 0.55, false, 0.4],
		[btn1, YELLOW * 1.5, false, 1.0], [btn2, YELLOW * 1.5, false, 1.0],
		[strap, YELLOW * 0.5, false, 0.4], [belly, light * 0.85, false, 0.5], [back, fur * 1.1, false, 0.5],
		[tail, light * 0.6, false, 0.5]], "occ": [body_occ]})

	# --- Beine: vorn, dann hinten (vom vorderen und vom Rumpf verdeckt) ---
	var leg_n := _leg(Vector2(HIP_NEAR, HIP_Y + bob), fn_l)
	var claw_n := P([[fn_l.x + 9.4, fn_l.y + 1.0], [fn_l.x + 11.8, fn_l.y + 0.4]])
	layers.append({"lines": [[leg_n, fur * 1.35, false, 0.5], [claw_n, fur * 0.9, false, 0.6]], "occ": [_leg_occ(leg_n)]})
	var leg_f := _leg(Vector2(HIP_FAR, HIP_Y + bob), ff_l)
	# Umhängetasche hängt auf der fernen Seite am Rücken
	var satchel := US.call([[-17.0, 47.5], [-25.5, 46.6], [-28.6, 37.0], [-26.0, 29.4], [-17.0, 29.0]], false) as PackedVector2Array
	var flap := US.call([[-18.0, 46.8], [-27.0, 45.6], [-28.2, 39.5], [-18.0, 38.8]], false) as PackedVector2Array
	var buckle := U.call([[-25.2, 39.4]]) as PackedVector2Array
	layers.append({"lines": [[leg_f, fur * 0.85, false, 0.5], [satchel, YELLOW * 0.6, false, 0.5],
		[flap, YELLOW * 0.4, false, 0.4], [buckle, YELLOW * 1.2, false, 1.0]], "occ": [_leg_occ(leg_f), satchel]})
	return {"layers": layers, "feet": [fn, ff], "body_x": bx}


func _leg_occ(leg: PackedVector2Array) -> PackedVector2Array:
	return leg
