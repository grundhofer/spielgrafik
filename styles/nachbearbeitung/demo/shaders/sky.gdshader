// Abendhimmel für die Hafenszene: Verlauf von Nachtblau über Violett zum orangen Horizontband, flache
// Wolkenbänke dicht über dem Horizont (unten vom Abendrot angeleuchtet) und die ersten Sterne.
// Sterne leuchten über 1 (HDR), damit der Bloom-Look sie erfasst. Zeit kommt als Uniform (reproduzierbar).
shader_type sky;
render_mode use_debanding;

uniform vec3 top_color : source_color = vec3(0.025, 0.055, 0.20);
uniform vec3 mid_color : source_color = vec3(0.22, 0.17, 0.38);
uniform vec3 low_color : source_color = vec3(0.78, 0.42, 0.40);
uniform vec3 horizon_color : source_color = vec3(1.0, 0.63, 0.36);
uniform vec3 cloud_dark : source_color = vec3(0.16, 0.12, 0.22);
uniform vec3 cloud_lit : source_color = vec3(1.0, 0.52, 0.30);
uniform vec3 glow_dir = vec3(-0.75, 0.0, -0.66);   // Richtung des hellsten Horizonts (links hinten)
uniform float star_energy = 2.2;
uniform float time_s = 0.0;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x),
		mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x), f.y);
}

float fbm(vec2 p) {
	float s = 0.0;
	float a = 0.5;
	for (int i = 0; i < 5; i++) {
		s += a * vnoise(p);
		p = p * 2.03 + vec2(17.1, 3.7);
		a *= 0.5;
	}
	return s;
}

void sky() {
	vec3 d = normalize(EYEDIR);
	float h = d.y;
	float toward = clamp(dot(normalize(vec3(d.x, 0.0, d.z)), normalize(glow_dir)) * 0.5 + 0.5, 0.0, 1.0);
	// Verlauf
	vec3 col = mix(horizon_color, low_color, smoothstep(0.0, 0.07, h));
	col = mix(col, mid_color, smoothstep(0.05, 0.22, h));
	col = mix(col, top_color, smoothstep(0.18, 0.62, h));
	// Horizontband heller zur Abendseite
	col += horizon_color * 0.45 * toward * (1.0 - smoothstep(0.0, 0.08, abs(h)));
	// Wolkenbänke: Projektion auf eine Ebene, waagerecht gestreckt, nur dicht über dem Horizont
	if (h > 0.0) {
		vec2 p = d.xz / max(h, 0.015) * 0.11;
		p = vec2(p.x * 0.55 + time_s * 0.012, p.y * 2.4);
		float n = fbm(p);
		float band = smoothstep(0.015, 0.05, h) * (1.0 - smoothstep(0.10, 0.24, h));
		float cov = smoothstep(0.50, 0.70, n) * band;
		float lit = smoothstep(0.45, 0.75, fbm(p + vec2(0.0, 0.35))) * 0.6 + 0.25 * toward;
		vec3 cc = mix(cloud_dark, cloud_lit, clamp(lit * (1.0 - smoothstep(0.03, 0.16, h)) + 0.1, 0.0, 1.0));
		col = mix(col, cc, cov * 0.92);
		// Sterne (nicht in der Radiance-Cubemap)
		if (!AT_CUBEMAP_PASS) {
			vec2 sp = vec2(atan(d.x, -d.z), asin(h)) * 260.0;
			vec2 cell = floor(sp);
			float r = hash12(cell);
			if (r < 0.006) {
				vec2 c = vec2(hash12(cell + 7.1), hash12(cell + 3.3)) * 0.6 + 0.2;
				float dist = length(fract(sp) - c);
				float tw = 0.75 + 0.25 * sin(time_s * (2.0 + 5.0 * hash12(cell + 1.9)) + r * 600.0);
				float b = (1.0 - smoothstep(0.08, 0.22, dist)) * tw * (0.4 + 0.6 * hash12(cell + 5.5));
				b *= smoothstep(0.16, 0.42, h) * (1.0 - cov);
				col += vec3(0.95, 0.93, 1.0) * b * star_energy;
			}
		}
	} else {
		col = mix(horizon_color * 0.5, vec3(0.05, 0.07, 0.12), smoothstep(0.0, 0.2, -h));
	}
	COLOR = col;
}
