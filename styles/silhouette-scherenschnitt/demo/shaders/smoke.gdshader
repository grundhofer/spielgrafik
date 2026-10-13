// Rauch aus dem Schornstein als geschnittene Papierwölkchen: alle 0,45 s steigt ein Ballen auf, wächst und
// treibt mit dem Wind (von See) nach links. Jeder Ballen hat einen dunklen Kern und einen helleren Rand,
// die Kanten sind scharf (zwei flache Töne) und durch ein Rauschen leicht ausgefranst.
shader_type canvas_item;

uniform float t = 0.0;
uniform vec2 rect_size = vec2(240.0, 140.0);
uniform vec2 source = vec2(210.0, 138.0);   // Schornsteinmündung im Rechteck
uniform vec4 col_a : source_color = vec4(0.27, 0.18, 0.30, 1.0);
uniform vec4 col_b : source_color = vec4(0.46, 0.31, 0.44, 1.0);
uniform float interval = 0.45;
uniform float life = 5.0;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash11(float p) {
	p = fract(p * 0.1031);
	p *= p + 33.33;
	p *= p + p;
	return fract(p);
}
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}
float vnoise(vec2 p) {
	vec2 i = floor(p), f = fract(p);
	vec2 u = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y);
}

void fragment() {
	vec2 p = floor(UV * rect_size) + 0.5;
	float core = 0.0;
	float rim = 0.0;
	float newest = floor(t / interval);
	for (int k = 0; k < 12; k++) {
		float i = newest - float(k);
		float age = t - i * interval;
		if (age < 0.0 || age > life) {
			continue;
		}
		float h = hash11(i * 1.37 + 3.0);
		// Bahn: steigt mit abnehmender Geschwindigkeit, Wind treibt mit der Höhe stärker nach links
		float rise = 30.0 * age - 2.2 * age * age;
		vec2 c = source + vec2(-6.0 * age - 4.5 * age * age + (h - 0.5) * 8.0, -rise);
		float r = 5.0 + 7.5 * age + h * 3.0;
		float n = vnoise((p - c) * 0.16 + vec2(i * 3.1, 0.0)) - 0.5;
		float d = length((p - c) * vec2(0.85, 1.0)) / r + n * 0.35;
		float fade = 1.0 - smoothstep(life * 0.55, life, age);
		core = max(core, step(d, 0.62) * fade * step(0.35, fade));
		rim = max(rim, step(d, 1.0) * fade);
	}
	float a_rim = rim * 0.55;
	vec4 c = vec4(col_b.rgb, a_rim);
	c = mix(c, vec4(col_a.rgb, 0.85), core);
	COLOR = c;
}
