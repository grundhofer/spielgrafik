// HD-2D-Wasser für das Mesh "Sea" (ersetzt das glTF-Material "Water").
// Dünung als Verschiebung (wie shared/3d), Kräuselung aber im Texelraster (global px_per_m, doppelt so grob):
// Die Normale ist je Wasser-Texel konstant, Spiegelungen (SSR) und Glanz zerfallen so in Pixelblöcke.
// Dazu Glitzerpixel (Hash je Texel und Takt) und ein wandernder Schaumsaum an der Kaimauer.
// Zeit als globale Uniform time_s (aufsummiertes delta), nicht TIME.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

global uniform float px_per_m;
global uniform float time_s;

uniform vec4 deep : source_color = vec4(0.05, 0.13, 0.19, 1.0);
uniform vec4 shallow : source_color = vec4(0.10, 0.24, 0.29, 1.0);
uniform vec4 foam : source_color = vec4(0.75, 0.82, 0.86, 1.0);
uniform vec3 glint : source_color = vec3(1.0, 0.78, 0.55);
uniform float swell_height = 0.05;
uniform float ripple_strength = 0.16;
uniform float texel_scale = 0.5;          // Wasser-Texel = 1 / (px_per_m * texel_scale) m
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform float glint_amount = 0.012;       // Anteil der Texel, die gerade glitzern
uniform float glint_energy = 3.0;

varying vec3 world_pos;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	float ph = k * (dot(normalize(dir), p) - speed * time_s);
	return vec3(amp * sin(ph), amp * k * cos(ph) * normalize(dir));
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 11.0, 1.0, 1.3)
		+ wave(p, vec2(-0.6, 1.0), 17.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 7.0, 0.35, 1.0);
}

vec2 ripples(vec2 p) {
	vec3 r = wave(p, vec2(0.2, 1.0), 2.3, 0.06, 0.9)
		+ wave(p, vec2(-0.8, 0.5), 1.7, 0.05, 0.8)
		+ wave(p, vec2(0.9, -0.3), 1.1, 0.03, 0.6)
		+ wave(p, vec2(-0.4, -1.0), 3.1, 0.07, 1.1);
	return r.yz;
}

float hash(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
}

void fragment() {
	float tex = px_per_m * texel_scale;
	vec2 cell = floor(world_pos.xz * tex);
	vec2 pc = (cell + 0.5) / tex;                      // Mitte des Wasser-Texels
	float d = length(world_pos - CAMERA_POSITION_WORLD);
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(pc - harbor_center));
	vec2 g = swell(pc).yz * swell_height * fade;
	float near = 1.0 - smoothstep(30.0, 90.0, d);
	g += ripples(pc) * ripple_strength * near;
	vec3 n_world = normalize(vec3(-g.x, 1.0, -g.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);
	// Farbe: im Hafen etwas heller (flacher), draußen tief; in zwei Stufen je Texel gerastert
	float sh = 1.0 - smoothstep(4.0, 30.0, length(pc - vec2(2.0, -4.0)));
	sh = floor(sh * 4.0 + hash(cell) * 0.6) / 4.0;
	vec3 col = mix(deep.rgb, shallow.rgb, sh);
	// Schaumsaum an der Kaimauer (Vorderkante z = -1,0 ab x = -5; Ecke x = -5 bis z = -3,6)
	float dw = 1e3;
	if (pc.x > -5.0 && pc.x < 8.1) dw = min(dw, abs(pc.y + 1.0));
	if (pc.y < -1.0 && pc.y > -3.6) dw = min(dw, abs(pc.x + 5.0));
	float band = 0.10 + 0.08 * (0.5 + 0.5 * sin(time_s * 1.7 + pc.x * 1.3 + pc.y));
	float f = step(dw, band) * step(0.35, hash(cell + floor(time_s * 4.0)));
	col = mix(col, foam.rgb, f * 0.85);
	ALBEDO = col;
	ROUGHNESS = mix(0.04, 0.6, f);
	METALLIC = 0.0;
	SPECULAR = 0.6;
	// Glitzern: einzelne Texel blitzen kurz auf, nur wo die Normale zum Licht im Westen/Horizont kippt
	float tick = floor(time_s * 8.0 + hash(cell) * 8.0);
	float gl = step(1.0 - glint_amount, hash(cell * 1.37 + tick)) * near;
	EMISSION = glint * gl * glint_energy * smoothstep(0.0, 0.12, length(g));
}
