// Abendhimmel in harten Farbbändern nach der Höhe über dem Horizont, Übergänge mit Bayer-Dither
// (ortsfest zum Bildinhalt), flache Wolkenbänke in drei Tönen (von unten angestrahlt), Sterne als
// einzelne Pixel. Alles hängt nur an der Blickrichtung und an p3d_pan: Bei der Kamerafahrt
// (Objektivverschiebung um ganze Pixel) verschiebt sich der Himmel exakt pixelweise mit.
shader_type sky;

#include "res://shaders/p3d_common.gdshaderinc"

// Farben von unten (Horizont) nach oben und Obergrenzen der Bänder in Grad
uniform vec4 c0 : source_color = vec4(1.0, 0.80, 0.45, 1.0);
uniform vec4 c1 : source_color = vec4(0.97, 0.60, 0.34, 1.0);
uniform vec4 c2 : source_color = vec4(0.87, 0.42, 0.38, 1.0);
uniform vec4 c3 : source_color = vec4(0.66, 0.31, 0.44, 1.0);
uniform vec4 c4 : source_color = vec4(0.43, 0.25, 0.43, 1.0);
uniform vec4 c5 : source_color = vec4(0.27, 0.20, 0.38, 1.0);
uniform vec4 c6 : source_color = vec4(0.16, 0.14, 0.28, 1.0);
uniform vec4 bands_deg = vec4(1.6, 4.2, 8.0, 13.0);
uniform vec2 bands_deg2 = vec2(19.0, 27.0);
uniform float dither_deg = 0.9;            // Breite der gediterten Übergangszone
uniform vec4 cloud_dark : source_color = vec4(0.36, 0.22, 0.38, 1.0);
uniform vec4 cloud_mid : source_color = vec4(0.62, 0.30, 0.42, 1.0);
uniform vec4 cloud_lit : source_color = vec4(0.98, 0.58, 0.40, 1.0);
uniform vec4 star_color : source_color = vec4(1.0, 0.93, 0.80, 1.0);
uniform float cloud_drift = 0.25;          // Grad pro Sekunde

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
	float a = hash12(i);
	float b = hash12(i + vec2(1.0, 0.0));
	float c = hash12(i + vec2(0.0, 1.0));
	float d = hash12(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec3 band_color(int i) {
	if (i <= 0) return c0.rgb;
	if (i == 1) return c1.rgb;
	if (i == 2) return c2.rgb;
	if (i == 3) return c3.rgb;
	if (i == 4) return c4.rgb;
	if (i == 5) return c5.rgb;
	return c6.rgb;
}

void sky() {
	vec3 dir = normalize(EYEDIR);
	float e = degrees(asin(clamp(dir.y, -1.0, 1.0)));
	float az = degrees(atan(dir.x, -dir.z));
	vec2 frag = FRAGCOORD.xy;
	float th = p3d_bayer(frag);

	// Band bestimmen, im oberen Rand jedes Bandes zum nächsten dithern
	float limits[6] = {bands_deg.x, bands_deg.y, bands_deg.z, bands_deg.w, bands_deg2.x, bands_deg2.y};
	int idx = 6;
	for (int i = 0; i < 6; i++) {
		if (e < limits[i]) {
			idx = i;
			float t = clamp((e - (limits[i] - dither_deg)) / dither_deg, 0.0, 1.0);
			if (th < t * 0.5) {
				idx = i + 1;
			}
			break;
		}
	}
	vec3 col = band_color(idx);

	// Sterne: einzelne Pixel, nur oberhalb von 9°, ein Teil blinkt in Stufen
	vec2 cell = floor(frag) + p3d_pan;
	float h = hash12(cell);
	float star_vis = smoothstep(9.0, 16.0, e);
	if (h < 0.006 * star_vis) {
		float tw = step(0.5, fract(hash12(cell + 7.0) * 3.0 + p3d_time * 0.7));
		col = mix(col, star_color.rgb, 0.55 + 0.45 * tw);
	}

	// Wolkenbänke: flach gestreckt, 2,5°..12°, drei Töne (Unterseite angestrahlt)
	vec2 cp = vec2((az + p3d_time * cloud_drift) / 9.0, e / 1.15);
	float n = vnoise(cp) * 0.6 + vnoise(cp * vec2(2.3, 2.0) + 11.0) * 0.3 + vnoise(cp * 5.0 + 3.0) * 0.1;
	float layer = smoothstep(2.0, 4.0, e) * (1.0 - smoothstep(9.0, 12.5, e));
	float dens = n * layer;
	if (dens > 0.5) {
		// Unterkante: Dichte knapp darunter kleiner -> angestrahlter Rand
		vec2 below = cp - vec2(0.0, 0.55 / 1.15);
		float nb = (vnoise(below) * 0.6 + vnoise(below * vec2(2.3, 2.0) + 11.0) * 0.3
				+ vnoise(below * 5.0 + 3.0) * 0.1) * smoothstep(2.0, 4.0, e - 0.55)
				* (1.0 - smoothstep(9.0, 12.5, e - 0.55));
		vec3 cc = dens > 0.6 ? cloud_dark.rgb : cloud_mid.rgb;
		if (nb <= 0.5) {
			cc = cloud_lit.rgb;
		}
		col = cc;
	}
	COLOR = col;
}
