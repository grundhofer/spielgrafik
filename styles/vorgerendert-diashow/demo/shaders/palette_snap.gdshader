// 8-Bit-Bildschirm: jeder Bildpunkt des fertigen Bildes (Knotenbild, Schrift, Mauszeiger) wird auf die nächste
// Farbe einer Palette gesetzt (die ersten `count` Einträge der Palettentextur).
// Zwei Rechtecke in main.tscn: Das Bild (y < 334) rastet auf die 256 Farben der gemeinsamen Palette ein; die
// Knotenbilder bestehen schon aus Palettenfarben und bleiben unverändert, betroffen ist nur der Mauszeiger.
// Das Textband (y ≥ 334) rastet nur auf die 12 Textfarben ein (Schwarz, Textrampe, Gold, nodes/text_palette.png):
// Die geglätteten Kantenpixel der Schrift landen so auf der Textrampe bzw. der Goldrampe, nicht auf Szenenfarben.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform sampler2D palette : filter_nearest;   // count×1 (oder breiter)
uniform int count = 256;

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	vec3 best_c = c;
	float best = 1e9;
	for (int i = 0; i < count; i++) {
		vec3 p = texelFetch(palette, ivec2(i, 0), 0).rgb;
		vec3 d = c - p;
		float e = dot(d * d, vec3(0.30, 0.59, 0.11));
		if (e < best) {
			best = e;
			best_c = p;
		}
	}
	COLOR = vec4(best_c, 1.0);
}
