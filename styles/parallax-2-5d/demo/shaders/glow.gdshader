// Additiver Lichtschein (Laterne, Fenster, Leuchtfeuer, Lichtkegel). Werte über 1 blühen im Glow auf.
shader_type spatial;
render_mode unshaded, blend_add, cull_disabled, depth_draw_never, shadows_disabled, fog_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec3 color = vec3(1.0, 0.7, 0.35);
uniform float intensity = 1.0;

void fragment() {
	vec4 c = texture(tex, UV);
	ALBEDO = color * c.rgb;
	ALPHA = c.a * intensity;
}
