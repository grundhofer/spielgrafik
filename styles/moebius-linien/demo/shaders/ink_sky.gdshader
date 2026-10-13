// Großer, heller Pastellhimmel in der Abenddämmerung, gezeichnet statt gemalt:
// weicher Verlauf (Aprikose am Horizont, Creme, Rosé, Flieder oben), darin
//  - Haufenwolken mit Tuscheumriss: Vereinigung von Kreisen mit flacher Unterkante, die oberen Bögen
//    der vorderen Bällchen als Innenlinien, unten ein Band in der Schattenfarbe mit leichter Schraffur,
//  - ein großer Mond mit Schattensichel, Schraffur und Kratern,
//  - Möwen als Tuschestriche, die mit den Flügeln schlagen und langsam gleiten.
// Alles in Winkelkoordinaten (Grad): x = Azimut (0 = Blick nach -Z, rechts positiv) mal cos(Höhe),
// y = Höhe über dem Horizont. Linienbreiten in Pixeln über px_deg (Grad je Bildpunkt; setzt main.gd
// je Kamera). Lage der Formen aus scripts/frame_shot.py (sichtbar in Totale und Nahaufnahme).
shader_type sky;

global uniform float ink_time;
global uniform vec4 ink_color;   // linear (globale Farben werden nicht aus sRGB umgerechnet)
global uniform float ink_hatch;

uniform vec4 col_horizon : source_color = vec4(0.97, 0.79, 0.6, 1.0);
uniform vec4 col_low : source_color = vec4(0.98, 0.88, 0.72, 1.0);
uniform vec4 col_mid : source_color = vec4(0.95, 0.84, 0.82, 1.0);
uniform vec4 col_high : source_color = vec4(0.78, 0.8, 0.91, 1.0);
uniform vec4 cloud_lit : source_color = vec4(1.0, 0.97, 0.91, 1.0);
uniform vec4 cloud_shade : source_color = vec4(0.9, 0.81, 0.85, 1.0);
uniform vec4 moon_col : source_color = vec4(1.0, 0.97, 0.86, 1.0);
uniform vec4 moon_shade : source_color = vec4(0.92, 0.85, 0.8, 1.0);
uniform float px_deg = 0.0583;          // Grad je Pixel (fov 42° / 720 px)
uniform float line_px = 1.7;            // Umrissbreite in Pixeln
uniform float cloud_drift = 1.2;        // Grad: Wolken pendeln langsam (Periode 240 s) um ihre Lage
uniform vec3 moon = vec3(5.0, 13.0, 3.6);   // x, Höhe, Radius in Grad
uniform float lines_on = 1.0;

// Haufenwolken: Mitte (x, y), Unterkante relativ zur Mitte, Höhe des Schattenbands
const int CLOUDS = 3;
const vec4 CLOUD[3] = {vec4(-30.0, 12.0, -2.2, 1.3), vec4(31.0, 14.5, -1.6, 1.0), vec4(-15.0, 19.5, -1.2, 0.8)};
const int CLOUD_START[4] = {0, 7, 12, 16};
// Bällchen (dx, dy, Radius) in Grad; von hinten nach vorn
const vec3 PUFFS[16] = {
	vec3(-6.5, -0.9, 1.7), vec3(6.4, -0.8, 1.9), vec3(-3.4, 0.6, 2.6), vec3(3.6, 0.9, 2.5),
	vec3(-0.2, 2.2, 3.2), vec3(-5.0, -0.9, 2.0), vec3(1.2, -0.6, 2.6),
	vec3(-3.8, -0.4, 1.6), vec3(3.9, -0.3, 1.7), vec3(-1.5, 1.0, 2.4), vec3(1.7, 1.5, 2.2), vec3(0.3, -0.4, 2.0),
	vec3(-2.6, -0.1, 1.3), vec3(2.5, -0.2, 1.3), vec3(-0.7, 0.8, 1.8), vec3(1.0, 0.2, 1.5)
};
// Möwen: Mitte (x, y), Spannweite in Grad, Phase
const int GULLS = 3;
const vec4 GULL[3] = {vec4(-3.0, 19.0, 1.5, 0.0), vec4(1.5, 20.8, 1.15, 0.37), vec4(-9.0, 12.0, 1.3, 0.71)};

float ink_cov(float d, float width_deg, float aa) {
	return 1.0 - smoothstep(width_deg * 0.5 - aa, width_deg * 0.5 + aa, abs(d));
}

// Distanzfunktion Strecke nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
float seg_dist(vec2 p, vec2 a, vec2 b) {
	vec2 pa = p - a;
	vec2 ba = b - a;
	float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
	return length(pa - ba * h);
}

float hatch(vec2 frag, float spacing) {
	float u = dot(frag, vec2(sin(0.96), cos(0.96)));
	float d = abs(fract(u / spacing) - 0.5) * spacing;
	return 1.0 - smoothstep(0.08, 1.08, d);
}

