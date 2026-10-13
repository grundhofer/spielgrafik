// Sprites (OBJ): Atlas mit CGRAM-Index je Pixel, 0 = durchsichtig, Farbe aus der CGRAM (Palettenanimation).
shader_type canvas_item;
render_mode unshaded, blend_disabled;

uniform sampler2D cgram : filter_nearest, repeat_disable;

void fragment() {
	ivec2 sz = textureSize(TEXTURE, 0);
	ivec2 p = clamp(ivec2(floor(UV * vec2(sz))), ivec2(0), sz - 1);
	int idx = int(round(texelFetch(TEXTURE, p, 0).r * 255.0));
	if (idx == 0) {
		discard;
	}
	COLOR = vec4(texelFetch(cgram, ivec2(idx, 0), 0).rgb, 1.0);
}
