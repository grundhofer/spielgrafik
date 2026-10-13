// Lichthof (Laterne, Leuchtfeuer) als additives, zur Kamera gedrehtes Sprite (Mischmodus B + F).
// Textur 32×32 mit 6 Helligkeitsstufen statt Verlauf; Eckpunkte gerundet.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

#include "res://shaders/ps1_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest;
uniform vec4 tint : source_color = vec4(1.0, 0.8, 0.5, 1.0);
uniform float strength = 1.0;
uniform bool depth_test = true;

varying float v_fog;
varying flat float v_ot;                 // als Ganzes sortiert (Mittelpunkt)

void vertex() {
	vec3 center = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	float sx = length(MODEL_MATRIX[0].xyz);
	float sy = length(MODEL_MATRIX[1].xyz);
	vec4 view = VIEW_MATRIX * vec4(center, 1.0);
	view.xy += VERTEX.xy * vec2(sx, sy);
	v_fog = ps1_fog(-view.z);
	v_ot = -view.z;
	POSITION = ps1_snap(PROJECTION_MATRIX * view);
}

void fragment() {
	ALBEDO = texture(tex, UV).rgb * tint.rgb * strength * (1.0 - 0.7 * v_fog);
	DEPTH = ps1_ot > 0.5 ? ps1_ot_depth(v_ot, PROJECTION_MATRIX) : FRAGCOORD.z;
}
