shader_type canvas_item;
// Fotorealistisches Standbild: ein einziges KI-Foto, belebt nur durch Masken und diesen Shader.
// Ebenen in einem Durchgang: Wolken ziehen langsam (reine Verschiebung, oben schneller als am Horizont), Wasser
// bewegt sich (Rauschverzerrung, perspektivisch) und die Lichtsäulen darauf flimmern, Boote schaukeln (Drehung um
// den Wasserpunkt über der sauberen Platte), Fenster und Laterne flackern (Maske x Faktor), Leuchtfeuer dreht sich
// (Lampe blitzt, Strahl als schwacher Lichtkegel im Dunst, nur vor dem Himmel), dünner Rauch aus dem Schornstein.
// Alle Zeitwerte kommen als Uniform aus main.gd (aufsummiertes delta, deterministisch).

uniform sampler2D plate : filter_linear, repeat_disable;
uniform sampler2D mask_a : filter_linear, repeat_disable;   // R Wasser, G Himmel, B Sterne
uniform sampler2D mask_b : filter_linear, repeat_disable;   // R Fenster, G Laterne, B Leuchtfeuer
uniform sampler2D mask_c : filter_linear, repeat_disable;   // R Boot 1, G Boot 2, B Strahl sichtbar
uniform sampler2D noise_tex : filter_linear, repeat_enable; // drei kachelbare Rauschkanäle

uniform float t = 0.0;
uniform vec2 size = vec2(1280.0, 720.0);
uniform float horizon_y = 289.0;
uniform float quay_y = 580.0;
uniform bool frozen = false;

// Wolken: Pendeln ohne Überblendung (bleibt beliebig lange sauber); oben schneller (näher) als am Horizont
uniform float sky_amp = 26.0;
uniform float sky_period = 120.0;
uniform float sky_t0 = -3.0;
// Wasser
uniform float water_amp = 1.5;
uniform float water_speed = 0.035;
uniform float shimmer_k = 0.22;
// Lichter
uniform vec3 flick = vec3(1.0);       // Fenster, Laterne, Leuchtfeuer
uniform vec2 glow_pos[3];
uniform vec4 glow_col[3];             // rgb, a = Stärke
uniform float glow_r[3];
// Leuchtfeuer
uniform vec2 lamp_pos = vec2(1088.0, 158.0);
uniform float beam_phi = 0.0;         // Drehwinkel (0 = nach rechts, PI/2 = zur Kamera)
uniform float beam_len = 900.0;
uniform float beam_k = 0.42;
uniform vec3 beam_col = vec3(1.0, 0.84, 0.62);
// Rauch
uniform vec2 chimney = vec2(130.0, 76.0);
uniform vec3 smoke_col = vec3(0.40, 0.42, 0.47);
uniform float smoke_k = 0.62;
uniform float smoke_rise = 16.0;      // px/s
uniform vec2 smoke_bend = vec2(0.0022, 0.30);
// Boote
uniform vec2 boat_pivot[2];
uniform float boat_angle[2];
uniform float boat_bob[2];

float nz(vec2 p, int c) {
	vec4 n = texture(noise_tex, p);
	return c == 0 ? n.r : (c == 1 ? n.g : n.b);
}

vec2 rot(vec2 v, float a) {
	float s = sin(a), c = cos(a);
	return vec2(c * v.x - s * v.y, s * v.x + c * v.y);
}

vec3 plate_at(vec2 p) {
	return texture(plate, clamp(p, vec2(0.5), size - 0.5) / size).rgb;
}

// am Bildrand gespiegelt: der verschobene Himmel zieht am Rand keine Streifen
vec3 plate_mirror(vec2 p) {
	vec2 q = abs(p);
	q = size - abs(size - q);
	return texture(plate, clamp(q, vec2(0.5), size - 0.5) / size).rgb;
}

