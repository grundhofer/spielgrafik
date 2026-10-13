// Eine 4bpp-Hintergrundebene wie in Mode 1 der SNES-PPU: Die Textur enthält je Pixel den CGRAM-Index
// (Palette × 16 + Farbe, Farbe 0 = durchsichtig), die Farbe kommt aus der 256×1-CGRAM-Textur, die main.gd
// jedes Bild setzt (Palettenanimation). Zeilenscroll wie per HDMA: Jede Bildschirmzeile liest ihren
// horizontalen Versatz aus der 224×1-Tabelle (R = Versatz + 128) und wird mit Umbruch nach 256 px verschoben
// (die Kachelkarte ist 32 Kacheln breit und wiederholt sich).
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D cgram : filter_nearest, repeat_disable;
uniform sampler2D hdma : filter_nearest, repeat_disable;
uniform bool use_hdma = false;

void fragment() {
	ivec2 size = textureSize(TEXTURE, 0);
	ivec2 px = clamp(ivec2(UV * vec2(size)), ivec2(0), size - 1);
	int off = int(texelFetch(hdma, ivec2(px.y, 0), 0).r * 255.0 + 0.5) - 128;
	int sx = use_hdma ? ((px.x + off) % size.x + size.x) % size.x : px.x;
	int idx = int(texelFetch(TEXTURE, ivec2(sx, px.y), 0).r * 255.0 + 0.5);
	vec4 col = texelFetch(cgram, ivec2(idx, 0), 0);
	if (idx % 16 == 0) {
		discard;
	}
	COLOR = vec4(col.rgb, 1.0);
}
