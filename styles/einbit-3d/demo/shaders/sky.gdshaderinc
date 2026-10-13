// Abendhimmel als Helligkeit (keine Farbe: das Bild hat ohnehin nur zwei Töne).
// Genutzt vom Nachbearbeitungs-Shader (Himmelspixel, Dunst) und vom Wasser (Spiegelung).
// Richtung in Weltkoordinaten; die Sonne ist rechts (+X) untergegangen: dort ist das Glutband heller.
// Wolken liegen auf der Himmelskugel (Azimut, Höhe) und treiben langsam nach rechts.

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float sky_hash(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float sky_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(sky_hash(i), sky_hash(i + vec2(1.0, 0.0)), u.x),
		mix(sky_hash(i + vec2(0.0, 1.0)), sky_hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float sky_fbm(vec2 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		s += a * sky_noise(p);
		p = p * 2.03 + vec2(17.0, 5.0);
		a *= 0.5;
	}
	return s;
}

// Wolkendichte 0..1 (flache Bänder knapp über dem Horizont)
float sky_clouds(vec3 dir, float time) {
	float e = dir.y;
	float az = atan(dir.x, -dir.z);
	float band = smoothstep(0.035, 0.07, e) * (1.0 - smoothstep(0.2, 0.34, e));
	float c = sky_fbm(vec2(az * 5.0 - time * 0.012, e * 34.0));
	return smoothstep(0.5, 0.62, c) * band;
}

float sky_luminance(vec3 dir, float time) {
	float e = max(dir.y, 0.0);
	float west = mix(0.55, 1.0, smoothstep(-0.5, 0.9, dir.x));     // rechts heller
	float glow = exp(-e * 14.0) * west;                              // Glutband am Horizont
	float L = 0.003 + 0.02 * exp(-e * 4.0) + 0.5 * glow;
	// Wolken: dunkle Streifen vor dem Glutband, mit hellerem Saum unten
	float c = sky_clouds(dir, time);
	float under = sky_clouds(dir + vec3(0.0, 0.012, 0.0), time);
	L = mix(L, 0.02 + 0.12 * glow, c * 0.9);
	L += 0.18 * glow * max(under - c, 0.0);
	return L;
}
