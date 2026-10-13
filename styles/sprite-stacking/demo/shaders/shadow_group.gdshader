// CanvasGroup der Schatten: Kinder werden in einen eigenen Puffer gezeichnet (keine Verdopplung, wo sich
// Schichten überlappen) und dann multiplikativ über das Bild gelegt.
shader_type canvas_item;
render_mode unshaded, blend_mul;

uniform sampler2D screen_texture : hint_screen_texture, repeat_disable, filter_nearest;

void fragment() {
	vec4 c = textureLod(screen_texture, SCREEN_UV, 0.0);
	vec3 col = c.a > 0.0001 ? c.rgb / c.a : vec3(1.0);
	COLOR = vec4(mix(vec3(1.0), col, step(0.5, c.a)), 1.0);
}
