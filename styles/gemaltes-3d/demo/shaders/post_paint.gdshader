// Nachbearbeitung 4 (Endbild): aus der Kuwahara-Fassung wird ein Bild auf Papier.
//  1. Zittern: Farbflächen um ein langsames Rauschfeld versetzt (unruhige, handgemalte Ränder)
//  2. Randabdunklung: wo die Farbe von ihrer weichen Umgebung abweicht, sammelt sich Pigment
//     (Aquarellränder; Formel nach Montesdeoca u. a. 2017: Farbe hoch (1 + Stärke · Abweichung))
//  3. Pinselstriche aus der LIC-Fassung: Helligkeit und Relief (Farbe auf den Borstenrillen)
//  4. Pigmentdichte: großflächig dichter und dünner aufgetragene Stellen
//  5. Papier: Körnung als Relief (Licht von links oben) und Granulation (Pigment sammelt sich in
//     den Tälern), dazu ein Rand, an dem das unbemalte Papier durchscheint
// Das Papier liegt fest im Bild wie ein echtes Blatt; alles andere hängt an der Szene.
shader_type canvas_item;

#include "res://shaders/paint_common.gdshaderinc"

global uniform float paint_time;

uniform sampler2D kuw : filter_linear, repeat_disable;    // Kuwahara-Fassung
uniform sampler2D kblur : filter_linear, repeat_disable;  // davon weichgezeichnet
uniform sampler2D lic : filter_nearest, repeat_disable;   // Strichwert
uniform sampler2D ctrl : filter_nearest, repeat_disable;  // Steuerkarte

uniform vec3 paper_color : source_color = vec3(0.95, 0.92, 0.85);
// Sterne: nach dem Filter als Tupfer gesetzt (der Kuwahara-Filter würde sie löschen), am Himmel
// festgemacht über die Blickrichtung je Pixel (Kamera aus main.gd)
uniform mat3 cam_basis = mat3(1.0);
uniform float tan_half_fov = 0.4245;
uniform float stars = 1.0;
uniform float sky_edge = 0.35;          // Kantenstärke am Himmel (dort trägt Steuerwert B die Wolkendeckung)
uniform float wobble_px = 1.6;          // Versatz der Ränder in Pixeln
uniform float wobble_scale = 26.0;      // Größe der Wellen in Pixeln
uniform float edge_strength = 2.2;      // Randabdunklung
uniform float edge_gain = 3.0;
uniform float stroke_tone = 0.10;       // Strichwert -> Helligkeit
uniform float stroke_relief = 0.07;     // Strichwert -> Relieflicht
uniform float stroke_hue = 0.05;        // Strichwert -> wärmer/kühler (benachbarte Striche verschieden gemischt)
uniform float stroke_fine = 0.4;        // Anteil der Striche bei feinem Pinsel (Figur), 1 bei grobem
uniform float stroke_sky = 0.5;         // Anteil der Striche am Himmel
uniform float turbulence = 0.18;        // Pigmentdichte großflächig
uniform float turb_scale = 160.0;
uniform float paper_relief = 0.06;
uniform float granulation = 0.16;
uniform float border = 1.0;             // 1 = Papierrand an den Bildkanten
uniform float border_px = 22.0;
uniform float paper_tint = 0.10;        // Anteil Papierfarbe im ganzen Bild (Lasur)
uniform float gain = 1.0;               // gleicht die Abdunklung durch Ränder, Papier und Granulation aus
uniform float wash = 0.0;               // Aquarell: lasierend aufhellen (Farbe als Filter über dem Papier)
uniform float wash_sat = 1.0;           // Sättigung danach

vec3 paper_h(vec2 x) {
	// Höhe und Gradient der Papierkörnung (kalt gepresstes Aquarellpapier, grob und fein)
	float e = 1.0;
	float h0 = 0.62 * fbm2(x / 5.5) + 0.38 * vnoise2(x / 1.7 + 13.0);
	float hx = 0.62 * fbm2((x + vec2(e, 0.0)) / 5.5) + 0.38 * vnoise2((x + vec2(e, 0.0)) / 1.7 + 13.0);
	float hy = 0.62 * fbm2((x + vec2(0.0, e)) / 5.5) + 0.38 * vnoise2((x + vec2(0.0, e)) / 1.7 + 13.0);
	return vec3(h0, hx - h0, hy - h0);
}

// Sternfeld: Zellen von etwa 1,1° in Azimut und Höhe, wenige Zellen mit einem Stern
vec3 star_layer(vec3 d, float px_per_rad, float time) {
	float el = asin(clamp(d.y, -1.0, 1.0));
	float az = atan(d.x, -d.z);
	float cell = 0.019;
	vec2 g = vec2(az, el) / cell;
	vec2 gi = floor(g);
	vec3 acc = vec3(0.0);
	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec2 c = gi + vec2(float(i), float(j));
			float h = hash12(c + 71.0);
			if (h > 0.94) {
				vec2 sp = (c + vec2(hash12(c + 3.1), hash12(c + 8.7))) * cell;
				vec2 dd = (vec2(az, el) - sp) * vec2(cos(el), 1.0) * px_per_rad;
				float r = 1.5 + 1.4 * hash12(c + 5.5);
				float tw = 0.75 + 0.25 * sin(time * (1.5 + 2.0 * hash12(c + 1.9)) + h * 40.0);
				float a = (1.0 - smoothstep(r * 0.4, r, length(dd * vec2(1.0, 1.35)))) * tw;
				float fade = smoothstep(0.12, 0.30, sp.y);
				acc = max(acc, vec3(1.0, 0.95, 0.82) * a * fade * (0.6 + 0.4 * hash12(c + 2.2)));
			}
		}
	}
	return acc;
}

