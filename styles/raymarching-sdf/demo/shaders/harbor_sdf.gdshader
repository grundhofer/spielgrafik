// Hafen von Lornholm, vollständig als Distanzfeld geraymarcht (Katalogeintrag raymarching-sdf).
// Ein Fragment-Shader auf einem ColorRect in einem 640×360-SubViewport; keine Meshes, keine Texturen.
// Weltkoordinaten wie shared/3d (Meter, +Y oben, Kamera blickt grob nach −Z, Kai bei y = 0,
// Wasserlinie y = −0,8). Zeit, Kamera, Laternenflackern, Leuchtfeuer und die Gelenkpunkte des Dachses
// kommen als Uniforms aus main.gd (aufsummiertes delta, deterministisch).
shader_type canvas_item;
render_mode unshaded;

uniform float t_sec = 0.0;
uniform vec3 cam_pos = vec3(-1.8, 3.4, 14.5);
uniform vec3 cam_tgt = vec3(-1.8, 2.876, 4.5);
uniform float cam_fov = 42.0;            // vertikal, Grad
uniform vec2 res = vec2(640.0, 360.0);
uniform float frame_no = 0.0;            // für das Rauschen der Volumen-Schritte
uniform float lantern_k = 1.0;           // Flackern der Laterne (0,6 … 1,1)
uniform float beam_yaw = 0.0;            // Drehwinkel des Leuchtfeuers (rad)
uniform float lamp_flash = 0.0;          // Aufblitzen, wenn der Strahl zur Kamera zeigt
// Dachs: Wurzel (Bodenpunkt), Blickrichtung, Gelenkpunkte im lokalen Raum (Blick +X, rechte Seite +Z)
uniform vec3 b_pos = vec3(0.0, 0.0, 1.2);
uniform float b_yaw = 0.0;
uniform vec3 bj[24];
uniform mat3 b_head_inv = mat3(1.0);     // lokal -> Kopfraum
// Qualität und Vergleichsschalter
uniform int max_steps = 160;             // Primärstrahl
uniform int shadow_steps = 40;           // weiche Schatten (Sonne)
uniform int refl_steps = 64;             // Spiegelung im Wasser
uniform int vol_steps = 10;              // Bodennebel
uniform int beam_steps = 14;             // Leuchtfeuer
uniform int cloud_steps = 24;            // tiefe Wolken
uniform int debug_mode = 0;              // 0 normal, 1 Schrittzahl, 2 ohne Volumen, 3 ohne Schatten/AO,
                                         // 4 Messmaske Dachs, 5 ohne Sonnenschatten, 6 ohne AO, 8 Schattenwerfer

const float WATER_Y = -0.8;
const float WAVE_A = 0.14;
const float FAR = 140.0;

const vec3 SUN = vec3(-0.7522, 0.2193, 0.6215);     // normalisiert: links vorn, 12,7° hoch
const vec3 SUN_COL = vec3(1.35, 0.6, 0.3);
const vec3 SKY_AMB = vec3(0.1, 0.11, 0.24);
const vec3 LANTERN_P = vec3(4.10, 1.79, -0.12);
const vec3 LANTERN_COL = vec3(1.0, 0.56, 0.22);
const vec3 WINDOW_P = vec3(-9.20, 1.45, 0.60);
const vec3 WINDOW_COL = vec3(1.0, 0.62, 0.28);
const vec3 LAMP_P = vec3(10.20, 12.58, -25.60);
const vec3 LAMP_COL = vec3(1.0, 0.86, 0.62);

// Materialnummern
const float M_PAVE = 1.0;
const float M_WALL = 2.0;
const float M_COPING = 3.0;
const float M_WOOD = 4.0;
const float M_WOODDARK = 5.0;
const float M_WHITE = 6.0;
const float M_RED = 7.0;
const float M_ROOF = 8.0;
const float M_WINDOW = 9.0;
const float M_METAL = 10.0;
const float M_TERRAIN = 11.0;
const float M_STONEDARK = 12.0;
const float M_COTTAGE = 13.0;
const float M_ROPE = 14.0;
const float M_LANTERN = 16.0;
const float M_LAMP = 17.0;
const float M_HULL_A = 18.0;
const float M_HULL_B = 19.0;
const float M_FUR = 20.0;
const float M_FURLIGHT = 21.0;
const float M_CAP = 22.0;
const float M_BRASS = 23.0;
const float M_VEST = 24.0;
const float M_SHIRT = 25.0;
const float M_SCARF = 26.0;
const float M_LEATHER = 27.0;
const float M_PARCEL = 28.0;
const float M_NOSE = 29.0;
const float M_EYE = 30.0;
const float M_HEAD = 31.0;
const float M_TORSO = 32.0;
const float M_SEAROCK = 15.0;
// Ohren des Dachses (Kopfraum, Seite gespiegelt)
const vec3 EAR_C = vec3(-0.03, 0.07, 0.15);
const vec3 EAR_R = vec3(0.02, 0.04, 0.036);

// ---------------------------------------------------------------------------------------------
// Rauschen (ohne Texturen; Hash ohne Sinus nach Dave Hoskins)
// ---------------------------------------------------------------------------------------------
// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash11(float p) { p = fract(p * 0.1031); p *= p + 33.33; p *= p + p; return fract(p); }
float hash12(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float hash13(vec3 p3) { p3 = fract(p3 * 0.1031); p3 += dot(p3, p3.zyx + 31.32); return fract((p3.x + p3.y) * p3.z); }

float vnoise2(vec2 x) {
	vec2 i = floor(x);
	vec2 f = fract(x);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash12(i);
	float b = hash12(i + vec2(1.0, 0.0));
	float c = hash12(i + vec2(0.0, 1.0));
	float d = hash12(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float vnoise3(vec3 x) {
	vec3 i = floor(x);
	vec3 f = fract(x);
	vec3 u = f * f * (3.0 - 2.0 * f);
	float n000 = hash13(i);
	float n100 = hash13(i + vec3(1.0, 0.0, 0.0));
	float n010 = hash13(i + vec3(0.0, 1.0, 0.0));
	float n110 = hash13(i + vec3(1.0, 1.0, 0.0));
	float n001 = hash13(i + vec3(0.0, 0.0, 1.0));
	float n101 = hash13(i + vec3(1.0, 0.0, 1.0));
	float n011 = hash13(i + vec3(0.0, 1.0, 1.0));
	float n111 = hash13(i + vec3(1.0, 1.0, 1.0));
	return mix(mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y),
			mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y), u.z);
}

float fbm2(vec2 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		s += a * vnoise2(p);
		p = mat2(vec2(1.6, 1.2), vec2(-1.2, 1.6)) * p;
		a *= 0.5;
	}
	return s;
}

float fbm3(vec3 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 3; i++) {
		s += a * vnoise3(p);
		p = p * 2.03 + vec3(1.7, 9.2, 3.1);
		a *= 0.5;
	}
	return s;
}

// ---------------------------------------------------------------------------------------------
// Grundkörper (Distanzfunktionen nach Inigo Quilez)
// ---------------------------------------------------------------------------------------------
// Distanzfunktionen nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions/
float sd_box(vec3 p, vec3 b) {
	vec3 q = abs(p) - b;
	return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}
float sd_rbox(vec3 p, vec3 b, float r) { return sd_box(p, b - r) - r; }
float sd_cyl(vec3 p, float r, float h) {      // senkrecht, Mitte im Ursprung, halbe Höhe h
	vec2 d = abs(vec2(length(p.xz), p.y)) - vec2(r, h);
	return min(max(d.x, d.y), 0.0) + length(max(d, 0.0));
}
float sd_capsule(vec3 p, vec3 a, vec3 b, float r) {
	vec3 pa = p - a;
	vec3 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h) - r;
}
float sd_rcone(vec3 p, vec3 a, vec3 b, float r1, float r2) {
	vec3 ba = b - a;
	float l2 = dot(ba, ba);
	float rr = r1 - r2;
	float a2 = l2 - rr * rr;
	float il2 = 1.0 / l2;
	vec3 pa = p - a;
	float y = dot(pa, ba);
	float z = y - l2;
	vec3 xv = pa * l2 - ba * y;
	float x2 = dot(xv, xv);
	float y2 = y * y * l2;
	float z2 = z * z * l2;
	float k = sign(rr) * rr * rr * x2;
	if (sign(z) * a2 * z2 > k) { return sqrt(x2 + z2) * il2 - r2; }
	if (sign(y) * a2 * y2 < k) { return sqrt(x2 + y2) * il2 - r1; }
	return (sqrt(x2 * a2 * il2) + y * rr) * il2 - r1;
}
float sd_ellipsoid(vec3 p, vec3 r) {
	float k0 = length(p / r);
	float k1 = length(p / (r * r));
	return k0 * (k0 - 1.0) / k1;
}
float sd_torus(vec3 p, float R, float r) {
	vec2 q = vec2(length(p.xz) - R, p.y);
	return length(q) - r;
}
float sd_capcone(vec3 p, float h, float r1, float r2) {   // senkrecht, y von −h bis h, Radien unten/oben
	vec2 q = vec2(length(p.xz), p.y);
	vec2 k1 = vec2(r2, h);
	vec2 k2 = vec2(r2 - r1, 2.0 * h);
	vec2 ca = vec2(q.x - min(q.x, (q.y < 0.0) ? r1 : r2), abs(q.y) - h);
	vec2 cb = q - k1 + k2 * clamp(dot(k1 - q, k2) / dot(k2, k2), 0.0, 1.0);
	float s = (cb.x < 0.0 && ca.y < 0.0) ? -1.0 : 1.0;
	return s * sqrt(min(dot(ca, ca), dot(cb, cb)));
}
// Weiche Vereinigung (smin) nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/smin/
float smin(float a, float b, float k) {
	float h = max(k - abs(a - b), 0.0) / k;
	return min(a, b) - h * h * k * 0.25;
}
float smax(float a, float b, float k) { return -smin(-a, -b, k); }

// Quadratische Bézier-Röhre: Abstand zur Kurve A-B-C (gibt Abstand und Kurvenparameter zurück)
// Quadratischer Bézier-Abstand nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
vec2 sd_bezier(vec3 pos, vec3 A, vec3 B, vec3 C) {
	vec3 a = B - A;
	vec3 b = A - 2.0 * B + C;
	vec3 c = a * 2.0;
	vec3 d = A - pos;
	float kk = 1.0 / max(dot(b, b), 1e-6);
	float kx = kk * dot(a, b);
	float ky = kk * (2.0 * dot(a, a) + dot(d, b)) / 3.0;
	float kz = kk * dot(d, a);
	vec2 res2;
	float p = ky - kx * kx;
	float p3 = p * p * p;
	float q = kx * (2.0 * kx * kx - 3.0 * ky) + kz;
	float h = q * q + 4.0 * p3;
	if (h >= 0.0) {
		h = sqrt(h);
		vec2 x = (vec2(h, -h) - q) / 2.0;
		vec2 uv = sign(x) * pow(abs(x), vec2(1.0 / 3.0));
		float t = clamp(uv.x + uv.y - kx, 0.0, 1.0);
		vec3 w = d + (c + b * t) * t;
		res2 = vec2(dot(w, w), t);
	} else {
		float z = sqrt(-p);
		float v = acos(q / (p * z * 2.0)) / 3.0;
		float m = cos(v);
		float n = sin(v) * 1.732050808;
		vec3 t3 = clamp(vec3(m + m, -n - m, n - m) * z - kx, 0.0, 1.0);
		vec3 w1 = d + (c + b * t3.x) * t3.x;
		float d1 = dot(w1, w1);
		vec3 w2 = d + (c + b * t3.y) * t3.y;
		float d2 = dot(w2, w2);
		res2 = (d1 < d2) ? vec2(d1, t3.x) : vec2(d2, t3.y);
	}
	return vec2(sqrt(res2.x), res2.y);
}

