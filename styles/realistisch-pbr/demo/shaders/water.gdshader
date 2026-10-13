shader_type spatial;
// Wasser für Echtzeit-PBR: undurchsichtig, damit Godots Screen-Space-Reflections (SSR) und die
// Himmelsspiegelung aus der Radiance-Cubemap greifen (durchsichtige Materialien bekommen in Godot
// kein SSR). Fresnel und Glanz rechnet Godot über SPECULAR (Wasser F0 ≈ 0,02).
// Wellen: wenige Gerstner-Wellen in Weltkoordinaten (nur im Hafen, außen ausgeblendet, weil das
// Gitter dort grob ist) + zwei wandernde Normalenkarten (Rauschen, nahtlos) + feines Kräuseln.
// Zeit kommt als Uniform aus main.gd (aufsummiertes delta, reproduzierbar).
render_mode cull_back, depth_draw_opaque;

uniform float time_s = 0.0;
uniform vec3 deep_color : source_color = vec3(0.012, 0.03, 0.035);
uniform vec3 shallow_color : source_color = vec3(0.03, 0.06, 0.055);
uniform sampler2D wave_n1 : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D wave_n2 : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float n1_scale_m = 9.0;
uniform float n2_scale_m = 3.1;
uniform vec2 n1_vel = vec2(0.05, 0.11);
uniform vec2 n2_vel = vec2(-0.09, 0.05);
uniform float n_strength = 0.55;
uniform float roughness_near = 0.035;
uniform float roughness_far = 0.12;
uniform float swell_amp = 0.045;            // Meter
uniform float harbor_radius = 30.0;         // Wellen nur im Hafen (Gitter dort 1,5 m)

varying vec3 v_wpos;
varying float v_crest;

// Dünung: Summe weniger Sinuswellen (Tiefwasser-Dispersion c = sqrt(g/k)), Normale analytisch
float swell(vec2 xz, vec2 d, float L, float a, float t, inout vec2 grad) {
	float k = TAU / L;
	float c = sqrt(9.81 / k);
	d = normalize(d);
	float f = k * (dot(d, xz) - c * t);
	grad += a * k * cos(f) * d;
	return a * sin(f);
}

void vertex() {
	vec3 w = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(harbor_radius * 0.6, harbor_radius, length(w.xz - vec2(2.0, -12.0)));
	vec2 g = vec2(0.0);
	float h = 0.0;
	h += swell(w.xz, vec2(0.3, 1.0), 7.5, swell_amp, time_s, g);
	h += swell(w.xz, vec2(-0.6, 1.0), 4.3, swell_amp * 0.55, time_s * 1.03 + 1.7, g);
	h += swell(w.xz, vec2(0.9, 0.4), 2.6, swell_amp * 0.3, time_s * 0.97 + 4.1, g);
	VERTEX.y += h * fade;
	NORMAL = normalize(vec3(-g.x * fade, 1.0, -g.y * fade));
	v_crest = h / swell_amp * fade;
	v_wpos = w;
}

vec3 unpack_n(vec4 t) {
	vec2 xy = t.xy * 2.0 - 1.0;
	return vec3(xy, sqrt(max(1.0 - dot(xy, xy), 0.0)));
}

void fragment() {
	vec2 xz = v_wpos.xz;
	float dist = length(CAMERA_POSITION_WORLD - v_wpos);
	vec3 n1 = unpack_n(texture(wave_n1, xz / n1_scale_m + n1_vel * time_s));
	vec3 n2 = unpack_n(texture(wave_n2, xz / n2_scale_m + n2_vel * time_s));
	vec3 n3 = unpack_n(texture(wave_n2, xz / (n2_scale_m * 0.37) * mat2(vec2(0.8, -0.6), vec2(0.6, 0.8)) + vec2(0.13, -0.07) * time_s));
	// Feine Kräuselung blendet mit der Entfernung aus; dafür steigt die Rauheit (sonst flimmert es)
	float far = smoothstep(15.0, 120.0, dist);
	vec2 slope = n1.xy * 0.9 + n2.xy * 0.7 * (1.0 - far * 0.6) + n3.xy * 0.35 * (1.0 - far);
	slope *= n_strength;
	// Normalenkarte: Bild rechts = +x, Bild oben = -z (uv = xz)
	vec3 wn_geo = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	vec3 nw = normalize(wn_geo + vec3(slope.x, 0.0, -slope.y));
	float facing = clamp(dot(normalize(CAMERA_POSITION_WORLD - v_wpos), nw), 0.0, 1.0);
	ALBEDO = mix(deep_color, shallow_color, clamp(0.5 + 0.5 * v_crest, 0.0, 1.0) * 0.6);
	ROUGHNESS = mix(roughness_near, roughness_far, far);
	METALLIC = 0.0;
	SPECULAR = 0.25;
	NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
}