float lum(vec3 c) {
	return dot(c, vec3(0.299, 0.587, 0.114));
}

void fragment() {
	vec2 sz = vec2(textureSize(kuw, 0));
	vec2 x = UV * sz;                         // Pixel, y nach unten
	ivec2 ip = ivec2(x);

	// 1. Zittern
	vec2 wob = vec2(vnoise2(x / wobble_scale), vnoise2(x / wobble_scale + vec2(31.7, 11.3))) - 0.5;
	vec2 uv = (x + wob * 2.0 * wobble_px) / sz;
	vec3 c = texture(kuw, uv).rgb;
	vec3 cb = texture(kblur, uv).rgb;
	vec4 cs = texelFetch(ctrl, ip, 0);

	// Aquarell: Lasur statt Deckfarbe; dunkle Stellen bleiben dunkel, helle lassen das Papier durch
	if (wash > 0.0) {
		vec3 wc = paper_color * pow(max(c, vec3(1e-4)), vec3(1.0 - 0.45 * wash));
		wc = mix(vec3(lum(wc)), wc, wash_sat);
		c = mix(c, wc, wash);
		vec3 wb = paper_color * pow(max(cb, vec3(1e-4)), vec3(1.0 - 0.45 * wash));
		cb = mix(cb, mix(vec3(lum(wb)), wb, wash_sat), wash);
	}

	// 2. Randabdunklung
	float dev = clamp((abs(cb.r - c.r) + abs(cb.g - c.g) + abs(cb.b - c.b)) * edge_gain, 0.0, 1.0);
	bool is_sky = cs.r > 0.99;
	c = pow(max(c, vec3(1e-4)), vec3(1.0 + edge_strength * dev * (is_sky ? sky_edge : cs.b)));

	// 3. Pinselstriche
	float s = texelFetch(lic, ip, 0).r;
	float sx = texelFetch(lic, min(ip + ivec2(1, 0), ivec2(sz) - 1), 0).r;
	float sy = texelFetch(lic, min(ip + ivec2(0, 1), ivec2(sz) - 1), 0).r;
	float relief_s = (sx - s) + (sy - s);      // Licht von links oben: Kanten, die nach oben links zeigen
	float amt = cs.r > 0.99 ? stroke_sky : mix(stroke_fine, 1.0, cs.r);
	c *= 1.0 + amt * stroke_tone * (s - 0.5) * 2.0;
	c += amt * stroke_hue * (s - 0.5) * 2.0 * vec3(0.8, 0.15, -0.6) * (0.3 + lum(c));
	c += amt * stroke_relief * relief_s * (0.4 + 0.6 * lum(c));

	// Sterne nur am Himmel (Steuerwert R = 1)
	if (stars > 0.0 && is_sky) {
		vec2 ndc = vec2(UV.x * 2.0 - 1.0, 1.0 - UV.y * 2.0);
		vec3 dv = normalize(vec3(ndc.x * tan_half_fov * sz.x / sz.y, ndc.y * tan_half_fov, -1.0));
		vec3 dw = normalize(cam_basis * dv);
		vec3 st = star_layer(dw, (sz.y * 0.5) / tan_half_fov, paint_time);
		float clear = 1.0 - smoothstep(0.05, 0.4, cs.b);
		c = mix(c, st / max(max(st.r, st.g), 1e-4), clamp(max(st.r, st.g) * 0.9 * clear, 0.0, 1.0));
	}

	// 4. Pigmentdichte
	float tb = fbm2(x / turb_scale + vec2(5.0, 9.0)) - 0.5;
	c = pow(max(c, vec3(1e-4)), vec3(1.0 + turbulence * tb * 2.0));

	// 5. Papier
	vec3 ph = paper_h(x);
	float shade = -(ph.y + ph.z) * 0.7071;
	float pig = 1.0 - lum(c);                 // wie viel Pigment hier liegt
	c *= 1.0 - granulation * (1.0 - ph.x) * pig;
	c = mix(c, c * paper_color, paper_tint);
	c *= 1.0 + paper_relief * shade * 12.0;
	c *= gain;

	if (border > 0.0) {
		vec2 dpx = min(x, sz - x);
		float dmin = min(dpx.x, dpx.y);
		float rag = (fbm2(x / 9.0 + vec2(2.0, 7.0)) - 0.5) * 14.0 + (vnoise2(x / 2.5) - 0.5) * 4.0;
		float paint = smoothstep(border_px - 3.0, border_px + 3.0, dmin + rag);
		vec3 paper = paper_color * (1.0 + paper_relief * shade * 10.0);
		// am Rand dunkelt das auslaufende Pigment nach (Wasserrand)
		float rim = smoothstep(border_px - 2.0, border_px + 2.0, dmin + rag) * (1.0 - smoothstep(border_px + 2.0, border_px + 9.0, dmin + rag));
		c = pow(max(c, vec3(1e-4)), vec3(1.0 + 0.6 * rim));
		c = mix(paper, c, paint * border + (1.0 - border));
	}
	COLOR = vec4(clamp(c, 0.0, 1.0), 1.0);
}