mat2 rot2(float a) { float c = cos(a); float s = sin(a); return mat2(vec2(c, s), vec2(-s, c)); }

void U(inout vec2 r, float d, float m) { if (d < r.x) { r = vec2(d, m); } }

// ---------------------------------------------------------------------------------------------
// Gelände: Felsnase rechts (Höhenfeld entlang einer Rückenlinie) und Insel links
// ---------------------------------------------------------------------------------------------
const int SPN = 7;
vec2 spine_pt(int i) {
	if (i == 0) { return vec2(11.2, 7.0); }
	if (i == 1) { return vec2(12.6, -1.0); }
	if (i == 2) { return vec2(13.3, -9.0); }
	if (i == 3) { return vec2(12.9, -16.5); }
	if (i == 4) { return vec2(11.4, -22.5); }
	if (i == 5) { return vec2(9.6, -26.2); }
	return vec2(8.4, -28.0);
}

// Abstand zur Rückenlinie und Lage s (0..1) entlang der Linie
vec2 spine_dist(vec2 p) {
	float best = 1e9;
	float bs = 0.0;
	float acc = 0.0;
	float total = 0.0;
	for (int i = 0; i < SPN - 1; i++) { total += length(spine_pt(i + 1) - spine_pt(i)); }
	for (int i = 0; i < SPN - 1; i++) {
		vec2 a = spine_pt(i);
		vec2 b = spine_pt(i + 1);
		vec2 ba = b - a;
		float L = length(ba);
		float h = clamp(dot(p - a, ba) / (L * L), 0.0, 1.0);
		float d = length(p - a - ba * h);
		if (d < best) { best = d; bs = (acc + h * L) / total; }
		acc += L;
	}
	return vec2(best, bs);
}

float headland_h(vec2 xz) {
	vec2 ds = spine_dist(xz);
	float s = ds.y;
	float w = mix(4.6, 3.4, s) + 1.1 * (vnoise2(vec2(s * 5.0, 9.7)) - 0.5) * 2.0;
	float top = 0.5 + 2.4 * smoothstep(0.2, 0.75, s);
	float edge = w - ds.x;
	float land = smoothstep(-1.6, 1.4, edge);
	float n = vnoise2(xz * 0.32) * 2.0 - 1.0;
	float h_top = top + 0.45 * n * smoothstep(0.0, 2.5, edge);
	float h = mix(-2.6, h_top, land);
	float dl = length(xz - vec2(10.2, -25.6));
	h = mix(2.75, h, smoothstep(2.2, 3.4, dl));
	return h;
}

float west_h(vec2 xz) {
	// Insel links hinter dem Häuschen (Godot: Mitte −18,5 | −2, Radien 13,6 und 17)
	vec2 e2 = (xz - vec2(-18.5, -2.0)) / vec2(13.6, 17.0);
	float e = 1.0 - length(e2);
	e += 0.09 * (vnoise2(xz * 0.07) * 2.0 - 1.0);
	float land = smoothstep(-0.06, 0.08, e);
	float rise = smoothstep(0.08, 0.6, e) * smoothstep(3.0, -10.0, xz.y);
	float hill = 6.0 * rise * (0.8 + 0.3 * (vnoise2(xz * 0.2) * 2.0 - 1.0));
	return mix(-2.6, 0.18, land) + hill * land;
}

float sd_terrain(vec3 p, out float rocky) {
	rocky = 0.0;
	float d = 1e9;
	// Felsnase: Höhenfeld, Lipschitz-Faktor 0,5; Felsrauschen nur nahe der Oberfläche
	if (p.x > 4.0 && p.x < 20.0 && p.z < 10.0 && p.z > -33.0) {
		float h = headland_h(p.xz);
		float dh = (p.y - h) * 0.5;
		if (dh < 1.6) {
			float cliff = smoothstep(0.2, 2.0, h + 2.6) * smoothstep(3.6, 1.2, h);
			float big = vnoise3(p * vec3(0.32, 0.5, 0.32));
			float rn = fbm3(p * vec3(1.0, 1.6, 1.0));
			dh -= cliff * (0.9 * (big - 0.5) + 0.35 * (rn - 0.45));
			dh *= 0.8;
			rocky = cliff;
		}
		d = dh;
	}
	if (p.x < -4.0 && p.z < 16.0) {
		float h = west_h(p.xz);
		float dh = (p.y - h) * 0.5;
		if (dh < 1.0) {
			float rn = fbm3(p * vec3(0.7, 1.1, 0.7));
			dh -= 0.25 * (rn - 0.45);
		}
		if (dh < d) { d = dh; rocky = 0.3; }
	}
	return d;
}

// Felsen im Wasser
float sd_searocks(vec3 p) {
	float d = 1e9;
	// (x, z, Größe) aus harbor_notes (RocksSea)
	vec3 R[8] = vec3[8](vec3(8.4, -3.2, 1.0), vec3(8.6, -8.0, 0.8), vec3(8.2, -13.0, 1.2), vec3(7.4, -19.5, 0.9),
			vec3(-5.9, -6.5, 0.8), vec3(-7.3, -12.0, 1.1), vec3(4.6, -17.0, 0.6), vec3(6.4, -29.5, 1.3));
	for (int i = 0; i < 8; i++) {
		vec3 c = vec3(R[i].x, WATER_Y + R[i].z * 0.08, R[i].y);
		float s = R[i].z;
		float db = length(p - c) - s * 1.5;
		if (db < d) {
			d = min(d, sd_ellipsoid(p - c, vec3(s * 1.2, s * 0.62, s)));
		}
	}
	if (d < 0.4) { d -= 0.3 * (fbm3(p * vec3(1.4, 2.2, 1.4)) - 0.45); }
	return d * 0.7;
}

// ---------------------------------------------------------------------------------------------
// Kai, Pflaster, Kantensteine, Poller
// ---------------------------------------------------------------------------------------------
float sd_quayblock(vec3 p) {
	float a = sd_box(p - vec3(-2.5, -1.325, 3.5), vec3(10.5, 1.275, 4.5));      // x −13..8, z −1..8, y −2,6..−0,05
	float b = sd_box(p - vec3(-9.0, -1.325, -2.3), vec3(4.0, 1.275, 1.3));      // linker Teil bis z = −3,6
	return min(a, b);
}

float sd_pave(vec3 p) {
	if (p.y > 0.12) { return p.y - 0.012; }
	float rz = floor(p.z / 0.68);
	float off = hash11(rz * 7.13 + 1.0);
	float len = 0.9 + 0.3 * hash11(rz * 3.7 + 5.0);
	float cx = floor((p.x + off) / len);
	float hz = hash12(vec2(cx, rz));
	vec3 c = vec3((cx + 0.5) * len - off, -0.028 + (hz - 0.5) * 0.014, (rz + 0.5) * 0.68);
	vec3 q = p - c;
	q.xz = rot2((hz - 0.5) * 0.03) * q.xz;
	float d = sd_rbox(q, vec3(len * 0.5 - 0.03, 0.03, 0.34 - 0.03), 0.028);
	return min(d, p.y + 0.05);
}

float sd_coping(vec3 p) {
	// entlang der Hinterkante (z −1,06 … −0,32), Lücke am Steg
	float d = 1e9;
	{
		float cell = 1.24;
		float id = floor((p.x + 5.62) / cell);
		float cx = -5.62 + (id + 0.5) * cell;
		vec3 q = p - vec3(cx, -0.06 + (hash11(id + 3.0) - 0.5) * 0.02, -0.69);
		float e = sd_rbox(q, vec3(cell * 0.5 - 0.022, 0.16, 0.37), 0.035);
		e = max(e, sd_box(p - vec3(1.22, 0.0, -0.69), vec3(6.84, 1.0, 1.0)));   // x −5,62 … 8,06
		e = max(e, -sd_box(p - vec3(3.45, 0.0, -0.69), vec3(0.86, 1.0, 1.0))); // Steg
		d = min(d, e);
	}
	// rechte Kante x 7,38 … 8,06, z −1 … 8
	{
		float cell = 1.2;
		float id = floor((p.z + 1.0) / cell);
		vec3 q = p - vec3(7.72, -0.06, -1.0 + (id + 0.5) * cell);
		float e = sd_rbox(q, vec3(0.34, 0.16, cell * 0.5 - 0.022), 0.035);
		e = max(e, sd_box(p - vec3(7.72, 0.0, 3.5), vec3(1.0, 1.0, 4.5)));
		d = min(d, e);
	}
	// Ecke links x −5,62 … −4,94, z −3,6 … −1
	{
		float cell = 1.3;
		float id = floor((p.z + 3.6) / cell);
		vec3 q = p - vec3(-5.28, -0.06, -3.6 + (id + 0.5) * cell);
		float e = sd_rbox(q, vec3(0.34, 0.16, cell * 0.5 - 0.022), 0.035);
		e = max(e, sd_box(p - vec3(-5.28, 0.0, -2.3), vec3(1.0, 1.0, 1.3)));
		d = min(d, e);
	}
	return d;
}

float sd_bollard(vec3 p) {
	float d = sd_capcone(p - vec3(0.0, 0.2, 0.0), 0.2, 0.16, 0.12);
	d = smin(d, sd_cyl(p - vec3(0.0, 0.43, 0.0), 0.18, 0.04) - 0.012, 0.03);
	d = smin(d, sd_ellipsoid(p - vec3(0.0, 0.47, 0.0), vec3(0.12, 0.07, 0.12)), 0.03);
	return d;
}

// ---------------------------------------------------------------------------------------------
// Steg
// ---------------------------------------------------------------------------------------------
float sd_jetty(vec3 p, out float mat) {
	mat = M_WOOD;
	vec3 q = p - vec3(3.45, 0.0, 0.0);
	// Planken quer zum Steg, z −0,45 … −8,6
	float id = floor((q.z + 0.45) / 0.2);
	float pz = -0.45 + (id + 0.5) * 0.2;
	float jy = (hash11(id * 1.7) - 0.5) * 0.012;
	float jx = (hash11(id * 3.1) - 0.5) * 0.05;
	float d = sd_rbox(q - vec3(jx, 0.015 + jy, pz), vec3(0.8, 0.025, 0.088), 0.01);
	d = max(d, sd_box(q - vec3(0.0, 0.0, -4.53), vec3(1.2, 1.0, 4.08)));
	// Längsträger, Querbalken, Pfähle
	float dk = 1e9;
	dk = min(dk, sd_box(vec3(abs(q.x) - 0.65, q.y + 0.09, q.z + 4.55), vec3(0.06, 0.07, 4.1)));
	dk = min(dk, sd_box(vec3(q.x, q.y + 0.09, q.z + 4.55), vec3(0.06, 0.07, 4.1)));
	float zc = clamp(floor((q.z + 0.45) / -2.0 + 0.5), 1.0, 4.0);
	float bz = -0.45 - zc * 2.0 + 0.15;
	dk = min(dk, sd_box(q - vec3(0.0, -0.3, bz), vec3(1.05, 0.08, 0.08)));
	vec3 pp = vec3(abs(q.x) - 0.92, q.y, q.z - bz);
	float top = (zc > 3.5) ? 0.79 : ((zc > 1.5 && zc < 2.5) ? 0.64 : -0.22);
	dk = min(dk, sd_capcone(pp - vec3(0.0, (top - 2.6) * 0.5, 0.0), (top + 2.6) * 0.5, 0.11, 0.1));
	if (dk < d) { d = dk; mat = M_WOODDARK; }
	return d;
}

