// Konturen als Nachbearbeitung für Mobile und Compatibility: dort gibt es keinen Normalen-/Rauheits-
// puffer, deshalb nur Silhouetten aus der Tiefe (outline_common.gdshaderinc); Knicke und Farbgrenzen
// fehlen. main.gd wählt diesen Shader, wenn nicht mit Forward+ gerendert wird.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/outline_common.gdshaderinc"

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

void fragment() {
	float zc;
	vec3 wc;
	vec2 ox;
	vec2 oy;
	float sky;
	float e = silhouette(SCREEN_UV, VIEWPORT_SIZE, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX, zc, wc, ox, oy, sky);
	ALBEDO = line_color(SCREEN_UV);
	ALPHA = finish(e, zc, wc, sky);
}
