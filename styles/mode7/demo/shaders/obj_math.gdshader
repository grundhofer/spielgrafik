// Sprites mit OBJ-Paletten 4..7 und Farbmathematik "halbe Addition" wie auf der Konsole: Ergebnis =
// (OBJ + Subscreen) >> 1 je 5-Bit-Kanal. Der Subscreen enthält nur die Hintergrundebenen (BackBufferCopy
// vor den Sprites), daher mischen sich durchscheinende Sprites nicht mit anderen Sprites.
shader_type canvas_item;
render_mode unshaded, blend_disabled;

uniform sampler2D cgram : filter_nearest, repeat_disable;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest, repeat_disable;

void fragment() {
	ivec2 sz = textureSize(TEXTURE, 0);
	ivec2 p = clamp(ivec2(floor(UV * vec2(sz))), ivec2(0), sz - 1);
	int idx = int(round(texelFetch(TEXTURE, p, 0).r * 255.0));
	if (idx == 0) {
		discard;
	}
	vec3 o = round(texelFetch(cgram, ivec2(idx, 0), 0).rgb * 31.0);
	vec3 s = round(texture(screen_tex, SCREEN_UV).rgb * 31.0);
	COLOR = vec4(round(floor((o + s) * 0.5) * 255.0 / 31.0) / 255.0, 1.0);
}