// ---------------------------------------------------------------------------------------------
// Boote (Rumpf: Grundriss als Spitzbogen, Boden als Ellipsoid, schaukeln um die Wasserlinie)
// ---------------------------------------------------------------------------------------------
float sd_hull(vec3 p, float L, float W, float H, float D) {
	// Grundriss: Schnitt zweier Kreise (spitzer Bug bei +x), Heck gerade abgeschnitten
	float c = (L * L - W * W) / (2.0 * W);
	float R = c + W;
	float plan = max(length(vec2(p.x, p.z - c)) - R, length(vec2(p.x, p.z + c)) - R);
	plan = max(plan, -p.x - L * 0.82);
	float sheer = H + 0.16 * smoothstep(0.0, 1.0, p.x / L) + 0.05 * smoothstep(-0.2, -1.0, p.x / L);
	float bottom = sd_ellipsoid(p - vec3(0.0, sheer, 0.0), vec3(L * 1.08, sheer + D, W * 1.25));
	float d = smax(plan, bottom, 0.12);
	d = max(d, p.y - sheer);
	return d;
}

vec2 sd_boats(vec3 p) {
	vec2 r = vec2(1e9, 0.0);
	// Boot A: weiß mit rotem Streifen, Ruderhaus
	{
		vec3 q = p - vec3(0.05, WATER_Y + 0.03 * sin(t_sec * 1.1), -6.1);
		if (length(q) < 4.0) {
			q.xy = rot2(0.018 * sin(t_sec * 0.9 + 0.4)) * q.xy;
			q.yz = rot2(0.04 * sin(t_sec * 1.3)) * q.yz;
			float hull = sd_hull(q, 2.3, 0.875, 0.55, 0.42);
			float inner = sd_hull(q * vec3(1.06, 1.0, 1.12) + vec3(0.04, -0.2, 0.0), 2.3, 0.875, 0.55, 0.42);
			hull = max(hull, -inner);
			U(r, hull, M_HULL_A);
			// Ruderhaus und Dach
			float hut = sd_rbox(q - vec3(-0.55, 0.85, 0.0), vec3(0.52, 0.42, 0.5), 0.03);
			hut = max(hut, -sd_box(q - vec3(-0.15, 0.95, 0.0), vec3(0.2, 0.14, 0.6)));   // Fenster
			U(r, hut, M_WHITE);
			U(r, sd_rbox(q - vec3(-0.55, 1.29, 0.0), vec3(0.62, 0.035, 0.58), 0.02), M_RED);
			U(r, sd_capsule(q, vec3(-0.75, 1.3, 0.0), vec3(-0.75, 2.05, 0.0), 0.025), M_METAL);
			U(r, sd_box(q - vec3(0.6, 0.48, 0.0), vec3(0.7, 0.02, 0.7)) , M_WOOD);       // Deck vorn
		}
	}
	// Boot B: rot mit weißem Streifen, offen, Mast
	{
		vec3 q = p - vec3(6.75, WATER_Y + 0.03 * sin(t_sec * 1.3 + 2.0), -6.4);
		if (length(q) < 4.0) {
			q.xy = rot2(0.022 * sin(t_sec * 1.05 + 1.3)) * q.xy;
			q.yz = rot2(0.05 * sin(t_sec * 1.45 + 0.9)) * q.yz;
			float hull = sd_hull(q, 2.0, 0.775, 0.5, 0.38);
			float inner = sd_hull(q * vec3(1.07, 1.0, 1.14) + vec3(0.03, -0.12, 0.0), 2.0, 0.775, 0.5, 0.38);
			hull = max(hull, -inner);
			U(r, hull, M_HULL_B);
			U(r, sd_box(q - vec3(0.0, 0.3, 0.0), vec3(0.09, 0.025, 0.7)), M_WOOD);        // Ducht
			U(r, sd_box(q - vec3(-0.9, 0.3, 0.0), vec3(0.09, 0.025, 0.66)), M_WOOD);
			U(r, sd_capsule(q, vec3(0.6, 0.2, 0.0), vec3(0.6, 3.0, 0.0), 0.04), M_WOODDARK);
			U(r, sd_capsule(q, vec3(0.6, 0.85, 0.0), vec3(-1.3, 0.75, 0.0), 0.03), M_WOODDARK);
			U(r, sd_rbox(q - vec3(-0.3, 0.86, 0.0), vec3(0.9, 0.06, 0.05), 0.04), M_WHITE);  // gerefftes Segel
		}
	}
	return r;
}

// ---------------------------------------------------------------------------------------------
// Häuschen, Leuchtturm, Requisiten
// ---------------------------------------------------------------------------------------------
vec2 sd_cottage(vec3 p) {
	vec2 r = vec2(1e9, 0.0);
	vec3 q = p - vec3(-8.4, 0.0, -1.0);
	float walls = sd_box(q - vec3(0.0, 1.225, 0.0), vec3(1.8, 1.225, 1.5));
	// Giebel (Dach fällt nach vorn und hinten, First entlang x)
	vec3 g = q - vec3(0.0, 2.45, 0.0);
	vec2 nrm = normalize(vec2(1.35, 1.75));
	float slope = dot(vec2(abs(g.z), g.y), nrm) - 1.35 * 1.75 / length(vec2(1.35, 1.75)) * (1.5 / 1.75);
	float gable = max(max(slope + 0.0, abs(g.x) - 1.8), -g.y);
	walls = min(walls, gable);
	// Fenster vorn (−9,2 | 1,45) und Tür (−7,65), seitliches Fenster
	float win = sd_box(q - vec3(-0.8, 1.45, 1.5), vec3(0.41, 0.45, 0.12));
	float door = sd_box(q - vec3(0.75, 0.94, 1.5), vec3(0.45, 0.94, 0.08));
	float win2 = sd_box(q - vec3(1.8, 1.5, -0.4), vec3(0.12, 0.38, 0.35));
	walls = max(walls, -min(min(win, door), win2));
	U(r, walls, M_COTTAGE);
	// Glas mit Sprossen
	float glass = sd_box(q - vec3(-0.8, 1.45, 1.42), vec3(0.41, 0.45, 0.02));
	U(r, glass, M_WINDOW);
	float bars = min(sd_box(q - vec3(-0.8, 1.45, 1.46), vec3(0.025, 0.45, 0.03)), sd_box(q - vec3(-0.8, 1.45, 1.46), vec3(0.41, 0.025, 0.03)));
	bars = min(bars, max(sd_box(q - vec3(-0.8, 1.45, 1.5), vec3(0.47, 0.51, 0.06)), -sd_box(q - vec3(-0.8, 1.45, 1.5), vec3(0.41, 0.45, 0.2))));
	U(r, bars, M_WOODDARK);
	U(r, sd_box(q - vec3(1.75, 1.5, -0.4), vec3(0.02, 0.38, 0.35)), M_WINDOW);
	// Läden
	vec3 sq = q - vec3(-0.8, 1.45, 1.55);
	sq.x = abs(sq.x) - 0.66;
	U(r, sd_rbox(sq, vec3(0.22, 0.47, 0.035), 0.01), M_RED);
	// Tür
	U(r, sd_box(q - vec3(0.75, 0.94, 1.44), vec3(0.45, 0.94, 0.03)), M_WOODDARK);
	// Dach (Schiefer), Überstand
	float roof = max(slope - 0.16, -slope);
	roof = max(roof, max(abs(g.x) - 2.0, max(-g.y + 0.0 - 0.12, abs(g.z) - 1.78)));
	U(r, roof, M_ROOF);
	// Schornstein
	U(r, sd_box(q - vec3(-1.18, 3.85, -0.35), vec3(0.28, 0.95, 0.28)), M_COTTAGE);
	U(r, sd_box(q - vec3(-1.18, 4.82, -0.35), vec3(0.33, 0.06, 0.33)), M_STONEDARK);
	return r;
}

vec2 sd_lighthouse(vec3 p) {
	vec2 r = vec2(1e9, 0.0);
	vec3 q = p - vec3(10.2, 0.0, -25.6);
	U(r, sd_cyl(q - vec3(0.0, 2.75, 0.0), 1.65, 0.3) - 0.03, M_STONEDARK);
	float tower = sd_capcone(q - vec3(0.0, 7.0, 0.0), 4.2, 1.25, 0.86);
	U(r, tower, M_WHITE);   // rotes Band über die Höhe in der Schattierung
	U(r, sd_cyl(q - vec3(0.0, 11.3, 0.0), 1.22, 0.09) - 0.02, M_METAL);
	// Geländer
	float rail = sd_torus(q - vec3(0.0, 11.85, 0.0), 1.15, 0.025);
	float ang = atan(q.z, q.x);
	float sec = 2.0 * PI / 16.0;
	float a2 = mod(ang + sec * 0.5, sec) - sec * 0.5;
	vec2 pr = vec2(cos(a2), sin(a2)) * length(q.xz);
	rail = min(rail, sd_capsule(vec3(pr.x, q.y, pr.y), vec3(1.15, 11.35, 0.0), vec3(1.15, 11.85, 0.0), 0.018));
	U(r, rail, M_METAL);
	// Laternenhaus: Glas, Sprossen, Dach, Knauf
	float glass = sd_cyl(q - vec3(0.0, 12.55, 0.0), 0.62, 0.62);
	U(r, glass, M_LAMP);
	float sec8 = 2.0 * PI / 8.0;
	float a8 = mod(ang + sec8 * 0.5, sec8) - sec8 * 0.5;
	vec2 pm = vec2(cos(a8), sin(a8)) * length(q.xz);
	U(r, sd_box(vec3(pm.x - 0.63, q.y - 12.55, pm.y), vec3(0.03, 0.62, 0.035)), M_METAL);
	U(r, sd_capcone(q - vec3(0.0, 13.55, 0.0), 0.38, 0.82, 0.08), M_RED);
	U(r, length(q - vec3(0.0, 14.05, 0.0)) - 0.13, M_METAL);
	U(r, sd_capsule(q, vec3(0.0, 14.1, 0.0), vec3(0.0, 14.45, 0.0), 0.02), M_METAL);
	return r;
}

