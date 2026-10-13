shader_type canvas_item;
// Papierkorn über dem ganzen Bild (auch über Figur und Schrift): multipliziert, dunkelt höchstens um `strength`.
render_mode blend_mul;

uniform sampler2D paper : repeat_enable, filter_linear;
uniform vec2 screen_px = vec2(1280.0, 720.0);
uniform float tile_px = 512.0;
uniform float strength = 0.07;

void fragment() {
	float g = texture(paper, UV * screen_px / tile_px).r;
	float f = 1.0 - strength * clamp(1.0 - g, 0.0, 1.0);
	COLOR = vec4(vec3(f), 1.0);
}
