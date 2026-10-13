// Figur: auf dasselbe Papier gedruckt wie die Platte. Innerhalb der Silhouette deckt das Papier (aus der Papier-
// textur an derselben Bildschirmstelle), darauf die Tusche. Die Laterne dünnt die Linien wie auf der Platte aus.
// TEXTURE: R = Tusche, G = Kammfeld, A = Deckung (scripts/build_badger.py)
shader_type canvas_item;
#include "res://shaders/inklight.gdshaderinc"

uniform sampler2D paper_tex : filter_linear;
uniform vec4 ink_color : source_color = vec4(0.169, 0.125, 0.09, 1.0);
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform vec2 lantern_screen = vec2(395.0, 119.0);
uniform float lantern_k = 1.0;
uniform float lantern_reach = 260.0;
uniform float light_amount = 0.32;

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec4 s = texture(TEXTURE, UV);
	vec3 paper = texture(paper_tex, world_pos / screen_size).rgb;
	float dl = length(world_pos - lantern_screen);
	float L = light_amount * lantern_k * (1.0 - smoothstep(lantern_reach * 0.45, lantern_reach, dl));
	float ink = thin_lines(s.r, s.g, L);
	COLOR = vec4(mix(paper, ink_color.rgb, ink * ink_color.a), s.a);
}