vec2 sd_props(vec3 p) {
	vec2 r = vec2(1e9, 0.0);
	// Fässer
	for (int i = 0; i < 2; i++) {
		vec3 c = (i == 0) ? vec3(-5.25, 0.0, -0.15) : vec3(-4.55, 0.0, -0.62);
		vec3 q = p - c - vec3(0.0, 0.45, 0.0);
		float bulge = 0.29 + 0.045 * cos(q.y * 3.0);
		float d = max(length(q.xz) - bulge, abs(q.y) - 0.45);
		d = max(d, -max(length(q.xz) - bulge + 0.035, q.y - 0.41));   // Deckel vertieft
		U(r, d, M_WOOD);
		float hoops = max(length(q.xz) - bulge - 0.008, abs(abs(q.y) - 0.3) - 0.03);
		U(r, hoops, M_METAL);
	}
	// Kistenstapel (6,55 | 0,2)
	{
		vec3 q = p - vec3(6.55, 0.0, 0.2);
		U(r, sd_rbox(q - vec3(0.0, 0.31, 0.0), vec3(0.31, 0.31, 0.31), 0.015), M_WOOD);
		U(r, sd_rbox(q - vec3(0.06, 0.91, -0.03), vec3(0.29, 0.29, 0.29), 0.015), M_WOOD);
		U(r, sd_rbox(q - vec3(0.02, 1.42, 0.02), vec3(0.22, 0.22, 0.22), 0.012), M_WOOD);
		U(r, sd_rbox(q - vec3(0.7, 0.22, 0.12), vec3(0.22, 0.22, 0.22), 0.012), M_WOOD);
	}
	// Taurolle
	{
		vec3 q = p - vec3(1.05, 0.0, 0.05);
		float d = sd_torus(q - vec3(0.0, 0.045, 0.0), 0.27, 0.045);
		d = min(d, sd_torus(q - vec3(0.0, 0.125, 0.0), 0.22, 0.045));
		d = min(d, sd_torus(q - vec3(0.0, 0.2, 0.0), 0.17, 0.042));
		U(r, d, M_ROPE);
	}
	// Poller an der Kante
	{
		float bx = (p.x < -1.35) ? -3.4 : ((p.x < 3.5) ? 0.7 : 6.3);
		U(r, sd_bollard(p - vec3(bx, 0.10, -0.7)), M_METAL);
	}
	// Laternenpfahl (4,6 | −0,12) mit Ausleger und Laterne bei (4,1 | 1,79)
	{
		vec3 q = p - vec3(4.6, 0.0, -0.12);
		U(r, sd_rbox(q - vec3(0.0, 0.11, 0.0), vec3(0.2, 0.11, 0.2), 0.02), M_STONEDARK);
		float post = sd_rbox(q - vec3(0.0, 1.25, 0.0), vec3(0.065, 1.2, 0.065), 0.01);
		post = min(post, sd_rbox(q - vec3(-0.27, 2.3, 0.0), vec3(0.34, 0.035, 0.035), 0.008));
		post = min(post, sd_capsule(q, vec3(0.0, 1.95, 0.0), vec3(-0.4, 2.3, 0.0), 0.022));
		U(r, post, M_WOODDARK);
		vec3 l = p - LANTERN_P;
		float frame = sd_box(l, vec3(0.115, 0.16, 0.115));
		frame = max(frame, -sd_box(l, vec3(0.085, 0.13, 0.2)));
		frame = max(frame, -sd_box(l, vec3(0.2, 0.13, 0.085)));
		frame = min(frame, sd_capcone(l - vec3(0.0, 0.215, 0.0), 0.055, 0.15, 0.03));
		frame = min(frame, sd_capsule(l, vec3(0.0, 0.27, 0.0), vec3(0.0, 0.51, 0.0), 0.012));
		frame = min(frame, sd_box(l + vec3(0.0, 0.18, 0.0), vec3(0.1, 0.02, 0.1)));
		U(r, frame, M_METAL);
		U(r, sd_box(l, vec3(0.095, 0.13, 0.095)), M_LANTERN);
	}
	return r;
}

// ---------------------------------------------------------------------------------------------
// Dachs-Kurier aus Grundkörpern; Gelenkpunkte bj[] im lokalen Raum (main.gd)
// ---------------------------------------------------------------------------------------------
vec3 to_badger(vec3 p) {
	vec3 q = p - b_pos;
	q.xz = rot2(b_yaw) * q.xz;
	return q;
}

vec2 sd_badger(vec3 p) {
	vec3 q = to_badger(p);
	vec2 r = vec2(1e9, 0.0);
	vec3 pel = bj[0];
	vec3 che = bj[1];
	// Rumpf: Bauch und Brust weich vereinigt
	float belly = sd_ellipsoid(q - pel - vec3(0.0, 0.06, 0.0), vec3(0.215, 0.205, 0.225));
	float chest = sd_ellipsoid(q - che, vec3(0.185, 0.175, 0.2));
	float torso = smin(belly, chest, 0.14);
	// Beine
	float legs = 1e9;
	for (int s = 0; s < 2; s++) {
		int o = 3 + s * 4;
		float th = sd_capsule(q, bj[o], bj[o + 1], 0.082);
		float sh = sd_capsule(q, bj[o + 1], bj[o + 2], 0.066);
		float ft = sd_rcone(q, bj[o + 2] + vec3(0.0, -0.01, 0.0), bj[o + 3], 0.058, 0.046);
		// Fuß nur schwach mit dem Unterschenkel verschmelzen (sonst wandert die Ferse mit dem Knie)
		// und das ganze Bein an der Sohle abschneiden, damit die Sohle eben bleibt
		float leg = smin(smin(th, sh, 0.04), ft, 0.012);
		leg = max(leg, -(q.y - (bj[o + 2].y - 0.066)));
		legs = min(legs, leg);
	}
	float body = smin(torso, legs, 0.07);
	U(r, body, M_TORSO);
	// Weste: Schale um den Rumpf zwischen Hüfte und Brust, vorn V-förmig offen
	float yrel = q.y - pel.y;
	float vest = max(torso - 0.016, abs(yrel - 0.215) - 0.16);
	float vx = q.x - pel.x;
	float vopen = max(-(vx - 0.05), abs(q.z - pel.z) - (0.025 + 0.32 * max(yrel - 0.1, 0.0)));
	vest = max(vest, -vopen);
	U(r, vest, M_VEST);
	// Riemen: Band schräg um den Rumpf (linke Schulter -> rechte Hüfte)
	vec3 sn = normalize(vec3(0.18, 0.55, 0.62));
	float strap = max(torso - 0.022, abs(dot(q - che - vec3(0.0, -0.02, 0.0), sn)) - 0.022);
	strap = max(strap, -(q.y - pel.y + 0.02));
	U(r, strap, M_LEATHER);
	// Tasche hinten an der rechten Hüfte
	vec3 sq = q - pel - vec3(-0.14, 0.03, 0.2);
	U(r, sd_rbox(sq, vec3(0.085, 0.085, 0.045), 0.022), M_LEATHER);
	// Arme: Hemdsärmel, Unterarm, Pfote
	for (int s = 0; s < 2; s++) {
		int o = 11 + s * 3;
		float sleeve = sd_capsule(q, bj[o], mix(bj[o], bj[o + 1], 0.9), 0.064);
		U(r, sleeve, M_SHIRT);
		float fore = sd_capsule(q, mix(bj[o], bj[o + 1], 0.85), bj[o + 2], 0.05);
		fore = smin(fore, length(q - bj[o + 2]) - 0.056, 0.03);
		U(r, fore, M_FUR);
	}
	// Paket unter dem rechten Arm
	{
		vec3 pq = q - bj[21];
		vec3 ax = normalize(bj[22]);
		vec3 az = normalize(cross(ax, vec3(0.0, 1.0, 0.0)));
		vec3 ay = cross(az, ax);
		vec3 lp = vec3(dot(pq, ax), dot(pq, ay), dot(pq, az));
		U(r, sd_rbox(lp, vec3(0.13, 0.09, 0.05), 0.012), M_PARCEL);
	}
	// Kopf (eigener Raum: gedreht um bj[2])
	vec3 h = b_head_inv * (q - bj[2]);
	float skull = sd_ellipsoid(h, vec3(0.15, 0.138, 0.148));
	float snout = sd_rcone(h, vec3(0.05, -0.03, 0.0), vec3(0.205, -0.05, 0.0), 0.088, 0.03);
	float head = smin(skull, snout, 0.07);
	vec3 he = vec3(h.x, h.y, abs(h.z));
	// Ohren seitlich unter dem Mützenrand (flache Scheiben mit Blick nach vorn, Saum hell im Shading)
	float ears = sd_ellipsoid(he - EAR_C, EAR_R);
	head = smin(head, ears, 0.02);
	// Hals unter dem Schal
	head = smin(head, sd_capsule(q, che, bj[2] - vec3(0.0, 0.05, 0.0), 0.1), 0.05);
	U(r, head, M_HEAD);
	U(r, length(h - vec3(0.232, -0.045, 0.0)) - 0.03, M_NOSE);
	U(r, length(he - vec3(0.113, 0.024, 0.091)) - 0.021, M_EYE);
	// Schirmmütze
	float crown = sd_ellipsoid(h - vec3(-0.01, 0.1, 0.0), vec3(0.168, 0.075, 0.162));
	crown = max(crown, -(h.y - 0.072));
	float brim = sd_ellipsoid(h - vec3(0.12, 0.08, 0.0), vec3(0.1, 0.014, 0.13));
	brim = max(brim, -(h.x - 0.03));
	U(r, min(crown, brim), M_CAP);
	U(r, length(he - vec3(0.115, 0.098, 0.085)) - 0.013, M_BRASS);
	// Schal: zwei Wicklungen um den Hals und zwei Enden als gebogene Röhren
	vec3 nq = q - che - vec3(0.0, 0.135, 0.0);
	nq.xy = rot2(-0.12) * nq.xy;
	float scarf = sd_torus(nq, 0.125, 0.052);
	scarf = smin(scarf, sd_torus(nq - vec3(0.0, 0.05, 0.0), 0.11, 0.045), 0.03);
	vec3 a0 = che + vec3(0.09, 0.125, 0.085);
	vec2 e1 = sd_bezier(q, a0, a0 + vec3(0.07, -0.09, 0.03), bj[17]);
	scarf = smin(scarf, e1.x - 0.036 + 0.008 * e1.y, 0.02);
	vec3 b0 = che + vec3(-0.1, 0.12, 0.07);
	vec2 e2 = sd_bezier(q, b0, bj[18], bj[19]);
	scarf = smin(scarf, e2.x - 0.034 + 0.006 * e2.y, 0.02);
	U(r, scarf, M_SCARF);
	// Schwanz
	U(r, sd_rcone(q, pel + vec3(-0.17, 0.02, 0.0), bj[20], 0.05, 0.022), M_FURLIGHT);
	return r;
}

// ---------------------------------------------------------------------------------------------
// Szene
// ---------------------------------------------------------------------------------------------
vec2 map(vec3 p) {
	vec2 r = vec2(1e9, 0.0);
	// Kai mit Pflaster
	float qb = sd_quayblock(p);
	if (qb < r.x + 0.3) {
		float pave = max(sd_pave(p), sd_box(p - vec3(-3.07, -0.5, 3.81), vec3(10.07, 0.6, 4.19)));
		pave = min(pave, max(sd_pave(p), sd_box(p - vec3(-9.31, -0.5, -2.3), vec3(3.69, 0.6, 1.3))));
		U(r, min(qb, pave), (qb < pave) ? M_WALL : M_PAVE);
		U(r, sd_coping(p), M_COPING);
	} else {
		r = vec2(qb, M_WALL);
	}
	// Steg
	float jb = sd_box(p - vec3(3.45, -1.0, -4.5), vec3(1.15, 1.85, 4.2));
	if (jb < r.x) {
		float jm;
		float jd = sd_jetty(p, jm);
		U(r, jd, jm);
	}
	// Requisiten
	float pb = sd_box(p - vec3(1.0, 1.2, -0.3), vec3(6.6, 1.4, 1.0));
	if (pb < r.x) {
		vec2 pr = sd_props(p);
		U(r, pr.x, pr.y);
	}
	// Häuschen
	float cb = sd_box(p - vec3(-8.4, 2.5, -1.0), vec3(2.2, 2.6, 2.0));
	if (cb < r.x) {
		vec2 cr = sd_cottage(p);
		U(r, cr.x, cr.y);
	}
	// Leuchtturm
	float lb = sd_box(p - vec3(10.2, 8.5, -25.6), vec3(1.8, 6.1, 1.8));
	if (lb < r.x) {
		vec2 lr = sd_lighthouse(p);
		U(r, lr.x, lr.y);
	}
	// Boote
	float bb = min(sd_box(p - vec3(0.05, -0.2, -6.1), vec3(2.7, 2.5, 1.3)), sd_box(p - vec3(6.75, 0.6, -6.4), vec3(2.4, 2.6, 1.2)));
	if (bb < r.x) {
		vec2 br = sd_boats(p);
		U(r, br.x, br.y);
	}
	// Gelände und Felsen
	float rocky;
	float td = sd_terrain(p, rocky);
	U(r, td, M_TERRAIN);
	if (p.y < 1.0) {
		U(r, sd_searocks(p), M_SEAROCK);
	}
	// Dachs
	float db = length(p - b_pos - vec3(0.0, 0.52, 0.0)) - 0.72;
	if (db < r.x) {
		vec2 dr = sd_badger(p);
		U(r, dr.x, dr.y);
	}
	return r;
}

