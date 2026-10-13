// Welt-Nachbearbeitung: liegt auf dem TextureRect, das das 3D-Bild (WorldVP) zeigt, und wirkt nur auf die
// Spielwelt, nicht auf die Oberfläche (die wird danach gezeichnet).
// Looks (look): 0 ohne (auch Bloom: der kommt aus dem Environment-Glow im HDR-Puffer), 2 Filmkorn & Vignette,
// 3 Farb-LUT, 4 Halbton (CMYK-Raster), 5 Paletten-Reduktion (16 Farben, Bayer-Dithering, 3-px-Raster).
// Alle Abtastungen mit textureLod(…, 0.0): das Viewport-Bild hat keine Mipmaps, und in Schleifen und
// Verzweigungen fehlen sonst die Ableitungen.
shader_type canvas_item;
render_mode unshaded;

// Quellbild (Viewport-Textur, setzt main.gd): TEXTURE ist in eigenen Funktionen nicht verfügbar.
uniform sampler2D src_tex : filter_linear, repeat_disable;

uniform int look = 0;
uniform int frame = 0;                    // Bildnummer der Aufnahme (Korn, Staub, Flackern)

// Filmkorn & Vignette
uniform float grain_amount = 0.075;
uniform float grain_size = 1.6;           // px je Kornzelle
uniform float vignette_amount = 0.7;
uniform float halation = 1.6;

// Farb-LUT: 32³ als Streifen 1024×32 (Kachel = Blau, x = Rot, y = Grün), sRGB
uniform sampler2D lut_tex : filter_linear, repeat_disable;

// Halbton
uniform float ht_cell = 8.0;              // Rasterweite in px
uniform float ht_ink_gamma = 1.6;         // Punktfarbe = Quellfarbe dunkler und satter
uniform float ht_lift = 1.3;              // Quelle vor dem Rastern aufhellen (die Abendszene ist dunkel)
uniform vec3 paper : source_color = vec3(0.97, 0.94, 0.86);

// Paletten-Reduktion
uniform float pal_pixel = 4.0;            // Blockgröße in px (320×180 Rasterpunkte)
uniform float pal_spread = 0.14;          // Stärke des geordneten Ditherings
uniform vec3 pal_rgb[16];
uniform vec3 pal_lab[16];
uniform int pal_count = 16;

vec3 src(vec2 uv) {
	return textureLod(src_tex, uv, 0.0).rgb;
}

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	// ohne sin(): rechnet in allen Renderern gleich
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float luma(vec3 c) {
	return dot(c, vec3(0.299, 0.587, 0.114));
}

