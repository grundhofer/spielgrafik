// Vierfarbdruck wie im Comic: Die Seite (page_tex) enthält nur die Farbflächen (Kolorierung), der Tusche-Viewport
// (ink_tex) die Zeichnung. Farbflächen werden gerastert: je Druckfarbe ein gedrehtes Punktraster (C 15°, M 75°,
// Y 0°, K 45°, Rasterweite pitch); jede Rasterzelle tastet die Seite in ihrer Mitte ab und setzt einen runden Punkt
// mit flächenrichtigem Radius (bis 78,5 % Deckung berühren sich die Punkte, darüber wachsen sie zusammen).
// Farbe -> Druckfarben wie bei einer Comic-Kolorierung: Der Grauanteil (min von C, M, Y) wird zu ucr aus den Bunt-
// farben genommen (Farben werden klarer und heller), nur dunkle Töne (k_lo..k_hi) bekommen Schwarz als Raster.
// Alle Raster unter 45° (angles): Punkte verschiedener Farben liegen ineinander statt Rosetten zu bilden (ruhiger,
// näher am Ben-Day-Bild als am Offset-Vierfarbdruck). Tusche liegt in voller Auflösung darüber (Schwarzplatte = Zeichnung): ink_tex Alpha minus
// Helligkeit = Schwarz, weiß gezeichnete Stellen (Deckweiß: Glitzern, Ziffern, Aufdecken der Panels) = Papier.
// Druckfarben werden auf Papier multipliziert; C, M und Y leicht versetzt (Passer).
shader_type canvas_item;

uniform sampler2D page_tex : filter_nearest;
uniform sampler2D ink_tex : filter_nearest;
uniform vec2 size = vec2(1280.0, 720.0);
uniform float pitch = 6.5;
uniform float min_tone = 0.05;         // hellere Töne drucken nicht (kein Punkt-Staub)
uniform float levels = 0.0;            // > 0: Tonwerte je Farbe auf Stufen runden (Farbtafel)
uniform vec3 paper : source_color = vec3(0.965, 0.937, 0.862);
uniform vec3 ink_c : source_color = vec3(0.0, 0.63, 0.89);
uniform vec3 ink_m : source_color = vec3(0.90, 0.14, 0.52);
uniform vec3 ink_y : source_color = vec3(1.0, 0.89, 0.06);
uniform vec3 ink_k : source_color = vec3(0.11, 0.10, 0.12);
uniform float ucr = 0.6;
uniform float k_lo = 0.45;
uniform float k_hi = 0.9;
uniform vec4 angles = vec4(45.0, 45.0, 45.0, 45.0);
uniform vec2 reg_c = vec2(1.0, 0.0);
uniform vec2 reg_m = vec2(0.0, 1.0);
uniform vec2 reg_y = vec2(-1.0, 0.0);
uniform float paper_noise = 0.02;
uniform int probe = 0;                 // 1: Seite ungerastert ausgeben (Prüfbilder)

vec4 cmyk(vec3 c) {
	vec3 cmy = 1.0 - c;
	float g = min(min(cmy.r, cmy.g), cmy.b);
	float kk = g * smoothstep(k_lo, k_hi, g);
	cmy = clamp(cmy - max(g * ucr, kk), 0.0, 1.0);
	return vec4(cmy, kk);
}

float dot_radius(float t) {
	// Radius in Rasterzellen; Fläche pi r^2 = t bis zum Berühren (t = pi/4), danach bis 0,78 (deckt die Zelle).
	if (t < min_tone) {
		return -1.0;
	}
	if (levels > 0.5) {
		t = floor(t * levels + 0.5) / levels;
	}
	float r = sqrt(t / 3.14159265);
	return t <= 0.785 ? r : mix(0.5, 0.78, (t - 0.785) / 0.215);
}

float screen(vec2 px, float ang, vec2 off, int ch) {
	float ca = cos(ang);
	float sa = sin(ang);
	vec2 p = px - off;
	vec2 q = vec2(ca * p.x + sa * p.y, -sa * p.x + ca * p.y) / pitch;
	vec2 base = floor(q - 0.5) + 0.5;
	float aa = 0.6 / pitch;
	float cov = 0.0;
	for (int i = 0; i < 4; i++) {
		vec2 cc = base + vec2(float(i & 1), float(i >> 1));
		vec2 w = cc * pitch;
		vec2 sp = vec2(ca * w.x - sa * w.y, sa * w.x + ca * w.y) + off;
		vec2 uv = clamp(sp, vec2(0.5), size - 0.5) / size;
		vec4 v = cmyk(textureLod(page_tex, uv, 0.0).rgb);
		float r = dot_radius(v[ch]);
		float d = length(q - cc);
		cov = max(cov, 1.0 - smoothstep(r - aa, r + aa, d));
	}
	return cov;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec3 page = textureLod(page_tex, UV, 0.0).rgb;
	vec4 inkpx = textureLod(ink_tex, UV, 0.0);
	float line = clamp(inkpx.a - max(max(inkpx.r, inkpx.g), inkpx.b), 0.0, 1.0);
	float white = clamp(min(min(inkpx.r, inkpx.g), inkpx.b), 0.0, 1.0);
	vec2 px = UV * size;
	float dc = screen(px, radians(angles.x), reg_c, 0);
	float dm = screen(px, radians(angles.y), reg_m, 1);
	float dy = screen(px, radians(angles.z), reg_y, 2);
	float dk = screen(px, radians(angles.w), vec2(0.0), 3);
	vec3 pap = paper * (1.0 - paper_noise * hash(floor(px * 0.5)));
	// Weiße Flächen der Seite (Stege, Sprechblase) bleiben punktfrei: Punkte aus Nachbarzellen enden dort.
	float blank = step(0.985, min(min(page.r, page.g), page.b));
	dc *= 1.0 - blank;
	dm *= 1.0 - blank;
	dy *= 1.0 - blank;
	dk *= 1.0 - blank;
	vec3 col = pap * mix(vec3(1.0), ink_c, dc) * mix(vec3(1.0), ink_m, dm) * mix(vec3(1.0), ink_y, dy)
		* mix(vec3(1.0), ink_k, dk);
	if (probe == 1) {
		col = page;
	}
	col = mix(col, ink_k, line);
	col = mix(col, pap, white);
	COLOR = vec4(col, 1.0);
}