float map_d(vec3 p) { return map(p).x; }

// Normale, weiche Schatten und Umgebungsverdeckung nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/normalsSDF/, https://iquilezles.org/articles/rmshadows/
vec3 calc_normal(vec3 p, float t) {
	float e = 0.0006 * max(t, 1.0);
	vec2 k = vec2(1.0, -1.0);
	return normalize(k.xyy * map_d(p + k.xyy * e) + k.yyx * map_d(p + k.yyx * e) +
			k.yxy * map_d(p + k.yxy * e) + k.xxx * map_d(p + k.xxx * e));
}

// Primärstrahl: Kugelverfolgung mit Abbruch bei 0,5 Pixel Fußabdruck
vec3 march(vec3 ro, vec3 rd, float tmax, int steps) {
	float t = 0.05;
	float m = -1.0;
	float pix = 1.6 * tan(radians(cam_fov) * 0.5) / res.y;
	int n = 0;
	for (int i = 0; i < 400; i++) {
		if (i >= steps) { break; }
		n = i + 1;
		vec3 p = ro + rd * t;
		vec2 h = map(p);
		if (abs(h.x) < pix * t * 0.5) { m = h.y; break; }
		t += h.x * 0.9;
		if (t > tmax) { break; }
	}
	if (t > tmax) { m = -1.0; }
	return vec3(t, m, float(n));
}

float soft_shadow(vec3 ro, vec3 rd, float tmin, float tmax, float k, int steps) {
	// klassische Fassung (k·h/t); die „verbesserte“ mit dem vorigen Abstand verträgt keine Mindestschrittweite
	float res2 = 1.0;
	float t = tmin;
	for (int i = 0; i < 64; i++) {
		if (i >= steps) { break; }
		float h = map_d(ro + rd * t);
		res2 = min(res2, k * h / t);
		t += clamp(h, 0.02, 0.6);
		if (res2 < 0.002 || t > tmax) { break; }
	}
	res2 = clamp(res2, 0.0, 1.0);
	return res2 * res2 * (3.0 - 2.0 * res2);
}

float calc_ao(vec3 p, vec3 n) {
	float occ = 0.0;
	float sca = 1.0;
	for (int i = 0; i < 5; i++) {
		float h = 0.02 + 0.11 * float(i);
		float d = map_d(p + n * h);
		occ += (h - d) * sca;
		sca *= 0.82;
	}
	return clamp(1.0 - 2.2 * occ, 0.0, 1.0);
}

// ---------------------------------------------------------------------------------------------
// Wasser: Höhenfeld aus überlagerten Wellen
// ---------------------------------------------------------------------------------------------
float waves(vec2 p, float detail) {
	float h = 0.0;
	float tt = t_sec;
	h += 0.05 * sin(dot(p, vec2(0.15, 0.99)) * 0.42 + tt * 0.85 + 0.8 * sin(p.x * 0.11));   // lange Dünung
	h += 0.032 * sin(dot(p, vec2(0.28, 0.96)) * 1.15 + tt * 1.35);
	h += 0.022 * sin(dot(p, vec2(-0.62, 0.78)) * 1.9 + tt * 1.85);
	h += 0.014 * sin(dot(p, vec2(0.92, 0.39)) * 3.2 - tt * 2.3);
	h -= 0.016 * abs(sin(dot(p, vec2(0.1, 0.995)) * 2.4 + tt * 2.0 + 0.6 * sin(p.x * 0.7)));
	if (detail > 0.0) {
		h += detail * 0.018 * (vnoise2(p * vec2(2.2, 3.4) + vec2(tt * 0.35, tt * 0.6)) - 0.5);
		h += detail * 0.008 * (vnoise2(p * vec2(5.5, 7.0) - vec2(tt * 0.5, tt * 0.9)) - 0.5);
	}
	return WATER_Y + h;
}

// Schnitt mit dem Höhenfeld zwischen t0 und t1 (lineare Suche + Halbierung)
float water_hit(vec3 ro, vec3 rd, float t0, float t1) {
	float a = t0;
	float fa = ro.y + rd.y * a - waves((ro + rd * a).xz, 0.0);
	for (int i = 1; i <= 10; i++) {
		float b = mix(t0, t1, float(i) / 10.0);
		float fb = ro.y + rd.y * b - waves((ro + rd * b).xz, 0.0);
		if (fb < 0.0) {
			for (int j = 0; j < 5; j++) {
				float m = 0.5 * (a + b);
				float fm = ro.y + rd.y * m - waves((ro + rd * m).xz, 0.0);
				if (fm < 0.0) { b = m; } else { a = m; }
			}
			return 0.5 * (a + b);
		}
		a = b;
		fa = fb;
	}
	return -1.0;
}

vec3 water_normal(vec2 p, float t) {
	float detail = clamp(1.0 - t / 45.0, 0.0, 1.0);
	float e = 0.02 + t * 0.002;
	float h0 = waves(p, detail);
	float hx = waves(p + vec2(e, 0.0), detail);
	float hz = waves(p + vec2(0.0, e), detail);
	vec3 n = normalize(vec3(h0 - hx, e, h0 - hz));
	return normalize(mix(n, vec3(0.0, 1.0, 0.0), clamp(t / 400.0, 0.0, 0.5)));
}

// ---------------------------------------------------------------------------------------------
// Himmel, Sterne, ferne Inseln, Wolken
// ---------------------------------------------------------------------------------------------
vec3 sky_color(vec3 rd) {
	float e = rd.y;
	float sunAz = max(dot(normalize(rd.xz), normalize(SUN.xz)), 0.0);
	vec3 zen = vec3(0.012, 0.016, 0.055);
	vec3 high = vec3(0.03, 0.035, 0.11);
	vec3 mid = vec3(0.17, 0.075, 0.18);
	vec3 low = vec3(1.1, 0.42, 0.16);
	vec3 col = mix(low, mid, smoothstep(-0.01, 0.07, e));
	col = mix(col, high, smoothstep(0.06, 0.26, e));
	col = mix(col, zen, smoothstep(0.26, 0.8, e));
	// Glut am Horizont, stärker zur Sonne hin
	col += vec3(1.2, 0.42, 0.1) * exp(-max(e, 0.0) * 45.0) * (0.45 + 0.55 * pow(sunAz, 3.0));
	col += vec3(0.5, 0.18, 0.06) * pow(max(dot(rd, SUN), 0.0), 10.0);
	return col;
}

vec3 stars(vec3 rd) {
	if (rd.y < 0.08) { return vec3(0.0); }
	vec2 sp = vec2(atan(rd.z, rd.x), asin(rd.y)) * 95.0;
	vec2 id = floor(sp);
	vec2 f = fract(sp) - 0.5;
	float h = hash12(id);
	if (h < 0.93) { return vec3(0.0); }
	vec2 o = vec2(hash12(id + 7.1), hash12(id + 3.3)) - 0.5;
	float d = length(f - o * 0.6);
	float tw = 0.65 + 0.35 * sin(t_sec * (2.0 + 4.0 * h) + h * 50.0);
	float s = smoothstep(0.18, 0.0, d) * (h - 0.93) * 14.0 * tw;
	return vec3(0.9, 0.92, 1.0) * s * smoothstep(0.08, 0.25, rd.y);
}

// ferne Inseln als Ellipsoide (analytisch geschnitten), Rückgabe: Abstand oder −1
float islands(vec3 ro, vec3 rd) {
	float best = -1.0;
	vec4 I[4] = vec4[4](vec4(-105.0, -185.0, 35.0, 13.0), vec4(-40.0, -230.0, 27.0, 10.0),
			vec4(12.0, -320.0, 30.0, 11.0), vec4(55.0, -200.0, 40.0, 15.0));
	float hh[4] = float[4](14.0, 9.0, 7.0, 18.0);
	for (int i = 0; i < 4; i++) {
		vec3 c = vec3(I[i].x, WATER_Y - 3.0, I[i].y);
		vec3 rr = vec3(I[i].z, hh[i] * 0.55 + 3.0, I[i].w);
		vec3 oc = (ro - c) / rr;
		vec3 dd = rd / rr;
		float a = dot(dd, dd);
		float b = dot(oc, dd);
		float cc = dot(oc, oc) - 1.0;
		float h = b * b - a * cc;
		if (h > 0.0) {
			float t = (-b - sqrt(h)) / a;
			vec3 hp = ro + rd * t;
			// unruhige Kuppe
			float n = vnoise2(hp.xz * 0.08 + float(i) * 7.0);
			float cap = (hh[i] * 0.55) * (0.55 + 0.6 * n);
			if (t > 0.0 && hp.y > WATER_Y && (hp.y - WATER_Y) < cap && (best < 0.0 || t < best)) {
				best = t;
			}
		}
	}
	return best;
}

float cloud_den(vec3 p) {
	vec3 w = p * vec3(0.014, 0.034, 0.022) + vec3(t_sec * 0.016, 0.0, t_sec * 0.005);
	float hfrac = (p.y - 38.0) / 32.0;
	float shape = smoothstep(0.0, 0.25, hfrac) * smoothstep(1.0, 0.45, hfrac);
	float d = fbm3(w) * shape - 0.45;
	d += 0.12 * (vnoise3(w * 3.3) - 0.5);
	return d;
}

vec4 clouds(vec3 ro, vec3 rd, float jit) {
	// Tiefe Wolkenschicht zwischen 38 und 70 m, wenige Schritte mit Versatz
	if (rd.y < 0.012) { return vec4(0.0); }
	float t0 = (38.0 - ro.y) / rd.y;
	float t1 = min((70.0 - ro.y) / rd.y, t0 + 450.0);
	float dt = (t1 - t0) / float(cloud_steps);
	float T = 1.0;
	vec3 acc = vec3(0.0);
	float t = t0 + dt * jit;
	for (int i = 0; i < 32; i++) {
		if (i >= cloud_steps) { break; }
		vec3 p = ro + rd * t;
		float hfrac = (p.y - 38.0) / 32.0;
		float den = cloud_den(p);
		if (den > 0.0) {
			den = min(den * 6.0, 1.0);
			float sunside = 0.5 + 0.5 * dot(normalize(rd.xz), normalize(SUN.xz));
			// ein Lichtschritt Richtung Sonne: Selbstschatten gibt den Wolken Form
			float dl = max(cloud_den(p + normalize(vec3(SUN.x, 0.25, SUN.z)) * 12.0), 0.0);
			float lit = exp(-dl * 14.0);
			vec3 sunlit = vec3(1.05, 0.42, 0.2) * (0.35 + 0.75 * sunside);
			vec3 shade_c = vec3(0.11, 0.075, 0.16);
			vec3 lc = mix(shade_c, sunlit, lit * (1.0 - 0.6 * smoothstep(0.2, 0.9, hfrac)));
			float a = 1.0 - exp(-den * dt * 0.16);
			acc += T * a * lc;
			T *= 1.0 - a;
			if (T < 0.03) { break; }
		}
		t += dt;
	}
	float fade = smoothstep(0.012, 0.05, rd.y);
	// ferne Wolken gehen im Dunst des Horizonts auf
	vec3 hz = sky_color(normalize(vec3(rd.x, 0.02, rd.z)));
	float haze = smoothstep(0.12, 0.02, rd.y);
	acc = mix(acc, hz * 0.6 * (1.0 - T), haze * 0.6);
	return vec4(acc, (1.0 - T) * fade);
}

