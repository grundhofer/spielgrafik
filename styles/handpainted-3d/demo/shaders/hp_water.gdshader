// Gemaltes Wasser für das Mesh "Sea" (Eintrag handpainted-3d).
// Durchsichtig gerendert (ALPHA = 1), damit der Tiefenpuffer der deckenden Geometrie lesbar ist:
//  - Farbe nach Wassertiefe entlang des Sehstrahls: Türkis am Ufer, Blauviolett in der Tiefe
//  - Spiegelung des gemalten Himmels (gleiche Abbildung wie der Himmel), stärker in der Ferne
//  - gemalte Wellenstriche: gestreckte, treibende Rauschbänder in hellem Flieder und Abendorange
//  - Schaumkante, wo das Wasser Kai, Pfähle, Boote und Felsen berührt, mit wanderndem zweitem Ring
//  - Dünung als Verschiebung (wie shared/3d), Zeit als Uniform aus dem Skript
shader_type spatial;
render_mode blend_mix, depth_draw_never, cull_back, unshaded, shadows_disabled, fog_disabled;

#include "res://shaders/hp_sky_map.gdshaderinc"

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform float time_s = 0.0;
uniform vec3 shallow : source_color = vec3(0.26, 0.62, 0.70);
uniform vec3 mid : source_color = vec3(0.13, 0.46, 0.64);
uniform vec3 deep : source_color = vec3(0.12, 0.27, 0.52);
uniform vec3 stroke_light : source_color = vec3(0.78, 0.80, 0.98);
uniform vec3 stroke_warm : source_color = vec3(1.0, 0.70, 0.46);
uniform vec3 foam_color : source_color = vec3(0.98, 0.94, 0.86);
uniform float shallow_depth = 0.9;
uniform float foam_width = 0.3;
uniform float swell_height = 0.05;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform vec3 fog_color : source_color = vec3(0.93, 0.62, 0.58);
uniform float fog_begin = 90.0;
uniform float fog_end = 520.0;

varying vec3 world_pos;

float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	float a = hash(i), b = hash(i + vec2(1.0, 0.0)), c = hash(i + vec2(0.0, 1.0)), d = hash(i + vec2(1.0, 1.0));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

float fbm(vec2 p) {
	return 0.55 * vnoise(p) + 0.3 * vnoise(p * 2.03 + 7.1) + 0.15 * vnoise(p * 4.1 - 3.7);
}

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	float ph = k * (dot(normalize(dir), p) - speed * time_s);
	return vec3(amp * sin(ph), amp * k * cos(ph) * normalize(dir));
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 11.0, 1.0, 1.3) + wave(p, vec2(-0.6, 1.0), 17.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 7.0, 0.35, 1.0);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
}

void fragment() {
	vec3 cam = CAMERA_POSITION_WORLD;
	float dist = length(world_pos - cam);
	vec3 v_world = normalize(cam - world_pos);

	// Wassertiefe entlang des Sehstrahls bis zur deckenden Geometrie dahinter
	float dz = texture(depth_tex, SCREEN_UV).r;
	vec4 sv = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, dz, 1.0);
	sv.xyz /= sv.w;
	float thick = length(sv.xyz) - length(VERTEX);
	if (dz <= 0.0000001) {
		thick = 1000.0;
	}

	// Grundfarbe: Ufer türkis, dann Mittelblau, in der Tiefe Blauviolett (weiche, gemalte Übergänge)
	float wob = fbm(world_pos.xz * 0.35 + vec2(0.05, 0.08) * time_s);
	float s1 = 1.0 - smoothstep(0.0, shallow_depth * (0.8 + 0.4 * wob), thick);
	float s2 = 1.0 - smoothstep(shallow_depth, shallow_depth * 4.0, thick);
	vec3 col = mix(deep, mid, s2);
	col = mix(col, shallow, s1);
	// großflächige Farbflecken wie gemalt
	col *= 0.92 + 0.16 * fbm(world_pos.xz * 0.08 + vec2(3.0, 1.0));

	// Spiegelung des gemalten Himmels, in der Ferne stärker
	float ndv = clamp(v_world.y, 0.0, 1.0);
	float fr = 0.18 + 0.82 * pow(1.0 - ndv, 5.0);
	vec2 g = swell(world_pos.xz).yz * swell_height;
	vec3 n = normalize(vec3(-g.x, 1.0, -g.y) + vec3(0.04 * (fbm(world_pos.xz * 1.3 + time_s * 0.3) - 0.5), 0.0, 0.0));
	vec3 r = reflect(-v_world, n);
	r.y = abs(r.y);
	vec3 refl = sky_color(r) * vec3(0.78, 0.86, 1.0);   // Spiegelung leicht ins Wasserblau gezogen
	col = mix(col, refl, fr * 0.5);

	// gemalte Wellenstriche: quer gestreckte, treibende Bänder; in Kameranähe größer
	vec2 sp = world_pos.xz * vec2(0.55, 2.2) + vec2(0.18 * time_s, 0.05 * time_s);
	sp.y += 0.6 * sin(world_pos.x * 0.35 + time_s * 0.5);
	float band = fbm(sp);
	float strokes = smoothstep(0.62, 0.70, band) * (1.0 - smoothstep(0.78, 0.86, band));
	float brk = smoothstep(0.45, 0.6, vnoise(world_pos.xz * vec2(0.4, 1.1) - vec2(0.1, 0.03) * time_s));
	float near = 1.0 - smoothstep(30.0, 90.0, dist);
	strokes *= brk * near;
	// warme Striche in Richtung der Abendglut (links hinten), sonst Flieder
	float warm = smoothstep(-0.2, 0.6, dot(normalize(-v_world.xz), normalize(vec2(-0.6, -1.0))));
	col = mix(col, mix(stroke_light, stroke_warm, warm), strokes * 0.75);

	// Schaumkante an Kai, Pfählen, Booten, Felsen (Breite schwankt), dazu ein wandernder zweiter Ring
	float fw = foam_width * (0.7 + 0.6 * vnoise(world_pos.xz * 2.5 + time_s * 0.4));
	float foam = 1.0 - smoothstep(fw * 0.75, fw, thick);
	float ring_pos = fract(time_s / 2.6);
	float ring_d = foam_width * (1.2 + 2.2 * ring_pos);
	float ring = (1.0 - smoothstep(0.0, 0.07, abs(thick - ring_d))) * (1.0 - ring_pos) * 0.8;
	ring *= smoothstep(0.35, 0.55, vnoise(world_pos.xz * 3.0 + 11.0));
	foam = max(foam, ring);
	col = mix(col, foam_color, foam * near * 0.9);

	// eigener Nebel (fog_disabled), damit die Meereskante am Horizont in der Himmelsfarbe verschwindet
	float fogk = smoothstep(fog_begin, fog_end, dist);
	vec3 horizon = sky_color(normalize(vec3(-v_world.x, 0.002, -v_world.z)));
	col = mix(col, horizon, fogk);

	ALBEDO = col;
	ALPHA = 1.0;
}
