// Letzter Schritt: jedes Pixel auf 15-Bit-RGB (5 Bit je Kanal) einrasten und so ausgeben, wie die
// Konsole es tut (v<<3 | v>>2). Sprites und Hintergrund liegen schon auf dem Raster; neue Farben
// entstehen nur durch Farbrechnung (Lichtkegel addiert, Schatten dunkelt ab) und landen hier wieder darauf.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;

void fragment() {
	vec3 c = texelFetch(screen_tex, ivec2(FRAGCOORD.xy), 0).rgb;
	vec3 v = floor(clamp(c, 0.0, 1.0) * 31.0 + 0.5);
	COLOR = vec4((v * 8.0 + floor(v / 4.0)) / 255.0, 1.0);
}
