// Gemeinsame Rauschfunktionen der Diorama-Shader (deterministisch, ohne Texturen).

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float dio_hash13(vec3 p) {
	p = fract(p * 0.1031);
	p += dot(p, p.zyx + 31.32);
	return fract((p.x + p.y) * p.z);
}

float dio_hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

// Wertrauschen 3D, Bereich 0..1
float dio_vnoise(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	vec3 u = f * f * (3.0 - 2.0 * f);
	float a = dio_hash13(i);
	float b = dio_hash13(i + vec3(1, 0, 0));
	float c = dio_hash13(i + vec3(0, 1, 0));
	float d = dio_hash13(i + vec3(1, 1, 0));
	float e = dio_hash13(i + vec3(0, 0, 1));
	float g = dio_hash13(i + vec3(1, 0, 1));
	float h = dio_hash13(i + vec3(0, 1, 1));
	float k = dio_hash13(i + vec3(1, 1, 1));
	return mix(mix(mix(a, b, u.x), mix(c, d, u.x), u.y), mix(mix(e, g, u.x), mix(h, k, u.x), u.y), u.z);
}

float dio_fbm(vec3 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		s += a * dio_vnoise(p);
		p = p * 2.03 + vec3(1.7, 9.2, 3.1);
		a *= 0.5;
	}
	return s / 0.9375;
}

// Wertrauschen 2D, Bereich 0..1
float dio_vnoise2(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(dio_hash12(i), dio_hash12(i + vec2(1, 0)), u.x),
		mix(dio_hash12(i + vec2(0, 1)), dio_hash12(i + vec2(1, 1)), u.x), u.y);
}

float dio_fbm2(vec2 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		s += a * dio_vnoise2(p);
		p = p * 2.07 + vec2(3.1, 7.7);
		a *= 0.5;
	}
	return s / 0.9375;
}

// Zellrauschen 3D: x = Abstand zum nächsten Punkt, y = Zufallswert der Zelle
vec2 dio_cells(vec3 p) {
	vec3 i = floor(p);
	vec3 f = fract(p);
	float best = 8.0;
	float id = 0.0;
	for (int z = -1; z <= 1; z++)
	for (int y = -1; y <= 1; y++)
	for (int x = -1; x <= 1; x++) {
		vec3 o = vec3(float(x), float(y), float(z));
		vec3 c = i + o;
		vec3 r = o + vec3(dio_hash13(c), dio_hash13(c + 17.1), dio_hash13(c + 41.7)) - f;
		float d = dot(r, r);
		if (d < best) {
			best = d;
			id = dio_hash13(c + 5.3);
		}
	}
	return vec2(sqrt(best), id);
}