vec3 background(vec3 ro, vec3 rd, float jit, bool with_clouds) {
	vec3 col = sky_color(rd) + stars(rd);
	if (with_clouds) {
		vec4 c = clouds(ro, rd, jit);
		col = col * (1.0 - c.a) + c.rgb;
	}
	float ti = islands(ro, rd);
	if (ti > 0.0) {
		vec3 isl = vec3(0.05, 0.04, 0.08);
		vec3 hz = sky_color(normalize(vec3(rd.x, 0.0, rd.z)));
		isl = mix(isl, hz * 0.55, 1.0 - exp(-ti * 0.004));
		col = isl;
	}
	return col;
}

// ---------------------------------------------------------------------------------------------
// Materialien
// ---------------------------------------------------------------------------------------------
struct Mat { vec3 alb; float spec; float gloss; vec3 emit; float fuzz; };

// Steinmuster (Mauerwerk) in einer Ebene: gibt Fugenmaske zurück (1 = Fuge)
float masonry(vec2 uv, vec2 size, out vec2 cid) {
	float row = floor(uv.y / size.y);
	float off = hash11(row * 5.3) * size.x;
	float col = floor((uv.x + off) / size.x);
	cid = vec2(col, row);
	vec2 f = vec2(fract((uv.x + off) / size.x) * size.x, fract(uv.y / size.y) * size.y);
	float e = min(min(f.x, size.x - f.x), min(f.y, size.y - f.y));
	return 1.0 - smoothstep(0.012, 0.03, e);
}

Mat material(float m, vec3 p, vec3 n) {
	Mat M;
	M.alb = vec3(0.5);
	M.spec = 0.04;
	M.gloss = 16.0;
	M.emit = vec3(0.0);
	M.fuzz = 0.0;
	float grain = vnoise3(p * 9.0);
	if (m == M_PAVE) {
		vec2 cid = vec2(floor((p.x + hash11(floor(p.z / 0.68) * 7.13 + 1.0)) / 0.9), floor(p.z / 0.68));
		float v = hash12(cid);
		M.alb = mix(vec3(0.46, 0.43, 0.40), vec3(0.56, 0.52, 0.46), v) * (0.85 + 0.25 * grain);
		M.alb *= mix(1.0, 0.55, smoothstep(-0.005, -0.04, p.y));      // Fugen dunkel
		M.spec = 0.08;
		M.gloss = 24.0;
	} else if (m == M_WALL) {
		vec2 cid;
		vec2 uv = (abs(n.z) > 0.5) ? p.xy : p.zy;
		float j = masonry(uv, vec2(0.62, 0.3), cid);
		float v = hash12(cid);
		M.alb = mix(vec3(0.34, 0.33, 0.32), vec3(0.45, 0.42, 0.38), v) * (0.8 + 0.3 * grain);
		M.alb *= 1.0 - 0.45 * j;
		float wet = smoothstep(-0.45, -0.75, p.y);
		M.alb = mix(M.alb, vec3(0.12, 0.16, 0.12), wet * 0.8);
		M.spec = 0.04 + 0.2 * wet;
	} else if (m == M_COPING || m == M_STONEDARK) {
		M.alb = vec3(0.30, 0.29, 0.28) * (0.8 + 0.35 * grain);
		M.spec = 0.06;
	} else if (m == M_COTTAGE) {
		vec2 cid;
		vec2 uv = (abs(n.z) > 0.5) ? p.xy : p.zy;
		float j = masonry(uv, vec2(0.42, 0.24), cid);
		float v = hash12(cid);
		M.alb = mix(vec3(0.44, 0.41, 0.37), vec3(0.6, 0.55, 0.47), v) * (0.85 + 0.25 * grain);
		M.alb *= 1.0 - 0.5 * j;
	} else if (m == M_WOOD) {
		float g2 = vnoise3(p * vec3(2.0, 30.0, 2.0));
		M.alb = mix(vec3(0.36, 0.22, 0.12), vec3(0.52, 0.34, 0.19), g2) * (0.85 + 0.2 * grain);
		M.spec = 0.05;
	} else if (m == M_WOODDARK) {
		M.alb = vec3(0.2, 0.13, 0.08) * (0.8 + 0.4 * grain);
	} else if (m == M_WHITE) {
		M.alb = vec3(0.8, 0.78, 0.72);
		M.spec = 0.1;
		M.gloss = 30.0;
		// rotes Band am Leuchtturm
		if (p.z < -20.0) {
			float band = step(6.6, p.y) * step(p.y, 7.8);
			M.alb = mix(M.alb, vec3(0.62, 0.1, 0.08), band);
			// Tür und kleine Fenster zur Kamera
			vec3 q = p - vec3(10.2, 0.0, -25.6);
			float front = step(0.0, q.z);
			float door = step(abs(q.x), 0.32) * step(q.y, 4.7) * front;
			float wins = step(abs(q.x), 0.12) * front * (step(abs(q.y - 5.6), 0.25) + step(abs(q.y - 9.2), 0.25));
			M.alb = mix(M.alb, vec3(0.18, 0.12, 0.08), max(door, wins));
		}
	} else if (m == M_RED) {
		M.alb = vec3(0.55, 0.1, 0.07);
		M.spec = 0.08;
	} else if (m == M_ROOF) {
		float row = fract(p.y / 0.16);
		float col2 = fract(p.x / 0.3 + hash11(floor(p.y / 0.16)) * 0.5);
		float j = max(smoothstep(0.85, 1.0, row), smoothstep(0.9, 1.0, col2));
		M.alb = vec3(0.2, 0.22, 0.27) * (0.85 + 0.3 * hash12(floor(vec2(p.x / 0.3, p.y / 0.16)))) * (1.0 - 0.35 * j);
		M.spec = 0.08;
		M.gloss = 20.0;
	} else if (m == M_WINDOW) {
		M.alb = vec3(0.1);
		M.emit = WINDOW_COL * 2.2;
	} else if (m == M_METAL) {
		M.alb = vec3(0.12, 0.12, 0.13);
		M.spec = 0.4;
		M.gloss = 40.0;
	} else if (m == M_TERRAIN || m == M_SEAROCK) {
		float rocky = smoothstep(0.82, 0.55, n.y + 0.15 * (vnoise3(p * 0.8) - 0.5));
		if (m == M_SEAROCK) { rocky = 1.0; }
		float strata = 0.5 + 0.5 * sin(p.y * 7.0 + 2.5 * vnoise3(p * 0.6));
		vec3 rock = vec3(0.2, 0.19, 0.19) * (0.65 + 0.35 * vnoise3(p * 1.7) + 0.2 * strata);
		vec3 grass = mix(vec3(0.12, 0.16, 0.06), vec3(0.2, 0.24, 0.08), vnoise3(p * 0.9));
		vec3 sand = vec3(0.42, 0.36, 0.27);
		M.alb = mix(grass, rock, rocky);
		M.alb = mix(M.alb, sand, smoothstep(-0.2, -0.45, p.y) * (1.0 - rocky) );
		float wet = smoothstep(-0.55, -0.78, p.y);
		M.alb = mix(M.alb, vec3(0.1, 0.12, 0.1), wet * 0.8);
		M.spec = 0.03 + 0.25 * wet;
	} else if (m == M_ROPE) {
		float tw = sin(atan(p.z - 0.05, p.x - 1.05) * 40.0 + p.y * 120.0);
		M.alb = vec3(0.58, 0.48, 0.32) * (0.85 + 0.15 * tw);
	} else if (m == M_LANTERN) {
		M.alb = vec3(0.2);
		vec3 lq = (p - LANTERN_P) / vec3(0.095, 0.13, 0.095);
		float core = exp(-dot(lq.xz, lq.xz) * 2.5 - lq.y * lq.y * 2.0);
		M.emit = LANTERN_COL * (1.0 + 2.6 * core) * lantern_k;
	} else if (m == M_LAMP) {
		M.alb = vec3(0.2);
		M.emit = LAMP_COL * (1.6 + 1.6 * exp(-pow((p.y - 12.55) * 2.2, 2.0)) + 6.0 * lamp_flash);
	} else if (m == M_HULL_A || m == M_HULL_B) {
		vec3 q = p - ((m == M_HULL_A) ? vec3(0.05, WATER_Y, -6.1) : vec3(6.75, WATER_Y, -6.4));
		float y = q.y;
		vec3 c1 = (m == M_HULL_A) ? vec3(0.78, 0.76, 0.7) : vec3(0.58, 0.11, 0.08);
		vec3 c2 = (m == M_HULL_A) ? vec3(0.6, 0.1, 0.07) : vec3(0.78, 0.76, 0.7);
		M.alb = c1;
		M.alb = mix(M.alb, c2, step(0.3, y) * step(y, 0.42));
		M.alb = mix(M.alb, vec3(0.35, 0.22, 0.12), step(0.5, y));
		M.alb = mix(M.alb, vec3(0.12, 0.08, 0.06), step(y, 0.06));
		if (n.y > 0.6) { M.alb = vec3(0.42, 0.28, 0.16); }      // Innenraum, Planken
		M.spec = 0.12;
		M.gloss = 30.0;
	} else if (m >= M_FUR) {
		// Dachs: Muster im lokalen Raum
		vec3 q = to_badger(p);
		M.fuzz = 1.0;
		M.spec = 0.03;
		if (m == M_TORSO) {
			vec3 pel = bj[0];
			float yrel = q.y - pel.y;
			float front = smoothstep(0.02, 0.1, q.x - pel.x);
			float belly = front * smoothstep(0.03, 0.0, yrel - 0.12) * smoothstep(-0.18, -0.1, yrel);
			// heller Bauch nur als Mittelfeld wie im Referenzblatt; Flanken und Oberschenkel dunkel
			belly *= smoothstep(0.15, 0.09, abs(q.z - pel.z)) * smoothstep(-0.11, -0.05, yrel);
			// Hemd im V der Weste
			float shirt = front * smoothstep(0.12, 0.16, yrel);
			M.alb = mix(vec3(0.075, 0.068, 0.068), vec3(0.78, 0.72, 0.62), belly);
			M.alb = mix(M.alb, vec3(0.8, 0.72, 0.58), shirt);
			M.fuzz = 1.0 - shirt;
		} else if (m == M_FUR) {
			M.alb = vec3(0.075, 0.068, 0.068);
		} else if (m == M_FURLIGHT) {
			M.alb = vec3(0.78, 0.72, 0.62);
		} else if (m == M_HEAD) {
			vec3 h = b_head_inv * (q - bj[2]);
			// dunkle Streifen von der Schnauze über die Augen zu den Ohren (je Seite eine Röhre aus
			// zwei Strecken), weißer Mittelstreifen und Wangen, Hinterkopf dunkel
			vec3 hz = vec3(h.x, h.y, abs(h.z));
			vec3 s0 = vec3(0.2, -0.018, 0.032);
			vec3 s1 = vec3(0.112, 0.024, 0.088);
			vec3 s2 = vec3(-0.035, 0.085, 0.118);
			vec3 b1 = s1 - s0;
			float k1 = clamp(dot(hz - s0, b1) / dot(b1, b1), 0.0, 1.0);
			float d1 = length(hz - s0 - b1 * k1) - mix(0.016, 0.04, k1);
			vec3 b2 = s2 - s1;
			float k2 = clamp(dot(hz - s1, b2) / dot(b2, b2), 0.0, 1.0);
			float d2 = length(hz - s1 - b2 * k2) - mix(0.04, 0.05, k2);
			float stripe = 1.0 - smoothstep(-0.004, 0.004, min(d1, d2));
			float back = smoothstep(-0.05, -0.1, h.x);
			float dark = max(stripe, back);
			// Ohr: innen dunkel, Saum hell
			vec3 eq = (hz - EAR_C) / EAR_R;
			float on_ear = 1.0 - smoothstep(1.15, 1.35, length(eq));
			dark = mix(dark, 1.0 - smoothstep(0.6, 0.75, length(eq.yz)), on_ear);
			M.alb = mix(vec3(0.82, 0.78, 0.7), vec3(0.075, 0.068, 0.068), dark);
			// Mund
			float mouth = (1.0 - smoothstep(0.004, 0.009, abs(h.y + 0.085 - 0.25 * (h.x - 0.12) * (h.x - 0.12) * 4.0))) * step(0.06, h.x) * step(h.x, 0.18);
			M.alb = mix(M.alb, vec3(0.1, 0.06, 0.05), mouth * smoothstep(0.02, 0.04, abs(h.z)));
		} else if (m == M_CAP) {
			vec3 h = b_head_inv * (q - bj[2]);
			M.alb = vec3(0.16, 0.2, 0.1);
			float band = step(h.y, 0.098) * step(h.x, 0.07);
			M.alb = mix(M.alb, vec3(0.3, 0.14, 0.08), band);
			M.fuzz = 0.2;
		} else if (m == M_BRASS) {
			M.alb = vec3(0.6, 0.42, 0.14);
			M.spec = 0.6;
			M.gloss = 60.0;
			M.fuzz = 0.0;
		} else if (m == M_VEST) {
			vec3 pel = bj[0];
			float yrel = q.y - pel.y;
			M.alb = vec3(0.19, 0.23, 0.11) * (0.9 + 0.2 * grain);
			// Taschenklappen und Knöpfe vorn
			float flap = (1.0 - smoothstep(0.004, 0.01, abs(yrel - 0.16))) * step(0.1, q.x - pel.x);
			M.alb *= 1.0 - 0.45 * flap;
			vec2 bp = vec2(q.y - pel.y, abs(q.z - pel.z));
			float btn = 0.0;
			for (int i = 0; i < 3; i++) {
				float by = 0.2 + 0.08 * float(i);
				float bz = 0.05 + 0.32 * (by - 0.1) + 0.012;
				btn = max(btn, 1.0 - smoothstep(0.01, 0.014, length(bp - vec2(by, bz))));
			}
			btn *= step(0.12, q.x - pel.x);
			M.alb = mix(M.alb, vec3(0.62, 0.44, 0.15), btn);
			M.fuzz = 0.25;
		} else if (m == M_SHIRT) {
			M.alb = vec3(0.8, 0.72, 0.58);
			M.fuzz = 0.2;
		} else if (m == M_SCARF) {
			float rib = sin((q.x * 2.0 + q.y * 3.0 + q.z * 2.0) * 90.0);
			M.alb = vec3(0.6, 0.07, 0.07) * (0.85 + 0.15 * rib);
			M.fuzz = 0.7;
		} else if (m == M_LEATHER) {
			M.alb = vec3(0.3, 0.13, 0.07);
			M.spec = 0.12;
			M.gloss = 30.0;
			M.fuzz = 0.0;
		} else if (m == M_PARCEL) {
			vec3 pq = q - bj[21];
			vec3 ax = normalize(bj[22]);
			vec3 az = normalize(cross(ax, vec3(0.0, 1.0, 0.0)));
			vec3 ay = cross(az, ax);
			vec3 lp = vec3(dot(pq, ax), dot(pq, ay), dot(pq, az));
			float str = max(1.0 - smoothstep(0.006, 0.011, abs(lp.x - 0.02)), 1.0 - smoothstep(0.006, 0.011, abs(lp.y + 0.005)));
			M.alb = mix(vec3(0.55, 0.36, 0.2), vec3(0.85, 0.78, 0.62), str);
			M.fuzz = 0.0;
		} else if (m == M_NOSE) {
			M.alb = vec3(0.03, 0.025, 0.025);
			M.spec = 0.5;
			M.gloss = 60.0;
			M.fuzz = 0.0;
		} else if (m == M_EYE) {
			M.alb = vec3(0.02, 0.015, 0.012);
			M.spec = 1.0;
			M.gloss = 120.0;
			M.fuzz = 0.0;
		}
	}
	return M;
}

