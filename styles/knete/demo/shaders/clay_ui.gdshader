// Knetplatte für die Oberfläche: von Hand ausgerollte Platte mit gerundetem, leicht welligem Rand,
// Fingerabdrücken, Krümeln und weichem Schatten auf das Bild darunter. Licht von links oben.
// Gezeichnet auf einem ColorRect, das an jeder Seite 'margin' Pixel Platz für den Schatten lässt.
shader_type canvas_item;

#include "res://shaders/clay_noise.gdshaderinc"

uniform vec2 size = vec2(400.0, 200.0);
uniform float margin = 20.0;
uniform float radius = 26.0;
uniform float bevel = 13.0;
uniform float wobble = 2.6;
uniform vec3 base : source_color = vec3(0.93, 0.88, 0.77);
uniform float seed = 0.0;
uniform vec2 shadow_off = vec2(4.0, 8.0);
uniform float shadow_blur = 13.0;
uniform float shadow_alpha = 0.42;
uniform float prints_amt = 1.0;
uniform bool circle = false;
uniform bool pressed = false;      // eingedrückte Mulde statt Wulst (ausgewählte Zeile)
uniform float speck_amt = 0.75;    // dunkle Krümel (auf kleinen Teilen aus, sonst stören sie die Schrift)

// Distanzfunktion abgerundetes Rechteck nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
float sd_round_rect(vec2 p, vec2 b, float r) {
	vec2 q = abs(p) - b + r;
	return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

float shape_sd(vec2 pos) {
	vec2 c = size * 0.5;
	float d;
	if (circle) {
		d = length(pos - c) - (min(size.x, size.y) * 0.5 - margin);
	} else {
		d = sd_round_rect(pos - c, c - margin, radius);
	}
	d += wobble * kn_vnoise(vec3(pos * 0.011, seed)) + wobble * 0.35 * kn_vnoise(vec3(pos * 0.045, seed + 3.0));
	return d;
}

float height(vec2 pos) {
	float d = shape_sd(pos);
	float x = clamp(-d / bevel, 0.0, 1.0);
	float h = sqrt(1.0 - (1.0 - x) * (1.0 - x)) * bevel * 0.7;
	if (pressed) {
		h = -h * 0.35;
	}
	h += prints_amt * kn_prints(vec3(pos, seed * 13.0), 95.0, 0.42, 2.4, 0.32, 6.5, 1.0, seed);
	h += 0.9 * kn_fbm(vec3(pos * 0.045, seed + 1.0), 2);
	float w = kn_worley(vec3(pos / 22.0, seed + 5.0), 2.0) * 22.0;
	h -= 0.9 * (1.0 - smoothstep(1.0, 2.2, w));
	return h;
}

void fragment() {
	vec2 pos = UV * size;
	float d = shape_sd(pos);
	float h = height(pos);
	float hx = height(pos + vec2(1.0, 0.0)) - h;
	float hy = height(pos + vec2(0.0, 1.0)) - h;
	vec3 n = normalize(vec3(-hx, -hy, 1.0));
	vec3 L = normalize(vec3(-0.45, -0.62, 0.64));
	float diff = dot(n, L);
	float shade = 0.70 + 0.44 * diff;
	vec3 hv = normalize(L + vec3(0.0, 0.0, 1.0));
	float sp = pow(max(dot(n, hv), 0.0), 22.0) * 0.16;
	vec3 col = base * (1.0 + 0.06 * kn_fbm(vec3(pos * 0.008, seed + 9.0), 2));
	float sw = kn_worley(vec3(pos / 30.0, seed + 11.0), 4.0) * 30.0;
	col = mix(col, col * 0.4, (1.0 - smoothstep(1.0, 1.9, sw)) * speck_amt);
	col = col * shade + sp;
	float inside = 1.0 - smoothstep(-0.7, 0.7, d);
	float ds = shape_sd(pos - shadow_off);
	float sh = (1.0 - smoothstep(-shadow_blur * 0.4, shadow_blur, ds)) * shadow_alpha;
	vec4 outside = vec4(0.05, 0.03, 0.06, sh);
	COLOR = mix(outside, vec4(col, 1.0), inside);
}
