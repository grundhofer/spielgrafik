// Schlagschatten der Figur im Jalousienlicht: dasselbe Sprite, von main.gd auf das Pflaster geschert. Zieht genau
// das Fensterlicht ab, das scene.gdshader an dieser Stelle addiert (blend_sub): sichtbar nur, wo Licht fällt.
shader_type canvas_item;
render_mode blend_sub;

#include "res://shaders/window.gdshaderinc"

uniform sampler2D bg_tex : filter_linear;
uniform sampler2D aux_mask : filter_linear;   // G Pflaster
uniform vec2 view_size = vec2(1280.0, 720.0);
uniform float strength = 0.92;

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec4 s = texture(TEXTURE, UV);
	vec2 suv = world / view_size;
	vec3 bg = texture(bg_tex, suv).rgb;
	float floor_m = texture(aux_mask, suv).g;
	vec3 add = win_floor_light(world, bg) * floor_m;
	COLOR = vec4(add * s.a * strength, 1.0);
}