void sky() {
	vec3 dir = normalize(EYEDIR);
	float el = degrees(asin(clamp(dir.y, -1.0, 1.0)));
	float az = degrees(atan(dir.x, -dir.z));
	vec2 sp = vec2(az * cos(radians(el)), el);
	vec2 frag = SCREEN_UV * vec2(1280.0, 720.0);
	float aa = px_deg * 0.6;
	float lw = px_deg * line_px;

	// Verlauf
	vec3 c = col_horizon.rgb;
	c = mix(c, col_low.rgb, smoothstep(0.0, 4.0, el));
	c = mix(c, col_mid.rgb, smoothstep(6.0, 15.0, el));
	c = mix(c, col_high.rgb, smoothstep(15.0, 30.0, el));
	float ink = 0.0;

	// Mond: Scheibe, Schattensichel mit Schraffur, drei Krater
	vec2 mp = sp - moon.xy;
	float md = length(mp) - moon.z;
	if (md < lw * 2.0) {
		float inside = 1.0 - smoothstep(-aa, aa, md);
		float sickle = smoothstep(-aa, aa, length(mp - vec2(-moon.z * 0.34, 0.25)) - moon.z * 0.9);
		c = mix(c, mix(moon_col.rgb, moon_shade.rgb, sickle), inside);
		ink = max(ink, inside * sickle * hatch(frag, 4.0) * 0.6 * ink_hatch);
		vec3 crater[3] = {vec3(-1.5, 1.3, 0.8), vec3(1.2, -1.5, 0.6), vec3(-0.4, -0.9, 0.4)};
		for (int i = 0; i < 3; i++) {
			float cd = length(mp - crater[i].xy) - crater[i].z;
			c = mix(c, moon_shade.rgb, inside * (1.0 - smoothstep(-aa, aa, cd)));
			ink = max(ink, inside * ink_cov(cd, lw * 0.7, aa));
		}
		ink = max(ink, ink_cov(md, lw * 1.1, aa));
	}

	// Haufenwolken
	for (int k = 0; k < CLOUDS; k++) {
		vec4 cl = CLOUD[k];
		vec2 p = sp - vec2(cl.x + cloud_drift * sin(ink_time * 6.2832 / 240.0 + float(k)), cl.y);
		if (abs(p.x) > 14.0 || abs(p.y) > 9.0) {
			continue;
		}
		float du = 1e5;
		float lobe = 0.0;
		for (int i = CLOUD_START[k]; i < CLOUD_START[k + 1]; i++) {
			vec3 b = PUFFS[i];
			float di = length(p - b.xy) - b.z;
			du = min(du, di);
			// vordere Bällchen verdecken die Bögen der hinteren; nur der obere Teil wird gezeichnet
			lobe *= smoothstep(-aa, aa, di);
			float arc = ink_cov(di, lw * 0.8, aa) * smoothstep(b.y - 0.25 * b.z, b.y + 0.15 * b.z, p.y);
			lobe = max(lobe, arc);
		}
		float d = max(du, cl.z - p.y);
		float inside = 1.0 - smoothstep(-aa, aa, d);
		float band = 1.0 - smoothstep(-aa, aa, p.y - (cl.z + cl.w + 0.25 * sin(p.x * 1.3)));
		c = mix(c, mix(cloud_lit.rgb, cloud_shade.rgb, band), inside);
		float h = band * hatch(frag, 5.0) * 0.4 * ink_hatch;
		float inner = lobe * (1.0 - smoothstep(-lw * 1.2, -lw * 0.6, d));
		ink = max(ink * (1.0 - inside), max(ink_cov(d, lw, aa), inside * max(h, inner)));
	}

	// Möwen: zwei Flügel aus je zwei Strichen, Flügelschlag mit 1,6 Hz, langsames Gleiten
	for (int i = 0; i < GULLS; i++) {
		vec4 g = GULL[i];
		// gleiten langsam hin und her (periodisch, damit sie auch nach Minuten im Bild bleiben)
		vec2 gp = g.xy + vec2(2.2 * sin(ink_time * 0.16 + g.w * 6.0), 0.25 * sin(ink_time * 0.7 + g.w * 6.0));
		vec2 p = sp - gp;
		if (abs(p.x) > 2.5 || abs(p.y) > 2.0) {
			continue;
		}
		float s = g.z;
		float flap = sin((ink_time * 1.6 + g.w) * 6.2832);
		vec2 elbow = vec2(0.45 * s, 0.16 * s + 0.12 * s * flap);
		vec2 tip = vec2(0.95 * s, -0.08 * s + 0.4 * s * flap);
		vec2 q = vec2(abs(p.x), p.y);
		float d = min(seg_dist(q, vec2(0.0), elbow), seg_dist(q, elbow, tip));
		ink = max(ink, ink_cov(d, lw * 1.05, aa));
	}

	COLOR = mix(c, ink_color.rgb, clamp(ink * lines_on, 0.0, 1.0));
}
