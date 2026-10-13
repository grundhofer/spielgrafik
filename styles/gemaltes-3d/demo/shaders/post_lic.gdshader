// Nachbearbeitung 3: Pinselstriche. Linienintegral-Faltung (LIC, Cabral und Leedom 1993) des
// Strichrauschens aus der Steuerkarte (G) entlang der Kantenrichtung: aus weißem Rauschen werden
// feine Borstenstriche, die den Formen folgen. Weil das Rauschen an den Oberflächen festgemacht ist
// (paint_common.gdshaderinc), wandern die Striche mit Figur, Booten und Kamera mit, statt wie eine
// Glasscheibe vor dem Bild stehen zu bleiben. Strichlänge je Pixel aus der Pinselgröße (R).
// Ausgabe: r = Strichwert 0..1 (0,5 = neutral).
shader_type canvas_item;

#include "res://shaders/post_flow.gdshaderinc"

uniform sampler2D tfm : filter_nearest, repeat_disable;
uniform sampler2D ctrl : filter_nearest, repeat_disable;
uniform float len_min = 4.0;     // halbe Strichlänge in Pixeln bei Steuerwert 0
uniform float len_max = 11.0;    // bei Steuerwert 1
uniform float contrast = 1.0;
uniform float calm_threshold = 0.25; // unter dieser Anisotropie (ruhige Flächen) laufen Striche waagrecht
uniform float screen_noise = 0.0;   // Vergleichsschalter: 1 = Rauschen fest im Bild statt an den Oberflächen

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash_px(ivec2 q) {
	vec3 p3 = fract(vec3(vec2(q).xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

// Strichrichtung: Kantenrichtung, in ruhigen Flächen (kaum Struktur, z. B. Himmel) zur Waagrechten
// gezogen, sonst kreiseln die Striche dort wie im Ölfilter einer Bildbearbeitung
vec2 stroke_dir(ivec2 q) {
	vec3 f = flow_from_tensor(texelFetch(tfm, q, 0).rgb);
	vec2 d = f.x < 0.0 ? -f.xy : f.xy;
	float k = smoothstep(0.0, calm_threshold, f.z);
	return normalize(mix(vec2(1.0, 0.0), d, k) + vec2(1e-5, 0.0));
}

float noise_at(ivec2 q) {
	return screen_noise > 0.5 ? hash_px(q) : texelFetch(ctrl, q, 0).g;
}

void fragment() {
	ivec2 sz = textureSize(ctrl, 0);
	ivec2 p = ivec2(UV * vec2(sz));
	vec4 c0 = texelFetch(ctrl, p, 0);
	float L = mix(len_min, len_max, clamp(c0.r, 0.0, 1.0));
	int steps = int(L);
	float sigma = L * 0.5;
	float acc = noise_at(p);
	float wsum = 1.0;
	float w2sum = 1.0;
	for (int side = 0; side < 2; side++) {
		vec2 pos = vec2(p) + 0.5;
		vec2 prev = stroke_dir(p) * (side == 0 ? 1.0 : -1.0);
		for (int k = 1; k <= steps; k++) {
			ivec2 ip = clamp(ivec2(pos), ivec2(0), sz - 1);
			vec2 d = stroke_dir(ip);
			if (dot(d, prev) < 0.0) {
				d = -d;
			}
			pos += d;
			prev = d;
			ip = clamp(ivec2(pos), ivec2(0), sz - 1);
			float w = exp(-float(k * k) / (2.0 * sigma * sigma));
			acc += w * noise_at(ip);
			wsum += w;
			w2sum += w * w;
		}
	}
	float m = acc / wsum;
	// gemitteltes Rauschen hat kleinere Streuung: auf die Streuung eines einzelnen Werts zurückrechnen
	float gain = wsum / sqrt(w2sum);
	float s = 0.5 + (m - 0.5) * gain * 0.5 * contrast;
	COLOR = vec4(clamp(s, 0.0, 1.0), 0.0, 0.0, 1.0);
}