// ---------------------------------------------------------------- Filmkorn & Vignette
float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash12(i);
	float b = hash12(i + vec2(1.0, 0.0));
	float c = hash12(i + vec2(0.0, 1.0));
	float d = hash12(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec3 film_look(vec2 uv, vec2 px, vec2 ps) {
	vec3 c = src(uv);
	// Halation: helle Stellen strahlen rötlich in die Umgebung (Licht streut in der Filmschicht zurück)
	vec3 hal = vec3(0.0);
	for (int i = 0; i < 12; i++) {
		float a = float(i) * 0.5235988 + 0.26;
		vec2 dir = vec2(cos(a), sin(a));
		hal += max(src(uv + dir * 5.0 * ps) - 0.66, vec3(0.0));
		hal += 0.6 * max(src(uv + dir * 13.0 * ps) - 0.66, vec3(0.0));
	}
	c += halation * (hal / 12.0) * vec3(1.0, 0.42, 0.22);
	// Filmkurve: Schwarz angehoben, Lichter weich, leicht warm und etwas entsättigt
	float l = luma(c);
	c = mix(vec3(l), c, 0.82);
	c = c * vec3(1.04, 0.99, 0.90);
	c = 0.045 + 0.94 * c / (1.0 + 0.12 * c);
	c = mix(c, c * c * (3.0 - 2.0 * c), 0.35);
	// Belichtung schwankt von Bild zu Bild ein wenig
	c *= 1.0 + 0.035 * (hash12(vec2(float(frame), 7.0)) - 0.5);
	// Korn: zwei Lagen Wertrauschen je Bild neu, am stärksten in Schatten und Mitten
	vec2 o = vec2(hash12(vec2(float(frame), 1.0)), hash12(vec2(float(frame), 2.0))) * 512.0;
	float g = value_noise(px / grain_size + o) + value_noise(px / (grain_size * 0.55) + o.yx) - 1.0;
	l = luma(c);
	c += g * grain_amount * (1.15 - 0.7 * l);
	// Staub: wenige dunkle Punkte und Fasern je Bild
	for (int i = 0; i < 4; i++) {
		vec2 seed = vec2(float(frame) * 3.17 + float(i) * 11.0, float(i) * 5.0);
		if (hash12(seed + 0.5) < 0.45) {
			vec2 pos = vec2(hash12(seed), hash12(seed + 9.1)) * vec2(1280.0, 720.0);
			float r = 1.0 + 2.2 * hash12(seed + 3.3);
			float d = length((px - pos) * vec2(1.0, 0.35 + 0.65 * hash12(seed + 4.4)));
			c *= 1.0 - 0.55 * (1.0 - smoothstep(r - 0.7, r + 0.7, d));
		}
	}
	// Vignette: ovale Abschattung zu den Ecken
	vec2 q = (uv - 0.5) * vec2(1.0, 0.72);
	float v = 1.0 - vignette_amount * smoothstep(0.18, 0.62, length(q));
	return c * v;
}

// ---------------------------------------------------------------- Farb-LUT
vec3 lut(vec3 c) {
	float n = 32.0;
	c = clamp(c, 0.0, 1.0);
	float b = c.b * (n - 1.0);
	float b0 = floor(b);
	float b1 = min(b0 + 1.0, n - 1.0);
	vec2 rg = (c.rg * (n - 1.0) + 0.5) / vec2(n * n, n);
	vec3 s0 = textureLod(lut_tex, vec2(rg.x + b0 / n, rg.y), 0.0).rgb;
	vec3 s1 = textureLod(lut_tex, vec2(rg.x + b1 / n, rg.y), 0.0).rgb;
	return mix(s0, s1, b - b0);
}

// ---------------------------------------------------------------- Halbton (Comic-Punktraster)
// Ein Raster unter 45°: je Zelle ein Punkt in der abgedunkelten, gesättigten Farbe der Zellmitte auf Papier.
// Punktfläche so gewählt, dass Papier und Punkt im Mittel die Helligkeit der Quelle ergeben
// (Mischung paper -> ink mit Deckung a). Ein Raster statt vier CMYK-Auszügen: ruhiger, klarer Comic-Look.
vec4 ht_ink(vec3 c) {
	c = clamp(c, 0.0, 1.0);
	float l = luma(c);
	vec3 ink = pow(c, vec3(ht_ink_gamma)) * 0.92;
	// gesättigter: Abstand zur Graustufe vergrößern
	float li = luma(ink);
	ink = clamp(vec3(li) + (ink - vec3(li)) * 1.6, 0.0, 1.0);
	li = luma(ink);
	float lp = luma(paper);
	float a = clamp((lp - l * ht_lift) / max(lp - li, 0.05), 0.0, 1.0);
	return vec4(ink, a);
}

vec3 halftone_look(vec2 px, vec2 ps) {
	float ang = radians(45.0);
	float ca = cos(ang);
	float sa = sin(ang);
	mat2 rot = mat2(vec2(ca, sa), vec2(-sa, ca));
	mat2 inv = mat2(vec2(ca, -sa), vec2(sa, ca));
	vec2 q = rot * px / ht_cell;
	vec2 base = floor(q - 0.5) + 0.5;
	vec3 col = paper * (0.97 + 0.03 * value_noise(px * 0.5));    // Papierstruktur
	// vier nächste Punkte; große Punkte überlappen in die Nachbarzellen
	float best = 0.0;
	vec3 best_ink = vec3(1.0);
	for (int i = 0; i < 4; i++) {
		vec2 cc = base + vec2(float(i & 1), float(i >> 1));
		vec2 cpx = inv * cc * ht_cell;
		vec2 o = vec2(0.25 * ht_cell, 0.0);
		vec3 sc = 0.25 * (src((cpx + o) * ps) + src((cpx - o) * ps) + src((cpx + o.yx) * ps) + src((cpx - o.yx) * ps));
		vec4 ink = ht_ink(sc);
		// Punktfläche = Deckung: r = sqrt(a/pi) bis die Punkte sich berühren, darüber schneller bis voll
		float r = ht_cell * sqrt(ink.a / 3.14159) * (1.0 + 0.25 * smoothstep(0.6, 1.0, ink.a));
		float d = length(q - cc) * ht_cell;
		float cov = 1.0 - smoothstep(r - 0.7, r + 0.7, d);
		if (cov > best) {
			best = cov;
			best_ink = ink.rgb;
		}
	}
	return mix(col, best_ink * col, best);
}

// ---------------------------------------------------------------- Paletten-Reduktion
vec3 srgb_to_oklab(vec3 c) {
	vec3 l = mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c));
	float L = 0.4122214708 * l.r + 0.5363325363 * l.g + 0.0514459929 * l.b;
	float M = 0.2119034982 * l.r + 0.6806995451 * l.g + 0.1073969566 * l.b;
	float S = 0.0883024619 * l.r + 0.2817188376 * l.g + 0.6299787005 * l.b;
	vec3 lms = pow(max(vec3(L, M, S), vec3(0.0)), vec3(1.0 / 3.0));
	return vec3(
		0.2104542553 * lms.x + 0.7936177850 * lms.y - 0.0040720468 * lms.z,
		1.9779984951 * lms.x - 2.4285922050 * lms.y + 0.4505937099 * lms.z,
		0.0259040371 * lms.x + 0.7827717662 * lms.y - 0.8086757660 * lms.z);
}

