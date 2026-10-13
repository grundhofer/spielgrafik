// Meer im N64-Look: zwei gegeneinander wandernde Lagen derselben 32er-Wassertextur (3-Punkt-Filter),
// Dünung als Verschiebung der Gitterpunkte, Licht, Spiegelung des Abendhimmels (Fresnel) und Nebel je
// Eckpunkt. Zeit aus n64_time (aufsummiertes delta).
shader_type spatial;
render_mode unshaded, cull_back, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest_mipmap, repeat_enable;
uniform float tile_m = 3.0;
uniform vec2 flow_a = vec2(0.035, 0.09);      // Kacheln je Sekunde
uniform vec2 flow_b = vec2(-0.07, 0.03);
uniform float swell_height = 0.06;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;
uniform vec4 sheen : source_color = vec4(0.95, 0.6, 0.45, 1.0);
uniform float sheen_strength = 0.55;
uniform float light_boost = 1.0;

varying vec3 v_light;
varying vec3 v_add;
varying float v_fog;
varying vec3 v_wp;

vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	vec2 d = normalize(dir);
	float ph = k * (dot(d, p) - speed * n64_time);
	return vec3(amp * sin(ph), amp * k * cos(ph) * d);
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 9.0, 1.0, 1.3)
		+ wave(p, vec2(-0.6, 1.0), 14.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 5.5, 0.4, 1.0);
}

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(wp.xz - harbor_center));
	vec3 s = swell(wp.xz) * swell_height * fade;
	VERTEX.y += s.x;
	wp.y += s.x;
	vec3 n = normalize(vec3(-s.y * 4.0, 1.0, -s.z * 4.0));
	vec3 l = n64_hemi(n) + n64_sun_color.rgb * n64_sun_energy * 0.4 * max(dot(n, -n64_sun_dir), 0.0)
		+ n64_lantern(wp, n) * 2.0;
	v_light = l * light_boost;
	vec3 cam = (INV_VIEW_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	vec3 v = normalize(wp - cam);
	float fres = pow(1.0 - max(dot(-v, n), 0.0), 3.0);
	v_add = sheen.rgb * sheen_strength * fres;
	float depth = -(VIEW_MATRIX * vec4(wp, 1.0)).z;
	v_fog = n64_fog(depth);
	v_wp = wp;
}

void fragment() {
	vec2 uv = v_wp.xz / tile_m;
	vec3 a = n64_tex(tex, uv + flow_a * n64_time).rgb;
	vec3 b = n64_tex(tex, uv * 1.37 + vec2(0.31, 0.17) + flow_b * n64_time).rgb;
	vec3 c = (a + b) * 0.5 * v_light + v_add;
	ALBEDO = mix(c, n64_fog_color.rgb, v_fog);
}
