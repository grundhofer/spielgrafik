// Wasser als bildschirmfüllende Fläche unter allen Schichten. Rechnet je Pixel die Weltlage (Kamera dreht mit),
// damit Wellen, Ufergischt und Glitzern an der Welt haften. Feste Farbstufen, keine Verläufe.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D world_map : filter_nearest, repeat_disable;  // R Ufernähe, G Geländeschatten, B Höhe*8
uniform vec4 world_rect = vec4(-64.0, -184.0, 576.0, 576.0);
uniform vec2 view_size = vec2(426.0, 240.0);
uniform vec4 c_deep : source_color = vec4(0.10, 0.11, 0.24, 1.0);
uniform vec4 c_dark : source_color = vec4(0.13, 0.16, 0.32, 1.0);
uniform vec4 c_mid : source_color = vec4(0.17, 0.24, 0.42, 1.0);
uniform vec4 c_light : source_color = vec4(0.25, 0.35, 0.52, 1.0);
uniform vec4 c_sheen : source_color = vec4(0.47, 0.40, 0.58, 1.0);
uniform vec4 c_warm : source_color = vec4(0.86, 0.52, 0.42, 1.0);
uniform vec4 c_glint : source_color = vec4(1.00, 0.82, 0.55, 1.0);
uniform vec4 c_foam : source_color = vec4(0.72, 0.78, 0.86, 1.0);
uniform vec4 c_shallow : source_color = vec4(0.22, 0.38, 0.48, 1.0);

global uniform vec2 cam_cs;
global uniform vec2 cam_pivot;
global uniform vec2 cam_center;
global uniform float sim_time;
global uniform vec4 light_lantern;
global uniform vec4 light_lamp;
global uniform vec4 light_window;
global uniform vec4 boat_a;     // xy Welt, z Drehung (rad), w Länge
global uniform vec4 boat_b;

vec2 rot(vec2 v, vec2 cs) { return vec2(cs.x * v.x - cs.y * v.y, cs.y * v.x + cs.x * v.y); }

float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float vnoise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

float bayer4(ivec2 p) {
	int x = p.x & 3, y = p.y & 3;
	int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
	return (float(m[y * 4 + x]) + 0.5) / 16.0;
}

// Abstand zum Rumpf eines Boots (Ellipse in Bootsrichtung), < 0 innen
float hull_dist(vec2 w, vec4 b) {
	vec2 d = rot(w - b.xy, vec2(cos(-b.z), sin(-b.z)));
	vec2 r = vec2(b.w * 0.5, b.w * 0.19);
	return (length(d / r) - 1.0) * min(r.x, r.y);
}

// Farbstufen als Nummern, erst am Ende in Farben übersetzt
const int W_DEEP = 0, W_DARK = 1, W_MID = 2, W_LIGHT = 3, W_SHEEN = 4, W_WARM = 5, W_GLINT = 6, W_FOAM = 7, W_SHALLOW = 8;

void fragment() {
	vec2 sp = floor(UV * view_size) + 0.5;                 // Bildpixel
	ivec2 ip = ivec2(sp);
	vec2 w = cam_pivot + rot(sp - cam_center, vec2(cam_cs.x, -cam_cs.y));
	vec2 wi = floor(w);                                     // ganzes Weltpixel -> Muster haftet an der Welt
	vec4 map = texture(world_map, (wi + 0.5 - world_rect.xy) / world_rect.zw);
	float t = sim_time;

	// Grundton: oben (Richtung Horizont) Abendschein, unten tiefes Blau
	float yv = sp.y / view_size.y;
	float swell = vnoise(wi * vec2(0.035, 0.07) + vec2(t * 0.15, -t * 0.05));
	float tone = 1.3 - yv * 2.1 + (swell - 0.5) * 1.1 + (bayer4(ip) - 0.5) * 0.32;
	int k = tone > 1.0 ? W_SHEEN : (tone > 0.35 ? W_MID : (tone > -0.35 ? W_DARK : W_DEEP));

	// Flachwasser am Ufer
	float near = map.r;
	if (near > 0.62 && near < 0.99) {
		k = W_SHALLOW;
	}

	// Wellenzüge in Weltrichtung (leicht schräg), helle Kämme und dunkle Täler als Pixelstriche
	float ph = wi.y * 0.55 + sin(wi.x * 0.09 + t * 0.7) * 1.6 + vnoise(wi * 0.06) * 3.0 - t * 2.4;
	float crest = sin(ph);
	float broken = vnoise(wi * vec2(0.22, 0.5) + vec2(t * 0.4, 0.0));
	if (crest > 0.95 && broken > 0.52) {
		k = tone > 0.6 ? W_WARM : W_LIGHT;
	} else if (crest < -0.96 && broken > 0.5) {
		k = W_DEEP;
	}

	// Gischt am Ufer
	if (near > 0.35 && near < 0.99) {
		float lap = sin(near * 9.0 - t * 2.6 + vnoise(wi * 0.12) * 4.0);
		if ((near > 0.8 && lap > 0.55) || (near > 0.66 && lap > 0.82 && broken > 0.4)) {
			k = W_FOAM;
		}
	}

	// Schaumring um die Boote (wandert mit dem Schaukeln)
	float hb = min(hull_dist(w, boat_a), hull_dist(w, boat_b));
	if (hb > -0.5 && hb < 2.5) {
		float ring = sin(hb * 2.2 - t * 3.0);
		if (hb < 1.2 || (ring > 0.6 && broken > 0.35)) {
			k = W_FOAM;
		}
	} else if (hb > 2.5 && hb < 5.0 && sin(hb * 1.6 - t * 2.2) > 0.85 && broken > 0.5) {
		k = W_LIGHT;
	}

	// Schatten des Geländes: eine Stufe tiefer
	if (map.g > 0.5) {
		k = k == W_FOAM ? W_LIGHT : ((k == W_SHEEN || k == W_WARM) ? W_MID : (k == W_SHALLOW ? W_DARK : W_DEEP));
	}

	// Glitzern: warme Funken nahe der Lichter und im Abendschein
	vec2 cell = floor(wi / 2.0);
	float sparkle = hash(cell + floor(t * 7.0) * 17.31);
	float dl = min(length(w - light_lantern.xy) * 0.9, min(length(w - light_window.xy) * 1.2, length(w - light_lamp.xy) * 0.8));
	float near_light = clamp(1.0 - dl / 70.0, 0.0, 1.0);
	if (sparkle > 0.995 - near_light * 0.07 && crest > 0.2) {
		k = W_GLINT;
	} else if (sparkle > 0.997 && tone > 0.8) {
		k = W_WARM;
	}

	vec4 cols[9] = vec4[](c_deep, c_dark, c_mid, c_light, c_sheen, c_warm, c_glint, c_foam, c_shallow);
	COLOR = cols[k];
}
