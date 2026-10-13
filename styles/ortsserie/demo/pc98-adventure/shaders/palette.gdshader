shader_type canvas_item;
// Bildspeicher -> Bildschirm wie beim 16-Farben-Modus: Der SubViewport enthält nur Palettenindizes 0..15
// (Rotkanal = Index / 15), dieser Shader schlägt jede Farbe in den 16 Palettenregistern nach (16x1-Textur,
// jeder Kanal 4 Bit). Palettenwechsel in main.gd ändern damit alle Pixel eines Index zugleich.
uniform sampler2D palette_tex : filter_nearest;

void fragment() {
	ivec2 p = ivec2(floor(UV * vec2(textureSize(TEXTURE, 0))));
	float r = texelFetch(TEXTURE, p, 0).r;
	int idx = clamp(int(round(r * 15.0)), 0, 15);
	COLOR = vec4(texelFetch(palette_tex, ivec2(idx, 0), 0).rgb, 1.0);
}
