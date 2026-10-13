// Meer: Gerstner-Wellen im Vertex-Shader auf einem fein unterteilten Gitter (sea_mesh.gd).
// Wellenwerte kommen aus waves.gd (gleiche Formel rechnet das Skript für Boote und Treibgut).
// Zeit steckt in den Phasen, die das Skript je Bild setzt (aufsummiertes delta, doppelt genau, gefaltet),
// nicht TIME: Aufnahmen bleiben reproduzierbar und lange Laufzeiten ruckelfrei.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

const int MAX_WAVES = 8;
uniform vec4 wave_a[MAX_WAVES];      // d.x, d.y, A, Q
uniform vec4 wave_b[MAX_WAVES];      // k, omega, Phase (φ − ω·t) mod 2π aus waves.gd, -
uniform vec4 ripple[4];              // d.x, d.y, k, Phase (nur Normale)
uniform int wave_count = 0;
uniform float amp_sum = 0.3;
uniform vec2 fade_center = vec2(2.0, -12.0);
uniform float fade_inner = 42.0;
uniform float fade_outer = 66.0;

uniform vec3 deep_color : source_color = vec3(0.035, 0.11, 0.14);
uniform vec3 crest_color : source_color = vec3(0.10, 0.30, 0.32);
uniform vec3 foam_color : source_color = vec3(0.85, 0.86, 0.84);
uniform float roughness_water = 0.06;
uniform float foam_start = 0.09;     // ab dieser Stauchung (1 - Jacobi-Determinante) Schaum
uniform float foam_full = 0.22;
uniform float ripple_strength = 0.07;
uniform float ripple_fade = 70.0;    // m Kameraabstand

varying vec2 rest_xz;
varying float fade_v;

// Gerstner: Versatz und die beiden Ableitungen der verschobenen Fläche nach Ruhe-x und Ruhe-z.
void gerstner(vec2 p, float fade, out vec3 disp, out vec3 dpx, out vec3 dpz) {
	disp = vec3(0.0);
	dpx = vec3(1.0, 0.0, 0.0);
	dpz = vec3(0.0, 0.0, 1.0);
	for (int i = 0; i < MAX_WAVES; i++) {
		if (i >= wave_count) {
			break;
		}
		vec2 d = wave_a[i].xy;
		float A = wave_a[i].z * fade;
		float Q = wave_a[i].w;
		float k = wave_b[i].x;
		float th = k * dot(d, p) + wave_b[i].z;
		float s = sin(th);
		float c = cos(th);
		disp += vec3(Q * A * d.x * c, A * s, Q * A * d.y * c);
		dpx += vec3(-Q * A * k * d.x * d.x * s, A * k * d.x * c, -Q * A * k * d.x * d.y * s);
		dpz += vec3(-Q * A * k * d.x * d.y * s, A * k * d.y * c, -Q * A * k * d.y * d.y * s);
	}
}

float fade_at(vec2 p) {
	return 1.0 - smoothstep(fade_inner, fade_outer, length(p - fade_center));
}

// Kleine Kräuselung nur in der Normale (keine Geometrie), blendet mit dem Abstand aus.
vec2 ripples(vec2 p) {
	vec2 g = vec2(0.0);
	for (int i = 0; i < 4; i++) {
		float th = ripple[i].z * dot(ripple[i].xy, p) + ripple[i].w;
		g += ripple[i].xy * cos(th) * (0.6 + 0.2 * float(i));
	}
	return g;
}

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash(vec2 p) {
	p = fract(p * vec2(0.1031, 0.1030));
	p += dot(p, p.yx + 33.33);
	return fract((p.x + p.y) * p.x);
}

float vnoise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), f.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), f.x), f.y);
}

void vertex() {
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	rest_xz = wp.xz;
	fade_v = fade_at(wp.xz);
	vec3 disp, dpx, dpz;
	gerstner(wp.xz, fade_v, disp, dpx, dpz);
	VERTEX += disp;                       // Sea hat nur eine Verschiebung (keine Drehung, kein Maßstab)
	NORMAL = normalize(cross(dpz, dpx));
}

void fragment() {
	vec3 disp, dpx, dpz;
	gerstner(rest_xz, fade_v, disp, dpx, dpz);
	vec3 n = normalize(cross(dpz, dpx));
	float cam_d = length(CAMERA_POSITION_WORLD.xz - rest_xz);
	vec2 rg = ripples(rest_xz * 1.0) * ripple_strength * (1.0 - smoothstep(ripple_fade * 0.3, ripple_fade, cam_d));
	n = normalize(n + vec3(-rg.x, 0.0, -rg.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);

	// Stauchung der Fläche: 1 - det der waagrechten Ableitungen; > 0 an Kämmen, < 0 in Tälern
	float jac = dpx.x * dpz.z - dpx.z * dpz.x;
	float squeeze = 1.0 - jac;
	float streak = vnoise(rest_xz * vec2(2.2, 3.1) + vec2(ripple[0].w * 0.12, 0.0)) * 0.7 + vnoise(rest_xz * 7.0) * 0.3;
	float foam = smoothstep(foam_start, foam_full, squeeze + (streak - 0.5) * 0.14) * fade_v;
	foam *= smoothstep(0.35, 0.75, streak);
	float crest = clamp(disp.y / max(amp_sum, 0.001) * 0.5 + 0.5, 0.0, 1.0);
	vec3 col = mix(deep_color, crest_color, crest * crest * fade_v);
	ALBEDO = mix(col, foam_color, foam * 0.8);
	// Kräuselung, die das Gitter nicht mehr auflöst, als Rauheit (sonst spiegelt die ferne See wie Glas)
	float far_rough = mix(roughness_water, 0.45, smoothstep(25.0, 160.0, cam_d));
	ROUGHNESS = mix(far_rough, 0.7, foam);
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