void fragment() {
	vec2 p = UV * size;
	vec3 photo = texture(TEXTURE, UV).rgb;
	if (frozen) {
		COLOR = vec4(photo, 1.0);
	} else {
	vec4 ma = texture(mask_a, UV);
	vec4 mb = texture(mask_b, UV);
	vec4 mc = texture(mask_c, UV);
	float water = ma.r, sky = ma.g, stars = ma.b;
	// alle Rauschwerte vor Verzweigungen holen
	float tw = nz(p / 256.0 + vec2(t * 0.11, t * 0.05), 1);

	// --- Himmel: Wolken ziehen als reine Verschiebung; Zeilen nahe dem Horizont langsamer (weiter weg)
	float par = mix(0.25, 1.0, smoothstep(horizon_y, 0.0, p.y));
	float sky_off = sky_amp * par * sin(6.2831853 * (t + sky_t0) / sky_period);
	vec3 skyc = plate_mirror(p + vec2(sky_off, 0.0));
	skyc = mix(skyc, photo * (0.75 + 0.5 * smoothstep(0.3, 0.7, tw)), stars);

	// --- Wasser: langsame Dünung, vorn stärker als am Horizont; Lichtsäulen zerfallen in waagerechte Bänder
	float depth = clamp((p.y - horizon_y) / max(quay_y - horizon_y, 1.0), 0.0, 1.0);
	float persp = mix(0.18, 1.0, depth);
	vec2 q = vec2(p.x / (520.0 * persp), p.y / (30.0 * persp));
	float n1 = nz(q + vec2(t * water_speed, -t * water_speed * 0.5), 0) - 0.5;
	float n2 = nz(q * 2.3 + vec2(-t * water_speed * 1.3, t * water_speed * 0.4), 1) - 0.5;
	vec2 wd = vec2((n1 * 2.0 + n2) * 1.6, (n2 - n1) * 0.5) * water_amp * persp;
	vec3 wc = plate_at(p + wd);
	// helle Stellen (Spiegelungen) flimmern leicht: Helligkeit wandert in breiten waagerechten Bändern
	float lum = dot(wc, vec3(0.299, 0.587, 0.114));
	float band = nz(vec2(p.x / (300.0 * persp), p.y / (9.0 * persp)) + vec2(t * 0.05, -t * 0.09), 2) - 0.5;
	wc *= 1.0 + band * shimmer_k * smoothstep(0.30, 0.65, lum);

	// --- Grundbild: Boote fallen aus dem Foto heraus, dahinter liegt die Platte
	float hole = max(mc.r, mc.g);
	vec3 col = photo;
	col = mix(col, skyc, sky);
	col = mix(col, wc, max(water, hole));

	// --- Boote schaukeln um den Drehpunkt auf der Wasserlinie
	for (int i = 0; i < 2; i++) {
		vec2 piv = boat_pivot[i];
		vec2 sp2 = piv + rot(p - piv, -boat_angle[i]) - vec2(0.0, boat_bob[i]);
		vec4 bm = texture(mask_c, sp2 / size);
		vec3 bc = texture(TEXTURE, sp2 / size).rgb;
		float m = i == 0 ? bm.r : bm.g;
		col = mix(col, bc, m);
	}

	// --- Lichter: Leuchtfläche und Lichtschein (Pfosten, Wand, Kai) werden heller/dunkler
	col *= 1.0 + mb.r * (flick.x - 1.0) + mb.g * (flick.y - 1.0) + mb.b * (flick.z - 1.0);

	// --- Rauch: dünner Schleier aus dem Schornstein, steigt, wird vom Wind nach rechts gebogen und zerfasert
	vec2 sv = p - chimney;
	float h = -sv.y;
	float hs = max(h, 0.0);
	float xc = smoke_bend.x * hs * hs + smoke_bend.y * hs;
	float wdt = 4.0 + hs * 0.30;
	// Rauschen in mitbewegten Koordinaten (steigt mit dem Rauch), zwei Oktaven, nie feiner als 1 px je Texel
	vec2 sp = vec2((sv.x - xc) / 70.0, (h - t * smoke_rise) / 90.0);
	float f1 = nz(sp + vec2(0.13, 0.41), 0);
	float f2 = nz(sp * 2.2 + vec2(0.57 + t * 0.004, 0.21), 1);
	float wob = (nz(vec2(h / 160.0 - t * smoke_rise / 160.0, 0.37), 2) - 0.5) * 18.0 * smoothstep(0.0, 60.0, hs);
	float dx = (sv.x - xc - wob) / wdt;
	float body = exp(-dx * dx);
	float puff = smoothstep(0.35, 0.75, f1 * 0.65 + f2 * 0.55);
	float dens = body * mix(0.35, 1.0, puff) * smoothstep(-1.0, 3.0, h) * (1.0 - smoothstep(60.0, 230.0, hs));
	dens *= smoothstep(-40.0, -10.0, -abs(sv.x - xc) + 60.0 + hs);
	vec3 scol = smoke_col * mix(0.92, 1.12, smoothstep(0.0, 120.0, hs));
	col = mix(col, scol, clamp(dens * smoke_k, 0.0, 1.0) * sky);

	// --- Leuchtturmstrahl: schwacher Lichtkegel im Dunst, additiv, nur vor dem Himmel
	float side = cos(beam_phi);
	float toward = sin(beam_phi);
	vec2 dv = p - lamp_pos;
	float dirx = side >= 0.0 ? 1.0 : -1.0;
	vec2 bdir = normalize(vec2(dirx, 0.02));
	float along = dot(dv, bdir);
	float across = abs(dv.x * bdir.y - dv.y * bdir.x);
	float L = beam_len * abs(side);
	float hw = 1.5 + max(along, 0.0) * (0.035 + 0.07 * max(toward, 0.0));
	float xr = across / max(hw, 1.0);
	// heller Kern mit weichem Dunstsaum, endet weich
	float cone = (exp(-xr * xr * 2.5) * 0.75 + exp(-xr * xr * 0.45) * 0.25) * smoothstep(0.0, 8.0, along)
		* (1.0 - smoothstep(L * 0.15, L, along));
	float haze = 0.6 + 0.8 * nz(vec2(xr * 0.12 + 0.2, along / 900.0 - t * 0.012), 2);
	float facing = mix(0.45, 1.0, clamp(toward * 0.5 + 0.5, 0.0, 1.0));
	col += beam_col * cone * haze * facing * beam_k * mc.b;

	// --- Lichthöfe (additiv, weich): Fenster, Laterne, Leuchtfeuer
	for (int i = 0; i < 3; i++) {
		float d = length(p - glow_pos[i]) / max(glow_r[i], 1.0);
		col += glow_col[i].rgb * glow_col[i].a * exp(-d * d * 2.0);
	}
	COLOR = vec4(col, 1.0);
	}
}
