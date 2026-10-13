// Lichtkegel des Leuchtturms im Toon-Stil: flache, durchscheinende Fläche mit harten Kanten,
// zweistufig (heller Kern, wo die Wand zur Kamera zeigt, schwächerer Saum), läuft am Ende weich aus.
// Mesh: CylinderMesh ohne Deckel, um -90° um X gedreht (lokales +Y zeigt vom Licht weg).
// Nur Vorderseiten (cull_back): Vorder- und Rückwand addiert ergäben helle Ellipsen.
shader_type spatial;
render_mode blend_add, unshaded, cull_back, depth_draw_never, fog_disabled, shadows_disabled;

uniform vec4 color : source_color = vec4(1.0, 0.86, 0.52, 1.0);
uniform float intensity = 0.42;
uniform float length_m = 26.0;

varying float along;
varying vec3 axis_view;

void vertex() {
	along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
	axis_view = normalize((MODELVIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
}

void fragment() {
	float side = abs(dot(normalize(NORMAL), VIEW));
	float facing = abs(dot(normalize(axis_view), VIEW));
	float core = smoothstep(0.7, 0.73, max(side, facing));
	float a = clamp(along, 0.0, 1.0);
	float fall = 1.0 - smoothstep(0.45, 1.0, a);
	ALBEDO = color.rgb * intensity * (0.5 + 0.5 * core) * fall;
}
