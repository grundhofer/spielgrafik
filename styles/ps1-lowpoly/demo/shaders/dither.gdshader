// Letzter Schritt über das ganze 320×240-Bild: 24 Bit -> 15 Bit (5 Bit je Kanal) mit der
// 4×4-Dithertabelle der Konsole (Versatz -4..+3 in 8-Bit-Stufen vor dem Abschneiden der unteren 3 Bit).
// Wirkt auf 3D, Himmel und Oberfläche gleichermaßen, wie bei der Konsole auf Gouraud-Flächen.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform bool enabled = true;

const float DITHER[16] = float[](-4.0, 0.0, -3.0, 1.0, 2.0, -2.0, 3.0, -1.0, -3.0, 1.0, -4.0, 0.0, 3.0, -1.0, 2.0, -2.0);

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	if (enabled) {
		ivec2 p = ivec2(FRAGCOORD.xy) % 4;
		vec3 c8 = floor(c * 255.0 + 0.5) + DITHER[p.y * 4 + p.x];
		vec3 c5 = floor(clamp(c8, 0.0, 255.0) / 8.0);
		c = c5 * 8.0 / 255.0 + c5 / 31.0 * (7.0 / 255.0);   // 5 Bit zurück auf 0..1 (31 -> 1.0)
	}
	COLOR = vec4(c, 1.0);
}
