// Lichtkegel des Leuchtfeuers als additives Halbtransparenz-Polygon (Mischmodus "B+F" der Konsole):
// Helligkeit nur je Eckpunkt (hell an der Lampe, schwarz am Ende), Gouraud dazwischen, Eckpunkte gerundet.
// Mesh: CylinderMesh mit 8 Segmenten, um -90° um X gedreht: lokales +Y zeigt vom Licht weg.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

#include "res://shaders/ps1_common.gdshaderinc"

uniform vec4 color : source_color = vec4(1.0, 0.85, 0.55, 1.0);
uniform float intensity = 0.5;
uniform float length_m = 30.0;

varying vec3 v_col;
varying vec4 v_col_w;                    // rgb = v_col · w, a = w: im Fragment geteilt = linear im Bildraum

void vertex() {
	float along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);
	vec3 axis = normalize((MODELVIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	vec4 view = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	vec3 v = normalize(-view.xyz);
	// von vorn gesehen leuchtet der ganze Kegel, seitlich vor allem die Lampennähe
	float facing = pow(abs(dot(axis, v)), 3.0);
	float fall = pow(clamp(1.0 - along, 0.0, 1.0), 1.5);
	v_col = color.rgb * intensity * fall * mix(0.55, 1.6, facing) * (1.0 - ps1_fog(-view.z));
	vec4 clip = ps1_snap(PROJECTION_MATRIX * view);
	POSITION = clip;
	v_col_w = vec4(v_col * clip.w, clip.w);
}

void fragment() {
	ALBEDO = mix(v_col, v_col_w.rgb / v_col_w.a, ps1_affine_vc);
}