float bayer4(vec2 p) {
	ivec2 i = ivec2(mod(p, 4.0));
	int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
	return (float(m[i.y * 4 + i.x]) + 0.5) / 16.0;
}

vec3 palette_look(vec2 px, vec2 ps) {
	vec2 cell = floor(px / pal_pixel);
	vec2 cen = (cell + 0.5) * pal_pixel;
	// Blockmittel aus vier bilinearen Abtastungen (≈ 4×4 px)
	vec3 c = 0.25 * (src((cen + vec2(-1.0, -1.0)) * ps) + src((cen + vec2(1.0, -1.0)) * ps)
		+ src((cen + vec2(-1.0, 1.0)) * ps) + src((cen + vec2(1.0, 1.0)) * ps));
	c = clamp(c + (bayer4(cell) - 0.5) * pal_spread, 0.0, 1.0);
	vec3 lab = srgb_to_oklab(c);
	float best = 1e9;
	vec3 out_c = pal_rgb[0];
	for (int i = 0; i < 16; i++) {
		if (i >= pal_count) {
			break;
		}
		vec3 d = (lab - pal_lab[i]) * vec3(1.0, 1.4, 1.4);
		float e = dot(d, d);
		if (e < best) {
			best = e;
			out_c = pal_rgb[i];
		}
	}
	return out_c;
}

void fragment() {
	vec2 ps = TEXTURE_PIXEL_SIZE;
	vec2 px = UV / ps;
	vec3 base = src(UV);
	vec3 c = base;
	if (look == 2) {
		c = film_look(UV, px, ps);
	} else if (look == 3) {
		c = lut(base);
	} else if (look == 4) {
		c = halftone_look(px, ps);
	} else if (look == 5) {
		c = palette_look(px, ps);
	}
	COLOR = vec4(c, 1.0);
}
