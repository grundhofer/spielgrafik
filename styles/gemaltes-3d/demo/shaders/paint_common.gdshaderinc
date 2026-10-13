// Gemeinsame Bausteine der 3D-Shader: Rauschen und die Steuerkarte.
//
// Jede Fläche wird zweimal gerendert: von der Bildkamera (Farbe) und von der Steuerkamera, die
// zusätzlich Ebene 20 sieht. Erkennt der Shader Ebene 20 in CAMERA_VISIBLE_LAYERS, gibt er statt
// Farbe drei Steuerwerte als EMISSION aus (ALBEDO 0, kein Licht, Umgebung der Steuerkamera schwarz):
//   R = Pinselgröße (0 fein … 1 grob), G = Strichrauschen, an der Oberfläche festgemacht,
//   B = Kantenstärke (wie kräftig der Rand der Farbfläche dunkelt).
// Die Nachbearbeitung (post_*.gdshader) liest diese Karte. Vorbild: Steuerkarten in MNPR
// (Montesdeoca u. a. 2018), dort je Objekt bemalt, hier je Material gesetzt.

const uint CTRL_LAYER_BIT = 1u << 19u;   // Ebene 20

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float hash13(vec3 p3) {
	p3 = fract(p3 * 0.1031);
	p3 += dot(p3, p3.zyx + 31.32);
	return fract((p3.x + p3.y) * p3.z);
}

float vnoise2(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	float a = hash12(i);
	float b = hash12(i + vec2(1.0, 0.0));
	float c = hash12(i + vec2(0.0, 1.0));
	float d = hash12(i + vec2(1.0, 1.0));
	return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float vnoise3(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
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
		p = mat2(vec2(1.6, 1.2), vec2(-1.2, 1.6)) * p + vec2(3.1, 1.7);
		a *= 0.5;
	}
	return s / 0.9375;
}

float fbm3(vec3 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		s += a * vnoise3(p);
		p = p * 2.03 + vec3(1.7, 9.2, 3.1);
		a *= 0.5;
	}
	return s / 0.9375;
}

// Strichrauschen mit etwa gleicher Zellgröße auf dem Bildschirm, aber an der Oberfläche
// festgemacht (Koordinate p in Metern, z. B. UV). Zwei Oktaven je nach Pixelgröße überblendet,
// Kontrast nach dem Mischen wiederhergestellt ("Dynamic Solid Textures", Bénard, Bousseau und Thollot 2009).
// Interpoliertes Wertrauschen statt hartem Zufall je Zelle: Bei Bewegung um Bruchteile eines Pixels
// ändern sich die Werte stetig; harte Zellen ließen die Striche nach dem LIC-Filter brodeln.
float stroke_noise(vec2 p, float cell_px) {
	vec2 dx = dFdx(p);
	vec2 dy = dFdy(p);
	float mpp = max(max(length(dx), length(dy)), 1e-6);   // Meter je Pixel
	float lv = log2(mpp * cell_px);
	float l0 = floor(lv);
	float fr = lv - l0;
	float s0 = exp2(l0);
	float n0 = vnoise2(p / s0 + vec2(l0 * 17.0, l0 * 31.0));
	float n1 = vnoise2(p / (2.0 * s0) + vec2(l0 * 17.0 + 17.0, l0 * 31.0 + 31.0));
	float n = mix(n0, n1, fr) - 0.5;
	n /= sqrt(fr * fr + (1.0 - fr) * (1.0 - fr));
	return clamp(0.5 + n * 1.6, 0.0, 1.0);   // Wertrauschen streut weniger als Zufall je Zelle
}

// Strichrauschen aus zwei Zellgrößen: grobe Zellen (ein Pinseltupfer breit) für einzelne Striche mit
// eigener Helligkeit, feine Zellen für die Borstenrillen darin.
float stroke_noise2(vec2 p, float fine_px, float coarse_px, float coarse_weight) {
	return mix(stroke_noise(p, fine_px), stroke_noise(p + vec2(37.1, 11.7), coarse_px), coarse_weight);
}
