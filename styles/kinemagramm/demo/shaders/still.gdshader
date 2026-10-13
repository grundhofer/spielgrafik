shader_type canvas_item;
// Lebendes Standbild: ein einziges gemaltes Bild, belebt nur durch Masken und diesen Shader.
// Ebenen in einem Durchgang: Himmel pendelt langsam (reine Verschiebung), Wasser wellt sich (Rauschverzerrung,
// perspektivisch), Glitzern auf hellen Spiegelungen, Sterne funkeln, Boote schaukeln (Drehung um den
// Wasserpunkt über der sauberen Platte), Fenster/Laterne/Leuchtfeuer flackern (Maske x Faktor + Lichthof),
// Leuchtturmstrahl additiv (nur vor dem Himmel), Rauch aus dem Schornstein (Kette weicher Ballen), Möwen.
// Alle Zeitwerte kommen als Uniform aus main.gd (aufsummiertes delta, deterministisch).

uniform sampler2D plate : filter_linear, repeat_disable;
uniform sampler2D mask_a : filter_linear, repeat_disable;   // R Wasser, G Himmel, B Sterne
uniform sampler2D mask_b : filter_linear, repeat_disable;   // R Fenster, G Laterne, B Leuchtfeuer
uniform sampler2D mask_c : filter_linear, repeat_disable;   // R Boot 1, G Boot 2, B Strahl sichtbar
uniform sampler2D noise_tex : filter_linear, repeat_enable; // drei kachelbare Rauschkanäle

uniform float t = 0.0;
uniform vec2 size = vec2(1280.0, 720.0);
uniform float horizon_y = 260.0;
uniform float quay_y = 600.0;

// Wasser
uniform float water_amp = 3.2;        // px Auslenkung vorn
uniform float water_speed = 0.06;
uniform float sparkle_k = 0.55;
uniform float glint_h0 = 200.0;       // px: Tiefenmaßstab des Glitzerns (Verhältnis fern/vorn)
// Himmel: pendelt als reine Verschiebung (keine Überblendung, kein Wabern: Pinselstruktur bleibt erhalten)
uniform float sky_amp = 24.0;         // px Auslenkung nach jeder Seite
uniform float sky_period = 80.0;      // s je Hin und Her
uniform float sky_t0 = -3.0;          // Phase: Mitte der Aufnahme = größte Geschwindigkeit nach links
uniform float sky_shade = 0.10;
// Lichter
uniform vec3 flick = vec3(1.0);       // Fenster, Laterne, Leuchtfeuer
uniform vec2 glow_pos[4];
uniform vec4 glow_col[4];             // rgb, a = Stärke
uniform float glow_r[4];
// Strahl
uniform vec2 lamp_pos = vec2(800.0, 130.0);
uniform float beam_phi = 0.0;         // Drehwinkel des Leuchtfeuers (0 = nach rechts, PI/2 = zur Kamera)
uniform float beam_len = 620.0;
uniform float beam_k = 0.55;
uniform vec3 beam_col = vec3(1.0, 0.86, 0.62);
// Rauch
uniform vec2 chimney = vec2(130.0, 84.0);
uniform vec3 smoke_col = vec3(0.37, 0.37, 0.45);   // kühles Grau, dunkler als die hellen Himmelsstellen
uniform float smoke_k = 0.82;
uniform float smoke_h = 230.0;        // px, bis hier ausgeblendet
uniform float smoke_rise = 22.0;      // px/s
uniform vec2 smoke_bend = vec2(0.0035, 0.32);   // Windbiegung: a*h^2 + b*h
uniform float smoke_dt = 0.55;        // s zwischen zwei Ballen
uniform float smoke_r0 = 8.5;         // px Radius eines Ballens am Aufsatz
uniform float smoke_grow = 0.36;      // px Radius je px Höhe
uniform float smoke_w0 = 5.5;         // px Breite des Stiels (Gauß, 1/e)
const int SMOKE_N = 20;               // gleichzeitig lebende Ballen: smoke_h / smoke_rise / smoke_dt + 1
// Möwen: Lage aus main.gd (fliegen um und kommen in neuer Höhe wieder)
uniform vec2 gull_pos[2];
uniform float gull_size[2];
uniform vec3 gull_col = vec3(0.13, 0.13, 0.17);
// Boote
uniform vec2 boat_pivot[2];
uniform float boat_angle[2];
uniform float boat_bob[2];

