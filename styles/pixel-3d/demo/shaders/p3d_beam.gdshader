// Lichtkegel des Leuchtturms für Pixel-3D: additiv, unbeleuchtet, Helligkeit in harten Stufen mit
// gediterten Übergängen (Kern hell, Rand schwach, nach außen in drei Stufen auslaufend).
// Mesh: CylinderMesh, um -90° um X gedreht, lokales +Y zeigt vom Licht weg (wie shared/3d).
// cull_back: sonst addieren sich Vorder- und Rückwand zu hellen Ellipsen.
shader_type spatial;
render_mode blend_add, unshaded, cull_back, depth_draw_never, fog_disabled, shadows_disabled;

#include "res://shaders/p3d_common.gdshaderinc"

uniform vec4 color : source_color = vec4(1.0, 0.86, 0.6, 1.0);
uniform float intensity = 0.32;
uniform float length_m = 30.0;

varying float along;   // 0 an der Lampe, 1 am Ende
varying vec3 axis;

void vertex() {
	along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
	axis = normalize((MODELVIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
}

void fragment() {
	float side = abs(dot(normalize(NORMAL), VIEW));
	float body = mix(side * side, 1.0, pow(clamp(abs(dot(normalize(axis), VIEW)), 0.0, 1.0), 4.0));
	float fall = pow(clamp(1.0 - along, 0.0, 1.0), 1.3);
	float v = clamp(body * fall, 0.0, 1.0);
	float q = p3d_steps(v, 3.0, 0.45, FRAGCOORD.xy);
	ALBEDO = color.rgb * intensity * q;
}
