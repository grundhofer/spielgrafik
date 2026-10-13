// Bildfläche 160×168 als Indexbild (R8 = EGA-Farbe 0–15), auf 320 Breite gestreckt (Doppelpixel).
// mode 0: EGA, 16 feste Farben. mode 1: CGA-Fassung (Palette 1: Schwarz, Cyan, Magenta, Weiß); jedes
// Doppelpixel wird in zwei echte 320er-Pixel zerlegt, die je nach EGA-Farbe ein Muster aus zwei CGA-Farben
// bilden – so zeigten die Interpreter dasselbe Bild auf CGA-Karten.
shader_type canvas_item;
render_mode unshaded;

uniform int mode = 0;
const vec3 EGA[16] = vec3[16](
	vec3(0.0, 0.0, 0.0), vec3(0.0, 0.0, 0.667), vec3(0.0, 0.667, 0.0), vec3(0.0, 0.667, 0.667),
	vec3(0.667, 0.0, 0.0), vec3(0.667, 0.0, 0.667), vec3(0.667, 0.333, 0.0), vec3(0.667, 0.667, 0.667),
	vec3(0.333, 0.333, 0.333), vec3(0.333, 0.333, 1.0), vec3(0.333, 1.0, 0.333), vec3(0.333, 1.0, 1.0),
	vec3(1.0, 0.333, 0.333), vec3(1.0, 0.333, 1.0), vec3(1.0, 1.0, 0.333), vec3(1.0, 1.0, 1.0));
const vec3 CGA[4] = vec3[4](vec3(0.0), vec3(0.333, 1.0, 1.0), vec3(1.0, 0.333, 1.0), vec3(1.0));
// je EGA-Farbe: CGA-Farbe linkes Pixel * 4 + rechtes Pixel
const int CGA_PAIR[16] = int[16](0, 1, 5, 5, 10, 2, 6, 7, 3, 5, 5, 5, 11, 10, 15, 15);

void fragment() {
	ivec2 size = textureSize(TEXTURE, 0);
	ivec2 p = ivec2(floor(UV * vec2(size)));
	int idx = int(round(texelFetch(TEXTURE, p, 0).r * 255.0));
	idx = clamp(idx, 0, 15);
	if (mode == 0) {
		COLOR = vec4(EGA[idx], 1.0);
	} else {
		int half_px = int(floor(UV.x * float(size.x) * 2.0)) % 2;
		int pair = CGA_PAIR[idx];
		int c = half_px == 0 ? pair / 4 : pair % 4;
		COLOR = vec4(CGA[c], 1.0);
	}
}
