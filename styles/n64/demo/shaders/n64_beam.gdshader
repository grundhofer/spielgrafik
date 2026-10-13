// Sichtbarer Lichtkegel des Leuchtturms: additiver Kegel, Helligkeit je Eckpunkt (hell an der Lampe,
// dunkel am Ende), seitlich weich; Nebel dämpft ihn. Das Mesh ist ein CylinderMesh, um -90° um X gedreht.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, shadows_disabled, specular_disabled;

#include "res://shaders/n64_common.gdshaderinc"

uniform vec4 color : source_color = vec4(1.0, 0.82, 0.5, 1.0);
uniform float intensity = 0.3;
uniform float length_m = 18.0;

varying float v_fall;
varying vec3 v_axis;

void vertex() {
	float along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
	v_fall = pow(1.0 - along, 1.5);
	v_axis = normalize((MODELVIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	vec3 wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float depth = -(VIEW_MATRIX * vec4(wp, 1.0)).z;
	v_fall *= 1.0 - 0.5 * n64_fog(depth);
}

void fragment() {
	float side = abs(dot(normalize(NORMAL), VIEW));
	float body = mix(side * side, 1.0, pow(abs(dot(normalize(v_axis), VIEW)), 4.0));
	ALBEDO = color.rgb * intensity * body * clamp(v_fall, 0.0, 1.0);
}
