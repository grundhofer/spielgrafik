// Lichtkegel des Leuchtfeuers, weich gemalt: additiver, unbeleuchteter Kegel ohne Deckel.
// Das Mesh ist ein CylinderMesh, um -90° um X gedreht: lokales +Y zeigt vom Licht weg.
// cull_back: sonst addieren sich Vorder- und Rückwand zu hellen Ellipsen (Lehre aus toon-cel).
shader_type spatial;
render_mode blend_add, unshaded, cull_back, depth_draw_never, fog_disabled, shadows_disabled;

uniform vec3 color : source_color = vec3(1.0, 0.88, 0.62);
uniform float intensity = 0.35;
uniform float length_m = 34.0;

varying float along;

void vertex() {
	along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
}

void fragment() {
	float side = clamp(abs(dot(normalize(NORMAL), VIEW)), 0.0, 1.0);
	float body = smoothstep(0.0, 0.9, side);
	float fall = pow(clamp(1.0 - along, 0.0, 1.0), 1.3);
	float start = smoothstep(0.0, 0.04, along);
	ALBEDO = color * intensity * body * fall * start;
}
