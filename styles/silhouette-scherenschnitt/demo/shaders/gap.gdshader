// Schnittfuge: Vor dem nahen Arm und dem nahen Bein liegt ein um 1,5 px geweiteter Umriss, der den
// Bildschirm ohne Puppe zeigt (BackBufferCopy vor der Puppe). Wo der Arm über dem Rumpf liegt, erscheint
// so eine feine helle Fuge wie zwischen zwei aufeinanderliegenden Scherenschnitten.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;

void fragment() {
	float a = texture(TEXTURE, UV).a;
	vec3 bg = texture(screen_tex, SCREEN_UV).rgb;
	COLOR = vec4(bg, a);
}
