// Weiche, halbtransparente Flächen im Raum: Rauchballen, Möwen, Kontaktschatten.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, depth_test_disabled, shadows_disabled, fog_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec4 tint : source_color = vec4(1.0);
uniform float opacity = 1.0;

void fragment() {
	vec4 c = texture(tex, UV);
	ALBEDO = c.rgb * tint.rgb;
	ALPHA = c.a * tint.a * opacity;
}
