shader_type canvas_item;
// Einblenden in Kachelmustern (geordnete 4x4-Schwelle), wie beim Bildaufbau der 16-Farben-Rechner:
// Pixel erscheinen in 16 festen Stufen, ohne Mischfarben. reveal 0 = unsichtbar, 1 = ganz sichtbar.
uniform float reveal = 1.0;
const float BAYER[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

void fragment() {
	ivec2 p = ivec2(floor(FRAGCOORD.xy));
	float th = (BAYER[(p.y % 4) * 4 + (p.x % 4)] + 0.5) / 16.0;
	if (COLOR.a < 0.5 || th >= reveal) {
		discard;
	}
	COLOR.a = 1.0;
}
