// Wasser als Farbvorlage für die Nachbearbeitung (Ersatz für das glTF-Material "Water" am Mesh "Sea").
// Unbeleuchtet: Grundfarbe in der Tiefe, gespiegelter Himmel (sky_common.gdshaderinc) nach Fresnel,
// Glitzerbahnen der Lichter (Laterne, Leuchtfeuer, Fenster) aus gekräuselten Normalen. Die
// Kräuselung ist in die Breite gezogen; der Kuwahara-Filter macht daraus waagrechte Pinselstriche.
// Dünung als Verschiebung wie shared/3d (Wellen in Weltkoordinaten, außerhalb des Hafens aus).
// Zeit kommt als globale Uniform paint_time aus main.gd (aufsummiertes delta).
shader_type spatial;
render_mode unshaded, cull_back, depth_draw_opaque;

#include "res://shaders/paint_common.gdshaderinc"
#include "res://shaders/sky_common.gdshaderinc"

uniform vec3 deep_color : source_color = vec3(0.10, 0.17, 0.26);
uniform vec3 near_color : source_color = vec3(0.14, 0.27, 0.32);
uniform float swell_height = 0.05;
uniform float ripple_strength = 0.16;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform float reflect_gain = 0.9;
// Lichter: xyz Position, w Stärke
uniform vec4 light_a = vec4(4.1, 1.79, -0.12, 1.0);     // Laterne
uniform vec4 light_b = vec4(10.2, 12.58, -25.6, 1.0);   // Leuchtfeuer
uniform vec4 light_c = vec4(-9.2, 1.45, 0.52, 1.0);     // Fenster
uniform vec3 light_color : source_color = vec3(1.0, 0.78, 0.45);
uniform float ctrl_size = 0.62;
uniform float ctrl_edge = 0.35;

varying vec3 world_pos;
varying float is_ctrl;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	float ph = k * (dot(normalize(dir), p) - speed * paint_time);
	return vec3(amp * sin(ph), amp * k * cos(ph) * normalize(dir));
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 11.0, 1.0, 1.3)
		+ wave(p, vec2(-0.6, 1.0), 17.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 7.0, 0.35, 1.0);
}

// Kräuselung: Rauschen, in x gestreckt (waagrechte Wellenkämme), treibt langsam
vec2 ripples(vec2 p) {
	vec2 q = p * vec2(0.55, 2.2) + vec2(paint_time * 0.25, paint_time * 0.6);
	float e = 0.05;
	float a = fbm2(q);
	float bx = fbm2(q + vec2(e, 0.0));
	float bz = fbm2(q + vec2(0.0, e));
	vec2 g = vec2(bx - a, bz - a) / e;
	return g * vec2(0.55, 2.2) * 0.25;
}

void vertex() {
	is_ctrl = (CAMERA_VISIBLE_LAYERS & CTRL_LAYER_BIT) != 0u ? 1.0 : 0.0;
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
}

float glitter(vec3 r, vec4 l) {
	vec3 to_l = normalize(l.xyz - world_pos);
	float c = max(dot(r, to_l), 0.0);
	return l.w * (pow(c, 300.0) * 1.6 + pow(c, 40.0) * 0.12);
}

void fragment() {
	vec3 cam = CAMERA_POSITION_WORLD;
	float dist = length(world_pos - cam);
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec2 g = swell(world_pos.xz).yz * swell_height * fade;
	// Kräuselung blendet in der Ferne aus (sonst Flimmern)
	g += ripples(world_pos.xz) * ripple_strength * (1.0 - smoothstep(25.0, 120.0, dist));
	vec3 n = normalize(vec3(-g.x, 1.0, -g.y));
	vec3 v = normalize(cam - world_pos);
	vec3 r = reflect(-v, n);
	r.y = max(r.y, 0.004);
	vec3 refl = sky_color(normalize(r));
	float fres = 0.04 + 0.96 * pow(1.0 - clamp(dot(n, v), 0.0, 1.0), 5.0);
	vec3 base = mix(near_color, deep_color, smoothstep(6.0, 40.0, dist));
	vec3 col = mix(base, refl * reflect_gain, clamp(fres * 1.15, 0.0, 1.0));
	vec3 rr = normalize(r);
	col += light_color * (glitter(rr, light_a) + glitter(rr, light_b) * 0.8 + glitter(rr, light_c) * 0.7);

	float sn = stroke_noise2(world_pos.xz * vec2(1.0, 2.5), 2.4, 6.0, 0.6);
	ALBEDO = mix(col, vec3(ctrl_size, sn, ctrl_edge), is_ctrl);
}
