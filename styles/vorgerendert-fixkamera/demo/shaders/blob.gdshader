// Runder Schatten unter der Figur (wie in den Spielen der Zeit): liegt 2,5 cm über dem Kai, dunkelt das
// Hintergrundbild ab und wird vom Tiefenbild verdeckt wie die Figur selbst.
// (blend_mul blieb in Forward+ unsichtbar und gab im Mobile-Renderer eine harte Fläche; daher Alpha-Mischung.)
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform float strength = 0.85;

void fragment() {
	float r = length(UV * 2.0 - 1.0);
	ALBEDO = vec3(0.02, 0.02, 0.04);
	ALPHA = (1.0 - smoothstep(0.55, 1.0, r)) * strength;
}