// ---------------------------------------------------------------------------------------------
// Licht
// ---------------------------------------------------------------------------------------------
vec3 point_light(vec3 p, vec3 n, vec3 rd, Mat M, vec3 lp, vec3 lc, float I, float rad, bool shadow) {
	vec3 L = lp - p;
	float d2 = dot(L, L);
	float d = sqrt(d2);
	vec3 l = L / d;
	float att = I / (1.0 + d2 / (rad * rad));
	float nl = max(dot(n, l), 0.0);
	if (M.fuzz > 0.0) { nl = mix(nl, max(dot(n, l) * 0.5 + 0.5, 0.0) * 0.8, M.fuzz * 0.5); }
	float sh = 1.0;
	if (shadow && nl > 0.0 && att > 0.02 && debug_mode != 3) { sh = soft_shadow(p + n * 0.02, l, 0.04, d - 0.2, 10.0, 20); }
	vec3 hv = normalize(l - rd);
	float sp = pow(max(dot(n, hv), 0.0), M.gloss) * M.spec * (M.gloss + 2.0) / 8.0;
	return lc * att * sh * (nl * M.alb + sp * nl);
}

vec3 shade(vec3 p, vec3 n, vec3 rd, float m, float t, bool full) {
	Mat M = material(m, p, n);
	float occ = 1.0;
	float sh = 1.0;
	float nl = dot(n, SUN);
	if (full && debug_mode != 3) {
		if (debug_mode != 6) { occ = calc_ao(p, n); }
		if (nl > 0.0 && debug_mode != 5) { sh = soft_shadow(p + n * 0.012, SUN, 0.04, 30.0, 10.0, shadow_steps); }
	}
	float dif = max(nl, 0.0);
	if (M.fuzz > 0.0) { dif = mix(dif, clamp(nl * 0.5 + 0.5, 0.0, 1.0) * 0.75, 0.5 * M.fuzz); }
	vec3 lin = vec3(0.0);
	lin += SUN_COL * dif * sh;
	lin += SKY_AMB * (0.55 + 0.45 * n.y) * occ;
	lin += vec3(0.26, 0.13, 0.08) * clamp(0.5 - 0.5 * n.y, 0.0, 1.0) * occ * 0.6;      // warmes Licht vom Boden
	float fre = pow(clamp(1.0 + dot(n, rd), 0.0, 1.0), 3.0);
	lin += vec3(0.55, 0.32, 0.32) * fre * occ * (0.25 + 0.6 * M.fuzz);                // Kante gegen den Abendhimmel
	vec3 col = M.alb * lin;
	// Glanz der Sonne
	vec3 hv = normalize(SUN - rd);
	col += SUN_COL * pow(max(dot(n, hv), 0.0), M.gloss) * M.spec * (M.gloss + 2.0) / 8.0 * dif * sh;
	// Punktlichter: Laterne (mit Schatten), Fenster, Leuchtfeuer
	col += point_light(p, n, rd, M, LANTERN_P, LANTERN_COL, 3.2 * lantern_k, 0.9, full && t < 25.0);
	if (p.z > 0.4) {
		col += point_light(p, n, rd, M, WINDOW_P, WINDOW_COL, 1.6, 1.0, false);
	}
	col += point_light(p, n, rd, M, LAMP_P, LAMP_COL, 3.0 * (1.0 + 2.0 * lamp_flash), 3.0, false);
	col *= mix(1.0, occ, 0.4);
	col += M.emit;
	return col;
}

// ---------------------------------------------------------------------------------------------
// Volumen: Leuchtfeuer, Bodennebel; Lichthöfe
// ---------------------------------------------------------------------------------------------
vec3 beam_dir() { return normalize(vec3(sin(beam_yaw), -0.01, cos(beam_yaw))); }

vec3 beam_volume(vec3 ro, vec3 rd, float tmax, float jit) {
	vec3 b = beam_dir();
	// Schritte nur um die Stelle, an der der Sehstrahl der Strahlachse am nächsten kommt:
	// Fensterbreite = 3 Kegelradien / sin(Winkel zwischen Sehstrahl und Achse)
	vec3 w0 = ro - LAMP_P;
	float bb = dot(rd, b);
	float dd = dot(rd, w0);
	float ee = dot(b, w0);
	float den0 = max(1.0 - bb * bb, 1e-4);
	float tc = (bb * ee - dd) / den0;
	float sc = (ee - bb * dd) / den0;
	float rad = 0.24 + abs(sc) * 0.036;
	float win = min(3.0 * rad / sqrt(den0), 160.0);
	float t0 = max(tc - win, 0.0);
	float t1 = min(tc + win, min(tmax, 300.0));
	if (t1 <= t0) { return vec3(0.0); }
	float dt = (t1 - t0) / float(beam_steps);
	vec3 acc = vec3(0.0);
	float t = t0 + dt * jit;
	for (int i = 0; i < 48; i++) {
		if (i >= beam_steps) { break; }
		vec3 p = ro + rd * t;
		vec3 v = p - LAMP_P;
		float along = dot(v, b);
		float aa = abs(along);
		float radial = length(v - b * along);
		float cone = 0.24 + aa * 0.036;
		float den = exp(-radial * radial / (cone * cone) * 1.6) * smoothstep(0.3, 2.0, aa) * exp(-aa / 45.0);
		den *= step(0.0, along);                        // ein Strahl
		den *= 0.7 + 0.6 * vnoise3(p * 0.35 + vec3(t_sec * 0.3, 0.0, 0.0));
		acc += den * dt;
		t += dt;
	}
	// mehr Licht, wenn der Strahl zur Kamera zeigt (Vorwärtsstreuung); weich begrenzt
	float ph = 0.8 + 1.2 * pow(max(dot(-rd, b), 0.0), 6.0);
	vec3 L = LAMP_COL * acc * 0.55 * ph;
	return 1.0 - exp(-L);
}

// Rauch aus dem Schornstein: Dichte um eine nach rechts gebogene Säule, die mit der Höhe breiter wird
const vec3 SMOKE_P = vec3(-9.58, 4.9, -1.35);
uniform int smoke_steps = 12;

vec4 chimney_smoke(vec3 ro, vec3 rd, float tmax, float jit) {
	// Schnitt mit einer Hülle (Kugel, Radius 2,4 m) um die Säule
	vec3 c0 = SMOKE_P + vec3(1.0, 1.7, -0.15);
	vec3 oc = ro - c0;
	float b = dot(oc, rd);
	float h = b * b - (dot(oc, oc) - 5.76);
	if (h < 0.0) { return vec4(0.0, 0.0, 0.0, 1.0); }
	h = sqrt(h);
	float t0 = max(-b - h, 0.0);
	float t1 = min(-b + h, tmax);
	if (t1 <= t0) { return vec4(0.0, 0.0, 0.0, 1.0); }
	float dt = (t1 - t0) / float(smoke_steps);
	float T = 1.0;
	vec3 acc = vec3(0.0);
	float t = t0 + dt * jit;
	for (int i = 0; i < 24; i++) {
		if (i >= smoke_steps) { break; }
		vec3 p = ro + rd * t;
		float hh = p.y - SMOKE_P.y;
		if (hh > -0.1 && hh < 3.6) {
			vec3 axis = SMOKE_P + vec3(0.35 * hh + 0.08 * hh * hh, hh, -0.08 * hh);
			float r = 0.18 + 0.2 * hh;
			vec2 dxz = p.xz - axis.xz;
			float n = vnoise3(vec3(p.x * 1.6 - t_sec * 0.3, p.y * 1.3 - t_sec * 0.9, p.z * 1.6));
			float den = exp(-dot(dxz, dxz) / (r * r) * 1.4) * smoothstep(-0.1, 0.3, hh) * smoothstep(3.6, 1.2, hh);
			den *= (0.3 + 0.9 * smoothstep(0.3, 0.7, n)) * 1.4 / (1.0 + 0.8 * hh);
			if (den > 0.001) {
				vec3 li = vec3(0.3, 0.26, 0.36) + vec3(0.5, 0.25, 0.12) * 0.45;
				float a = 1.0 - exp(-den * dt * 2.0);
				acc += T * a * li;
				T *= 1.0 - a;
			}
		}
		t += dt;
	}
	return vec4(acc, T);
}

