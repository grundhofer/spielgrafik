// Runder, weicher Bodenschatten unter der Figur (wie in Online-Rollenspielen üblich): dunkles Violett mit
// weichem Rand, gemischt (blend_mix), damit es in allen Renderern gleich wirkt (blend_mul wurde in
// Compatibility zu einem schwarzen Viereck).
shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform vec3 shadow_color : source_color = vec3(0.24, 0.16, 0.32);
uniform float strength = 0.6;

void fragment() {
	vec2 p = UV * 2.0 - 1.0;
	float r = length(p);
	ALBEDO = shadow_color;
	ALPHA = (1.0 - smoothstep(0.3, 1.0, r)) * strength;
}
