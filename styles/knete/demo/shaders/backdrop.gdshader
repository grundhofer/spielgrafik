// Himmelsprospekt aus verstrichener Knete (Plastilinmalerei auf einer Platte hinter dem Set):
// Farbbänder mit dem Daumen waagrecht ineinander verstrichen, darauf modellierte Wolkenwülste und
// Sterne als kleine Kügelchen. Unbeleuchtet: das Relief wird mit einer festen Lichtrichtung schattiert
// (warmes Licht vom Horizont), weil das Studiolicht den 60 m entfernten Prospekt nicht sinnvoll trifft.
// Koordinaten: Weltposition auf der Platte (x waagrecht, y hoch, Meter).
shader_type spatial;
render_mode unshaded, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/clay_noise.gdshaderinc"

uniform vec3 c_top : source_color = vec3(0.13, 0.15, 0.33);
uniform vec3 c_mid : source_color = vec3(0.42, 0.30, 0.48);
uniform vec3 c_low : source_color = vec3(0.86, 0.47, 0.40);
uniform vec3 c_glow : source_color = vec3(0.99, 0.70, 0.36);
uniform vec3 c_line : source_color = vec3(1.0, 0.86, 0.52);
uniform vec3 c_cloud : source_color = vec3(0.47, 0.36, 0.50);
uniform vec3 c_cloud_lit : source_color = vec3(0.98, 0.62, 0.42);
uniform vec3 c_star : source_color = vec3(1.0, 0.93, 0.70);
uniform float horizon_y = -0.8;
uniform float brightness = 1.0;

varying vec3 wpos;

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

// Wolkenwülste: je Wolke 5 Lappen (Ellipsen), Kuppelprofil, unten flach abgestrichen.
// Rückgabe: Höhe der Wolke (0..~1), 0 außerhalb.
float clouds(vec2 p) {
	float h = 0.0;
	for (int i = 0; i < 9; i++) {
		float fi = float(i);
		vec3 r = kn_hash33(vec3(fi, 3.3, 8.1));
		vec2 c = vec2(-46.0 + fi * 15.5 + 9.0 * r.x, 7.0 + 15.0 * r.y + 4.0 * float(i % 2));
		float len = 10.0 + 9.0 * r.z;
		float th = 1.5 + 1.4 * r.y;
		for (int j = 0; j < 5; j++) {
			float fj = float(j);
			vec3 q = kn_hash33(vec3(fi, fj, 1.7));
			vec2 lc = c + vec2((fj / 4.0 - 0.5) * len * 0.8 + q.x * 1.5, (q.y - 0.3) * th * 0.6);
			vec2 rad = vec2(len * (0.16 + 0.08 * q.z), th * (0.55 + 0.45 * q.x) * (j == 1 || j == 2 ? 1.25 : 0.9));
			vec2 d = (p - lc) / rad;
			float dome = 1.0 - dot(d, d);
			if (dome > 0.0) {
				float bottom = smoothstep(c.y - th * 0.45, c.y - th * 0.2, p.y);
				h = max(h, sqrt(dome) * bottom);
			}
		}
	}
	return h;
}

float stars(vec2 p, out float glow) {
	vec2 cell = vec2(3.6, 3.0);
	vec2 g = p / cell;
	vec2 i = floor(g);
	vec3 r = kn_hash33(vec3(i, 5.0));
	glow = 0.0;
	float on = step(0.87, r.z) * smoothstep(12.0, 20.0, p.y);
	vec2 ctr = (i + 0.2 + 0.6 * r.xy) * cell;
	float rad = 0.11 + 0.08 * r.x;
	float d = length(p - ctr) / rad;
	glow = 0.0;
	return on * sqrt(max(1.0 - d * d, 0.0));
}

float relief(vec2 p, out float cl, out float st, out float sg) {
	// Daumenstriche: waagrecht gestreckte Beulen über die ganze Platte
	float smear = 0.06 * kn_fbm(vec3(p.x * 0.06, p.y * 0.55, 1.0), 3)
		+ 0.03 * kn_vnoise(vec3(p.x * 0.25, p.y * 1.6, 4.0));
	cl = clouds(p);
	st = stars(p, sg);
	float prints = kn_prints(vec3(p * 0.12, 0.0), 0.5, 0.45, 0.25, 0.03, 0.08, 1.0, 3.0);
	return smear + 0.55 * cl + 0.25 * st + 0.35 * prints;
}

void fragment() {
	vec2 p = wpos.xy;
	float cl, st, sg;
	float h = relief(p, cl, st, sg);
	float e = 0.08;
	float cl2, st2, sg2;
	float hx = relief(p + vec2(e, 0.0), cl2, st2, sg2) - h;
	float hy = relief(p + vec2(0.0, e), cl2, st2, sg2) - h;
	vec3 n = normalize(vec3(-hx / e * 0.6, -hy / e * 0.6, 1.0));
	vec3 L = normalize(vec3(0.35, -0.55, 0.75));      // warmes Licht von unten rechts (Horizont)
	float shade = 0.82 + 0.45 * dot(n, L) - 0.45 * L.z;

	// Farbbänder, mit verwischter Höhe gemischt (Strichrichtung waagrecht)
	float y = p.y - horizon_y + 1.8 * kn_fbm(vec3(p.x * 0.05, p.y * 0.35, 7.0), 3);
	vec3 c = mix(c_glow, c_low, smoothstep(0.6, 6.0, y));
	c = mix(c, c_mid, smoothstep(5.0, 15.0, y));
	c = mix(c, c_top, smoothstep(13.0, 32.0, y));
	c = mix(c_line, c, smoothstep(0.0, 1.2, p.y - horizon_y));
	// Wolken: Unterseiten vom Horizont angestrahlt
	float lit = clamp(0.5 - n.y * 1.4, 0.0, 1.0) * (1.0 - smoothstep(6.0, 26.0, p.y) * 0.5);
	vec3 cc = mix(c_cloud, c_cloud_lit, lit);
	c = mix(c, cc, smoothstep(0.02, 0.12, cl));
	c = mix(c, c_star, smoothstep(0.05, 0.3, st));
	c *= shade;
	c += c_star * sg * 0.35;
	ALBEDO = c * brightness;
}
