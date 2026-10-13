// Meer aus Knete: Reihen gerollter Wellenwülste, die in Stufen (10 Bilder/s, sea_t) zum Kai wandern.
// Jede Reihe ist in Stücke von 1–3 m gebrochen und leicht gebogen, einzelne Kämme tragen weiße Knete.
// Die feine Oberfläche wird je Animationsbild leicht neu "geknetet" (sea_seed), wie bei Ersatzteilen.
// Höhe und Normale kommen aus derselben Funktion in Weltkoordinaten (Gitter aus main.gd, Ursprung 0).
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert_wrap, specular_schlick_ggx;

#include "res://shaders/clay_noise.gdshaderinc"

uniform vec3 deep : source_color = vec3(0.09, 0.22, 0.31);
uniform vec3 crest : source_color = vec3(0.22, 0.47, 0.55);
uniform vec3 foam : source_color = vec3(0.86, 0.88, 0.84);
uniform float sea_t = 0.0;          // gestufte Zeit (s)
uniform float sea_seed = 0.0;       // Index des Animationsbilds
uniform float wave_len = 1.15;       // m zwischen zwei Reihen
uniform float wave_h = 0.14;       // m Wulsthöhe
uniform float speed = 0.28;         // m/s, mit der die Reihen zum Kai wandern
uniform float roughness = 0.55;

varying vec3 wpos;

// x: Höhe (m), y: Wulst 0..1, z: Schaum 0..1
vec3 sea_field(vec2 p) {
	float warp = 1.1 * kn_vnoise(vec3(p * 0.28, 1.0)) + 0.35 * kn_vnoise(vec3(p * 0.9, 4.0));
	float u = p.y / wave_len + warp - sea_t * speed / wave_len;
	float row = floor(u);
	float f = fract(u) - 0.5;
	// Stücke entlang x: je Reihe eigenes Rauschen, Stücke wandern mit ihrer Reihe
	float segn = kn_vnoise(vec3(p.x * 0.55, row * 3.17, 2.0)) + 0.35 * kn_vnoise(vec3(p.x * 1.7, row * 1.3, 9.0));
	float seg = smoothstep(-0.25, 0.25, segn);
	// gebogener Wulst: Querprofil weich gerundet, vorn steiler (zum Kai hin)
	float w = 0.22 + 0.06 * kn_vnoise(vec3(p.x * 1.3, row, 5.0));
	float x = f / w;
	float prof = exp(-x * x * (x > 0.0 ? 2.2 : 1.1));
	float ridge = prof * seg;
	float h = wave_h * ridge;
	// Grundfläche: flache Beulen, zwischen den Animationsbildern leicht neu geknetet
	h += 0.012 * kn_fbm(vec3(p.x * 1.4, p.y * 1.4, 0.0), 2);
	h += 0.0035 * kn_vnoise(vec3(p * 7.0, sea_seed * 0.61));
	float fo = smoothstep(0.78, 0.95, prof) * smoothstep(0.3, 0.7, segn) * step(0.35, kn_hash13(vec3(row, 7.0, 1.0)));
	return vec3(h, ridge, fo);
}

void vertex() {
	vec3 w = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 s = sea_field(w.xz);
	VERTEX.y += s.x;
	wpos = w + vec3(0.0, s.x, 0.0);
}

void fragment() {
	vec2 p = wpos.xz;
	float fw = max(length(dFdx(wpos)), length(dFdy(wpos)));
	float e = max(0.012, fw * 0.7);
	vec3 s0 = sea_field(p);
	float hx = sea_field(p + vec2(e, 0.0)).x - s0.x;
	float hz = sea_field(p + vec2(0.0, e)).x - s0.x;
	// Fingerabdrücke im Meer: beim Formen der Wülste hinterlassen, nur Mulden
	float ridge_vis = 1.0 - smoothstep(0.003, 0.006, fw);
	vec3 q = vec3(p.x, 0.0, p.y);
	float pr0 = kn_prints(q, 0.22, 0.5, 0.004, 0.0006, 0.016, ridge_vis, floor(sea_seed / 3.0));
	float prx = kn_prints(q + vec3(e, 0.0, 0.0), 0.22, 0.5, 0.004, 0.0006, 0.016, ridge_vis, floor(sea_seed / 3.0)) - pr0;
	float prz = kn_prints(q + vec3(0.0, 0.0, e), 0.22, 0.5, 0.004, 0.0006, 0.016, ridge_vis, floor(sea_seed / 3.0)) - pr0;
	vec3 nw = normalize(vec3(-(hx + prx) / e, 1.0, -(hz + prz) / e));
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);

	vec3 c = mix(deep, crest, smoothstep(0.1, 0.9, s0.y));
	c *= 1.0 + 0.08 * kn_fbm(vec3(p * 2.0, 3.0), 2);
	c = mix(c, foam, s0.z * (1.0 - smoothstep(0.07, 0.16, fw)));
	c *= 1.0 - 0.25 * clamp(-pr0 / 0.004, 0.0, 1.0);
	ALBEDO = c;
	ROUGHNESS = mix(roughness, 0.6, s0.z);
	SPECULAR = 0.3;
}