vec4 ground_fog(vec3 ro, vec3 rd, float tmax, float jit) {
	float tm = min(tmax, 70.0);
	float dt = tm / float(vol_steps);
	float T = 1.0;
	vec3 acc = vec3(0.0);
	float t = dt * jit;
	for (int i = 0; i < 32; i++) {
		if (i >= vol_steps) { break; }
		vec3 p = ro + rd * t;
		float hgt = p.y - WATER_Y;
		float den = 0.16 * exp(-max(hgt, 0.0) / 0.4);
		// Schwaden: Rauschen mit Schwelle, treibt langsam nach rechts
		float nz = vnoise3(vec3(p.x * 0.18 - t_sec * 0.22, p.y * 0.5, p.z * 0.26 - t_sec * 0.06));
		den *= smoothstep(0.3, 0.8, nz) * 1.6;
		if (den > 0.0005) {
			vec3 li = vec3(0.16, 0.15, 0.27);
			vec3 L = LANTERN_P - p;
			li += LANTERN_COL * 3.0 * lantern_k / (1.0 + dot(L, L) * 1.2);
			vec3 W = WINDOW_P - p;
			li += WINDOW_COL * 1.2 / (1.0 + dot(W, W) * 0.8);
			li += vec3(0.6, 0.28, 0.12) * 0.25;   // Abendlicht
			float a = 1.0 - exp(-den * dt);
			acc += T * a * li;
			T *= 1.0 - a;
		}
		t += dt;
	}
	return vec4(acc, T);
}

vec3 halos(vec3 ro, vec3 rd, float tmax) {
	vec3 col = vec3(0.0);
	// Laterne, Fenster, Leuchtfeuer: Abstand des Strahls zum Lichtpunkt (nur wenn nicht verdeckt)
	{
		vec3 L = LANTERN_P - ro;
		float tl = dot(L, rd);
		if (tl > 0.0 && tl < tmax + 0.3) {
			float d = length(L - rd * tl);
			float k = d / tl;
			col += LANTERN_COL * lantern_k * (0.7 * exp(-k * k * 6000.0) + 0.16 * exp(-k * k * 500.0));
		}
	}
	{
		vec3 L = LAMP_P - ro;
		float tl = dot(L, rd);
		if (tl > 0.0 && tl < tmax + 1.0) {
			float d = length(L - rd * tl);
			float k = d / tl;
			col += LAMP_COL * (1.0 + 4.0 * lamp_flash) * (0.6 * exp(-k * k * 9000.0) + 0.18 * exp(-k * k * 600.0));
		}
	}
	{
		vec3 L = WINDOW_P - ro;
		float tl = dot(L, rd);
		if (tl > 0.0 && tl < tmax + 0.5) {
			float d = length(L - rd * tl);
			float k = d / tl;
			col += WINDOW_COL * 0.25 * exp(-k * k * 900.0);
		}
	}
	return col;
}

// ---------------------------------------------------------------------------------------------
vec3 aces(vec3 x) {
	return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

vec3 render(vec3 ro, vec3 rd, vec2 fc, out float steps, out float bmask) {
	// Versatz der Volumen-Schritte: weißes Rauschen je Pixel und Bild (gleichmäßiges Korn statt Schraffur)
	float jit = hash12(fc * 1.37 + vec2(frame_no * 17.13, frame_no * 7.71));
	steps = 0.0;
	bmask = 0.0;
	// Wasser: Band zwischen Wellenober- und -unterkante
	float t_top = 1e9;
	float t_bot = 1e9;
	if (rd.y < 0.0) {
		t_top = (WATER_Y + WAVE_A - ro.y) / rd.y;
		t_bot = (WATER_Y - WAVE_A - ro.y) / rd.y;
	}
	float tmax = min(FAR, t_bot);
	vec3 h = march(ro, rd, tmax, max_steps);
	steps = h.z;
	float t = h.x;
	float m = h.y;
	bool water = false;
	float tw = -1.0;
	if (rd.y < 0.0 && (m < 0.0 || (ro + rd * t).y < WATER_Y + WAVE_A)) {
		float tend = (m < 0.0) ? t_bot : min(t, t_bot);
		if (t_top < tend) {
			tw = water_hit(ro, rd, t_top, tend);
			if (tw > 0.0) { water = true; }
		}
		if (!water && m < 0.0 && t_bot < 1e8) {
			tw = t_bot;
			water = true;
		}
	}
	vec3 col;
	float tscene;
	if (water) {
		tscene = tw;
		vec3 p = ro + rd * tw;
		vec3 n = water_normal(p.xz, tw);
		float fre = 0.02 + 0.98 * pow(1.0 - max(dot(n, -rd), 0.0), 5.0);
		vec3 rr = reflect(rd, n);
		rr.y = abs(rr.y);
		vec3 refl;
		vec3 hr = vec3(0.0, -1.0, 0.0);
		if (tw < 90.0) { hr = march(p + vec3(0.0, 0.02, 0.0), rr, 70.0, refl_steps); }
		if (hr.y > 0.0) {
			vec3 rp = p + rr * hr.x;
			vec3 rn = calc_normal(rp, hr.x);
			refl = shade(rp, rn, rr, hr.y, hr.x + tw, false);
			refl = mix(refl, sky_color(normalize(vec3(rr.x, 0.0, rr.z))) * 0.6, 1.0 - exp(-hr.x * 0.012));
		} else {
			refl = background(p, rr, jit, false);
		}
		refl += halos(p, rr, hr.y > 0.0 ? hr.x : 1e9) * 0.8;
		vec3 deep = vec3(0.004, 0.018, 0.03);
		// Schaum an Mauern, Booten und Felsen (Abstand im Distanzfeld)
		float dsc = map_d(p);
		float foam = smoothstep(0.16, 0.0, dsc) * (0.45 + 0.55 * vnoise2(p.xz * 6.0 + t_sec * 0.8));
		col = mix(deep, refl * vec3(0.55, 0.62, 0.8), fre);
		// Lichtglitzern der Laterne und des Fensters auf den Wellen
		col += point_light(p, n, rd, Mat(vec3(0.0), 1.0, 300.0, vec3(0.0), 0.0), LANTERN_P, LANTERN_COL, 3.0 * lantern_k, 2.5, false);
		col += point_light(p, n, rd, Mat(vec3(0.0), 1.0, 250.0, vec3(0.0), 0.0), WINDOW_P, WINDOW_COL, 1.5, 2.5, false);
		col += SUN_COL * 0.5 * pow(max(dot(reflect(rd, n), SUN), 0.0), 200.0);
		col = mix(col, vec3(0.5, 0.48, 0.55) * (SKY_AMB * 2.0 + 0.2), foam * 0.7);
		float fd = 1.0 - exp(-tw * 0.006);
		col = mix(col, sky_color(normalize(vec3(rd.x, 0.0, rd.z))) * 0.7, fd);
	} else if (m > 0.0) {
		tscene = t;
		vec3 p = ro + rd * t;
		vec3 n = calc_normal(p, t);
		col = shade(p, n, rd, m, t, true);
		float fd = 1.0 - exp(-max(t - 12.0, 0.0) * 0.006);
		vec3 hz = sky_color(normalize(vec3(rd.x, 0.03, rd.z)));
		col = mix(col, hz * 0.45, fd);
		if (m >= M_FUR) {
			// Messmaske: 1 = Körper, 2 = linker Fuß, 3 = rechter Fuß, 4 = Kopf
			vec3 q = to_badger(p);
			bmask = 1.0;
			float fl = sd_capsule(q, bj[5], bj[6], 0.075);
			float fr = sd_capsule(q, bj[9], bj[10], 0.075);
			if (fl < 0.0 && q.y < bj[5].y + 0.02) { bmask = 2.0; }
			if (fr < 0.0 && q.y < bj[9].y + 0.02) { bmask = 3.0; }
			if (m == M_HEAD || m == M_CAP || m == M_NOSE || m == M_EYE || m == M_BRASS && q.y > bj[2].y) { bmask = 4.0; }
		}
	} else {
		tscene = 1e9;
		col = background(ro, rd, jit, debug_mode != 2);
	}
	if (debug_mode != 2) {
		col += beam_volume(ro, rd, tscene, jit);
		vec4 sm = chimney_smoke(ro, rd, tscene, jit);
		col = col * sm.a + sm.rgb;
		vec4 fog = ground_fog(ro, rd, tscene, jit);
		col = col * fog.a + fog.rgb;
	}
	col += halos(ro, rd, tscene);
	return col;
}

void fragment() {
	vec2 uv = UV;
	vec2 fc = uv * res;
	float aspect = res.x / res.y;
	vec2 ndc = vec2((uv.x * 2.0 - 1.0) * aspect, 1.0 - uv.y * 2.0);
	vec3 f = normalize(cam_tgt - cam_pos);
	vec3 r = normalize(cross(f, vec3(0.0, 1.0, 0.0)));
	vec3 u = cross(r, f);
	float th = tan(radians(cam_fov) * 0.5);
	vec3 rd = normalize(f + ndc.x * th * r + ndc.y * th * u);
	float steps;
	float bmask;
	vec3 col = render(cam_pos, rd, fc, steps, bmask);
	if (debug_mode == 8) {
		// Fehlersuche: Was wirft den Schatten? Farbe nach Material des ersten Treffers Richtung Sonne
		vec3 h = march(cam_pos, rd, FAR, max_steps);
		vec3 c = vec3(0.0);
		if (h.y > 0.0) {
			vec3 p = cam_pos + rd * h.x;
			vec3 n = calc_normal(p, h.x);
			vec3 hs = march(p + n * 0.03, SUN, 30.0, 80);
			if (hs.y > 0.0) {
				c = vec3(fract(hs.y * 0.37), fract(hs.y * 0.61), fract(hs.y * 0.13));
				if (hs.x < 0.3) { c *= 0.5; }
			} else { c = vec3(1.0); }
		}
		COLOR = vec4(c, 1.0);
	} else if (debug_mode == 1) {
		float s = steps / float(max_steps);
		COLOR = vec4(s, s, s, 1.0);
	} else if (debug_mode == 4) {
		vec3 mc = vec3(0.0);
		if (bmask > 0.5) { mc = vec3(1.0); }
		if (bmask > 1.5) { mc = vec3(1.0, 0.0, 0.0); }
		if (bmask > 2.5) { mc = vec3(0.0, 1.0, 0.0); }
		if (bmask > 3.5) { mc = vec3(0.0, 0.0, 1.0); }
		COLOR = vec4(mc, 1.0);
	} else {
		col = aces(col * 0.8);
		col = pow(col, vec3(1.0 / 2.2));
		// Vignette und Dithering gegen Stufen im Himmel
		vec2 vq = uv - 0.5;
		col *= 1.0 - 0.28 * dot(vq, vq) * 1.6;
		col += (hash12(fc + frame_no * 13.0) - 0.5) / 255.0;
		COLOR = vec4(col, 1.0);
	}
}
