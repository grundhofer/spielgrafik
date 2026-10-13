// Lichthof als Billboard mit zwei harten Ringen (additiv), z. B. um Laterne, Fenster und Leuchtfeuer.
// Größe kommt aus dem Mesh; `pulse` (0..1) vergrößert den inneren Ring (Flackern, Aufblitzen).
// Das Billboard wird um `toward_cam` m zur Kamera gezogen, damit es nicht im Glaskörper steckt;
// mit Tiefentest, damit es nicht über die Figur zeichnet.
// Der äußere Ring ist ein 50-%-Schachbrett (ortsfest zum Bildinhalt), wie gepixelte Lichthöfe.
shader_type spatial;
render_mode blend_add, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

#include "res://shaders/p3d_common.gdshaderinc"

uniform vec4 color : source_color = vec4(1.0, 0.78, 0.42, 1.0);
uniform float inner = 0.42;
uniform float outer = 1.0;
uniform float inner_gain = 0.38;
uniform float outer_gain = 0.16;
uniform float pulse = 0.0;
uniform float toward_cam = 0.4;

void vertex() {
	vec3 c = (VIEW_MATRIX * vec4(MODEL_MATRIX[3].xyz, 1.0)).xyz;
	c -= normalize(c) * toward_cam;
	float s = length(MODEL_MATRIX[0].xyz);
	POSITION = PROJECTION_MATRIX * vec4(c + vec3(VERTEX.xy * s, 0.0), 1.0);
}

void fragment() {
	float r = length(UV - 0.5) * 2.0;
	float checker = step(p3d_bayer(FRAGCOORD.xy), 0.5);
	float a = step(r, outer) * outer_gain * 2.0 * checker
		+ step(r, inner * (1.0 + 0.35 * pulse)) * inner_gain * (1.0 + pulse);
	ALBEDO = color.rgb * a;
}