float nz(vec2 p, int c) {
	vec4 n = texture(noise_tex, p);
	return c == 0 ? n.r : (c == 1 ? n.g : n.b);
}

// Hash ohne sin (nur Multiplikation und fract): liefert in allen Renderern dieselben Werte
// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash1(float x) {
	x = fract(x * 0.1031);
	x *= x + 33.33;
	x *= x + x;
	return fract(x);
}

vec2 rot(vec2 v, float a) {
	float s = sin(a), c = cos(a);
	return vec2(c * v.x - s * v.y, s * v.x + c * v.y);
}

vec3 plate_at(vec2 p) {
	return texture(plate, clamp(p, vec2(0.5), size - 0.5) / size).rgb;
}

// am Bildrand gespiegelt statt festgeklemmt: der verschobene Himmel zieht am Rand keine Streifen
vec3 plate_mirror(vec2 p) {
	vec2 q = abs(p);
	q = size - abs(size - q);
	return texture(plate, clamp(q, vec2(0.5), size - 0.5) / size).rgb;
}

void fragment() {
	vec2 p = UV * size;
	vec3 still = texture(TEXTURE, UV).rgb;
	vec4 ma = texture(mask_a, UV);
	vec4 mb = texture(mask_b, UV);
	vec4 mc = texture(mask_c, UV);
	float water = ma.r, sky = ma.g, stars = ma.b;

	// --- Himmel: langsames Hin- und Herziehen als reine Verschiebung (sin, größte Geschwindigkeit ~1,9 px/s).
	// Keine Überblendung zweier Lagen (die doppelte weiche Wolken zeigt) und kein Wabern (macht weich).
	float sky_off = sky_amp * sin(6.2831853 * (t + sky_t0) / sky_period);
	vec3 skyc = plate_mirror(p + vec2(sky_off, 0.0));
	// Wolkenschatten: sehr flache Helligkeitswelle, zieht mit dem Himmel und etwas schneller
	skyc *= 1.0 + (nz((p + vec2(sky_off * 1.3 + t * 0.4, 0.0)) / vec2(820.0, 520.0), 0) - 0.5) * sky_shade;
	// Sterne bleiben stehen und funkeln
	float tw = nz(p / 256.0 + vec2(t * 0.12, t * 0.07), 1);   // glatter Kanal, langsam: kein Flimmern von Bild zu Bild
	skyc = mix(skyc, still * (0.55 + 0.9 * smoothstep(0.35, 0.7, tw)), stars);

	// --- Wasser: Zeilenwellen, vorn stärker als am Horizont
	float depth = clamp((p.y - horizon_y) / max(quay_y - horizon_y, 1.0), 0.0, 1.0);
	float persp = mix(0.22, 1.0, depth);
	vec2 q = vec2(p.x / (600.0 * persp), p.y / (44.0 * persp));
	float n1 = nz(q + vec2(t * water_speed, -t * water_speed * 0.6), 0) - 0.5;
	float n2 = nz(q * 2.1 + vec2(-t * water_speed * 1.4, t * water_speed * 0.4), 1) - 0.5;
	vec2 wd = vec2(n1 * 2.0 + n2, (n2 - n1) * 0.35) * water_amp * persp * 1.6;
	vec3 wc = plate_at(p + wd);
	// Glitzern: kurze waagerechte Striche, nur auf hellen Spiegelungen. Rauschen in Koordinaten der Wasserfläche
	// (perspektivisch, logarithmisch in der Tiefe): am Horizont 3 x 1 px je Texel, vorn etwa 7 x 2,3 px; nie
	// feiner als 1 px je Texel, sonst pixelweises Salzrauschen.
	float lum = dot(wc, vec3(0.299, 0.587, 0.114));
	float hz = max(p.y - horizon_y, 0.0);
	float kf = glint_h0 / (hz + glint_h0);
	vec2 wpl = vec2((p.x - size.x * 0.5) * kf / 3.0, glint_h0 * log((hz + glint_h0) / glint_h0)) / 256.0;
	float g1 = nz(wpl + vec2(t * 0.012, t * 0.004), 2);
	float g2 = nz(wpl * vec2(0.83, 1.0) + vec2(0.43 - t * 0.010, 0.71 + t * 0.006), 0);
	float glint = smoothstep(0.36, 0.47, g1 * g2) * smoothstep(0.38, 0.60, lum);
	wc += glint * sparkle_k * vec3(1.0, 0.85, 0.62) * (0.4 + 0.6 * depth);

	// --- Grundbild zusammensetzen: Boote fallen aus dem Standbild heraus, dahinter liegt die Platte
	float hole = max(mc.r, mc.g);
	vec3 col = still;
	col = mix(col, skyc, sky);
	col = mix(col, wc, max(water, hole));

	// --- Boote: um den Drehpunkt auf der Wasserlinie schaukeln
	for (int i = 0; i < 2; i++) {
		vec2 piv = boat_pivot[i];
		vec2 sp2 = piv + rot(p - piv, -boat_angle[i]) - vec2(0.0, boat_bob[i]);
		vec4 bm = texture(mask_c, sp2 / size);
		float m = i == 0 ? bm.r : bm.g;
		vec3 bc = texture(TEXTURE, sp2 / size).rgb;
		col = mix(col, bc, m);
	}

	// --- Lichter flackern: Leuchtfläche und gemalter Lichtschein werden heller/dunkler
	col *= 1.0 + mb.r * (flick.x - 1.0) + mb.g * (flick.y - 1.0) + mb.b * (flick.z - 1.0);

	// --- Rauch: Kette weicher Ballen. Alle smoke_dt s verlässt ein Ballen den Aufsatz, steigt mit smoke_rise,
	// wird vom Wind nach rechts gebogen, wächst und verblasst; Größe, Dichte und Versatz je Ballen aus einem Hash
	// seiner Nummer (deterministisch). Jeder Ballen oben heller als unten (Volumen). Darunter ein kurzer Stiel.
	vec2 sv = p - chimney;
	float hgt = -sv.y;
	if (hgt > -2.0 && hgt < smoke_h && sv.x > -80.0 && sv.x < 420.0) {
		float hs = max(hgt, 0.0);
		float vis = smoothstep(-2.0, 1.0, hgt);
		float sdx = (sv.x - smoke_bend.x * hs * hs - smoke_bend.y * hs) / smoke_w0;
		float stem = exp(-sdx * sdx) * (1.0 - smoothstep(12.0, 45.0, hs));
		col = mix(col, smoke_col * 0.77, clamp(stem * vis * smoke_k, 0.0, 1.0));
		// Rand der Ballen: glattes Rauschen (Texel ≥ 1 px), steigt mit dem Rauch
		vec2 ep = p + vec2(0.0, t * smoke_rise);
		float en = (nz(ep / 300.0 + vec2(t * 0.01, 0.0), 1) - 0.5) * 0.7 + (nz(ep / 600.0 + vec2(0.3, 0.6), 0) - 0.5) * 0.6;
		float k0 = floor(t / smoke_dt);
		for (int k = SMOKE_N - 1; k >= 0; k--) {
			float kk = k0 - float(k);
			float age = t - kk * smoke_dt;
			float h = smoke_rise * age;
			if (h > smoke_h) {
				continue;
			}
			float r1 = hash1(kk), r2 = hash1(kk + 17.3), r3 = hash1(kk + 41.7);
			vec2 c = vec2(smoke_bend.x * h * h + smoke_bend.y * h + (r3 - 0.5) * h * 0.32 + sin(age * 1.1 + r1 * 6.28) * h * 0.06, -h * (0.96 + 0.08 * r2));
			float rad = smoke_r0 + h * smoke_grow * (0.5 + 1.0 * r1);
			float d = (length((sv - c) * vec2(1.0, 1.15)) + en * (2.0 + 0.15 * h)) / rad;
			float a = (1.0 - smoothstep(0.3, 1.0, d)) * smoothstep(0.0, 0.3, age) * (1.0 - smoothstep(smoke_h * 0.3, smoke_h, h)) * (0.6 + 0.4 * r2) * vis;
			float lit = clamp(0.5 - (sv.y - c.y) / rad * 0.5, 0.0, 1.0);
			vec3 sc = smoke_col * (0.62 + 0.44 * lit) * mix(0.85, 1.0, smoothstep(0.0, 60.0, h));
			col = mix(col, sc, clamp(a * smoke_k, 0.0, 1.0));
		}
	}

	// --- Leuchtturmstrahl (additiv, nur vor dem Himmel)
	float side = cos(beam_phi);
	float toward = sin(beam_phi);
	vec2 dv = p - lamp_pos;
	float dirx = side >= 0.0 ? 1.0 : -1.0;
	vec2 bdir = normalize(vec2(dirx, 0.035));
	float along = dot(dv, bdir);
	float across = abs(dv.x * bdir.y - dv.y * bdir.x);
	float L = beam_len * abs(side);
	float hw = 2.5 + max(along, 0.0) * (0.085 + 0.10 * max(toward, 0.0));
	float cone = smoothstep(hw, hw * 0.25, across) * smoothstep(0.0, 14.0, along) * (1.0 - smoothstep(L * 0.25, L, along));
	float haze = 0.7 + 0.6 * nz(p / 1100.0 + vec2(t * 0.01, 0.0), 0);
	// Streifen längs des Strahls (Dunst), wandern langsam
	float rel = (dv.x * bdir.y - dv.y * bdir.x) / max(hw, 1.0);
	haze *= 0.65 + 0.7 * nz(vec2(rel * 0.45 + 0.13, along / 1400.0 - t * 0.012), 2);
	float facing = mix(0.35, 1.0, clamp(toward * 0.5 + 0.5, 0.0, 1.0));
	col += beam_col * cone * haze * facing * beam_k * mc.b;

	// --- Möwen: zwei kleine Silhouetten aus Kurven, Flügelschlag und Gleiten aus der Zeit
	for (int i = 0; i < 2; i++) {
		vec2 c = gull_pos[i];
		vec2 g = (p - c) / gull_size[i];
		float ph = t * (i == 0 ? 7.5 : 6.3) + float(i);
		// Flügelschlag mit Gleitphasen
		float flap = mix(0.18, sin(ph) * 0.55, smoothstep(0.2, 0.6, sin(t * 0.7 + float(i) * 1.7) * 0.5 + 0.5));
		float ax = abs(g.x);
		float yc = -flap * ax + 0.35 * ax * ax - 0.10;
		float th = 0.16 * (1.0 - ax) + 0.05;
		float wing = (1.0 - smoothstep(th * 0.6, th, abs(g.y - yc))) * (1.0 - smoothstep(0.92, 1.0, ax));
		float body = 1.0 - smoothstep(0.10, 0.18, length(g * vec2(0.9, 1.6)));
		float ga = clamp(max(wing, body), 0.0, 1.0) * 0.9;
		col = mix(col, gull_col, ga);
	}

	// --- Lichthöfe (additiv, weich)
	for (int i = 0; i < 4; i++) {
		float d = length(p - glow_pos[i]) / max(glow_r[i], 1.0);
		col += glow_col[i].rgb * glow_col[i].a * exp(-d * d * 2.2);
	}

	COLOR = vec4(col, 1.0);
}
