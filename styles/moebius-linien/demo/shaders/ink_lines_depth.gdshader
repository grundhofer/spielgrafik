// Ersatz für Mobile und Compatibility (kein Normalen-/Rauheitspuffer): nur Silhouetten aus der Tiefe,
// dazu Papierkorn. Knick- und Farbgrenzlinien fehlen hier.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/ink_lines_common.gdshaderinc"

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

void fragment() {
	vec2 px = 1.0 / VIEWPORT_SIZE;
	vec2 uv = snap_uv(wobble_uv(SCREEN_UV, px, FRAGCOORD.xy), VIEWPORT_SIZE);
	float zc = lin_z(uv, INV_PROJECTION_MATRIX);
	float sky = step(2900.0, zc);   // Kamera far = 3000 m; unabhängig von der Tiefenrichtung des Renderers
	float e = silhouette(uv, VIEWPORT_SIZE, zc, INV_PROJECTION_MATRIX, min_gap);
	vec4 c = compose(SCREEN_UV, FRAGCOORD.xy, e, zc, sky);
	ALBEDO = c.rgb;
	ALPHA = 1.0;
}
