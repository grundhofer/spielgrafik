// Bitplane-Bild wie auf dem Amiga: Die Textur enthält je Pixel das Farbregister (0..31), die Farbe kommt aus
// einer 32x1-Palette, die main.gd jedes Bild neu schreibt (Farbzyklus, Blinken, Flackern = nur Registerwerte).
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D palette_tex : filter_nearest, repeat_disable;

void fragment() {
	ivec2 size = textureSize(TEXTURE, 0);
	ivec2 px = clamp(ivec2(UV * vec2(size)), ivec2(0), size - 1);
	int idx = int(texelFetch(TEXTURE, px, 0).r * 255.0 + 0.5);
	COLOR = texelFetch(palette_tex, ivec2(idx, 0), 0);
}
