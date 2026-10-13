// Wasser für den 1-Bit-Look (Ersatz für das glTF-Material "Water" am Mesh "Sea").
// Dünung als Verschiebung und Kräuselung in der Normale wie in shared/3d (Weltkoordinaten), dazu:
// Das Wasser spiegelt den Himmel aus sky.gdshaderinc (Fresnel) und die drei Lampen als Glitzerstreifen.
// Alles als EMISSION: Die Nachbearbeitung macht daraus Punkte; das Kräuseln bricht die Spiegelung in
// waagerechte Streifen. ID 15 im Blaukanal: keine Knicklinien auf dem Wasser.
// Zeit als globale Uniform onebit_time (aufsummiertes delta, reproduzierbar).
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_back;

#include "res://shaders/sky.gdshaderinc"

global uniform float onebit_time;

uniform float value = 0.02;
uniform float reflect_strength = 0.4;
uniform float swell_height = 0.05;
uniform float ripple_strength = 0.16;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform float ripple_fade = 120.0;
uniform vec4 glint_pos[3];          // xyz Lampe, w Stärke
uniform float glint_sharpness = 260.0;

varying vec3 world_pos;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	float ph = k * (dot(normalize(dir), p) - speed * onebit_time);
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
		+ wave(p, vec2(-0.4, -1.0), 3.1, 0.07, 1.1)
		+ wave(p, vec2(0.05, 1.0), 0.8, 0.02, 0.7);
	return r.yz;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
	NORMAL = normalize(vec3(-s.y, 1.0, -s.z));
}

void fragment() {
	float d = length(world_pos - CAMERA_POSITION_WORLD);
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec2 g = swell(world_pos.xz).yz * swell_height * fade;
	g += ripples(world_pos.xz) * ripple_strength * (1.0 - smoothstep(ripple_fade * 0.3, ripple_fade, d));
	vec3 n = normalize(vec3(-g.x, 1.0, -g.y));
	vec3 v = normalize(CAMERA_POSITION_WORLD - world_pos);
	vec3 r = reflect(-v, n);
	r.y = abs(r.y);
	float fres = 0.03 + 0.97 * pow(clamp(1.0 - dot(n, v), 0.0, 1.0), 5.0);
	float refl = sky_luminance(normalize(r), onebit_time) * fres * reflect_strength;
	float glint = 0.0;
	for (int i = 0; i < 3; i++) {
		vec3 l = normalize(glint_pos[i].xyz - world_pos);
		glint += glint_pos[i].w * pow(max(dot(r, l), 0.0), glint_sharpness);
	}
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);
	ALBEDO = vec3(value, 0.0, 0.0);
	EMISSION = vec3(refl + glint, 0.0, (15.0 + 0.5) / 16.0);   // Rot: Helligkeit, Blau: ID 15
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	METALLIC = 0.0;
}
