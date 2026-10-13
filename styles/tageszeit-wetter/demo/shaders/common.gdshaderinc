// Gemeinsam für Hintergrund und Figur: Farb-LUT des Zustands, Nebel, Blitz.
// Alle Werte setzt main.gd je Bild auf jedes Material (gleiche Namen), damit Figur und Hintergrund
// immer dieselbe Farbkorrektur bekommen.

uniform sampler2D lut_tex : filter_linear, repeat_disable;   // 6 LUTs à 1024×32 übereinander
uniform float lut_a = 0.0;      // Zeile (Zustand) A
uniform float lut_b = 0.0;      // Zeile (Zustand) B
uniform float lut_mix = 0.0;    // 0 = A, 1 = B
uniform float fog = 0.0;        // Nebeldichte
uniform vec3 fog_col = vec3(0.7, 0.72, 0.75);
uniform float fog_front = 1.0;  // 0..1: Nebel zieht von fern nach nah herein (1 = überall)
uniform float flash = 0.0;      // Blitz 0..1
uniform float time = 0.0;

const float LUT_N = 32.0;
const float LUT_ROWS = 6.0;

vec3 lut_sample(vec3 c, float row) {
	c = clamp(c, 0.0, 1.0);
	float b = c.b * (LUT_N - 1.0);
	float b0 = floor(b);
	float b1 = min(b0 + 1.0, LUT_N - 1.0);
	float f = b - b0;
	float x = c.r * (LUT_N - 1.0) + 0.5;
	float y = (row * LUT_N + c.g * (LUT_N - 1.0) + 0.5) / (LUT_N * LUT_ROWS);
	vec3 s0 = texture(lut_tex, vec2((b0 * LUT_N + x) / (LUT_N * LUT_N), y)).rgb;
	vec3 s1 = texture(lut_tex, vec2((b1 * LUT_N + x) / (LUT_N * LUT_N), y)).rgb;
	return mix(s0, s1, f);
}

vec3 grade(vec3 c) {
	vec3 a = lut_sample(c, lut_a);
	if (lut_mix <= 0.0) {
		return a;
	}
	return mix(a, lut_sample(c, lut_b), lut_mix);
}

// Nebelanteil aus Entfernung (0 nah .. 1 Himmel) und einem Rauschwert um 1
float fog_amount(float dist, float n) {
	float edge = 1.0 - fog_front * 1.3;
	float front = smoothstep(edge, edge + 0.3, dist + (n - 1.0) * 0.15);
	return (1.0 - exp(-fog * (dist * 2.6 + 0.10) * n)) * front;
}

// Hash ohne sin (rechnet in allen Renderern gleich)
// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
