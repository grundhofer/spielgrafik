// Rauch aus Watte, wie im Modellbau: Billboard mit flauschigem Rand aus Rauschen und einer einfachen
// Kugelbeleuchtung (Sonne von links, violetter Schatten). depth_prepass_alpha schreibt die dichten Teile in
// den Tiefenpuffer, damit die Tiefenunschärfe die Watte am Schornstein einordnet.
shader_type spatial;
render_mode blend_mix, depth_prepass_alpha, cull_disabled, unshaded, fog_disabled;

#include "res://shaders/dio_noise.gdshaderinc"

uniform vec4 lit : source_color = vec4(1.0, 0.93, 0.85, 1.0);
uniform vec4 shade : source_color = vec4(0.52, 0.48, 0.62, 1.0);
uniform vec3 sun_view = vec3(-0.7, 0.5, 0.3);   // Lichtrichtung im Kameraraum (main.gd setzt sie)
instance uniform float seed = 0.0;
instance uniform float fade = 1.0;

void vertex() {
	// Billboard zur Kamera, Größe aus der Skalierung der Instanz
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(vec4(length(MODEL_MATRIX[0].xyz), 0, 0, 0), vec4(0, length(MODEL_MATRIX[1].xyz), 0, 0),
		vec4(0, 0, length(MODEL_MATRIX[2].xyz), 0), vec4(0, 0, 0, 1));
}

void fragment() {
	vec2 q = UV * 2.0 - 1.0;
	float r = length(q);
	vec3 p = vec3(q * 1.6, seed * 7.3);
	float n = dio_fbm(p * 1.4);
	float fib = dio_vnoise(vec3(q.x * 9.0, q.y * 2.5, seed * 3.1)) * 0.5 + dio_vnoise(vec3(q.y * 8.0, q.x * 3.0, seed)) * 0.5;
	float body = 1.0 - r + (n - 0.5) * 0.9 + (fib - 0.5) * 0.35;
	float a = smoothstep(0.08, 0.32, body);
	// Kugelnormale für die Beleuchtung
	vec3 nrm = normalize(vec3(q, sqrt(max(1.0 - r * r, 0.0)) + 0.3));
	float l = clamp(dot(nrm, normalize(sun_view)) * 0.5 + 0.55 + (n - 0.5) * 0.4, 0.0, 1.0);
	ALBEDO = mix(shade.rgb, lit.rgb, l) * (0.92 + 0.12 * fib);
	ALPHA = a * fade;
}
