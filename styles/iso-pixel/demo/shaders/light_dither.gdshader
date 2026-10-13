// Additives Licht in Pixelstufen: Deckkraft (Vertexfarbe × strength) wird auf drei Stufen gerastert,
// die Übergänge mit einem 4×4-Bayer-Muster im Bildschirmraster. Bleibt auf dem Pixelraster, kein weicher Rand.
shader_type canvas_item;
render_mode blend_add;

uniform float strength = 1.0;
uniform float levels = 3.0;

const float BAYER[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

void fragment() {
	ivec2 p = ivec2(FRAGCOORD.xy) % 4;
	float th = (BAYER[p.y * 4 + p.x] + 0.5) / 16.0;
	float a = clamp(COLOR.a * strength, 0.0, 1.0);
	float q = floor(a * levels + th) / levels;
	COLOR = vec4(COLOR.rgb, q);
}
