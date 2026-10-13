// Indexbild + Palette wie im VGA-Modus 13h: die Textur enthält Palettenindizes (0..255),
// die Farbe kommt aus einer 256x1-Palette, die das Skript jedes Bild neu setzt (Farbzyklus).
// Der Lichtkegel des Leuchtturms erzeugt keine neuen Farben: er tauscht Indizes über eine
// Aufhell-Tabelle (fünf Stufen) aus. Die Stufen liegen als flache Bänder übereinander; geordnetes
// 4x4-Dithering nur in einem schmalen Übergang an jeder Stufengrenze (beam_band), damit das Kegelende
// nicht zu einem breiten Punkteraster wird. Die Werte setzt main.gd aus palette.json -> beam.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D palette_tex : filter_nearest, repeat_disable;
uniform sampler2D beam_tex : filter_nearest, repeat_disable;
uniform sampler2D lut_tex : filter_nearest, repeat_disable;
uniform float beam_angle = 0.0;
uniform int beam_levels = 5;
uniform float beam_gain = 5.8;
uniform float beam_band = 0.25;
uniform float beam_cut = 0.0;
uniform float beam_soft = 0.14;

const float BAYER[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0,
                                  3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

void fragment() {
	ivec2 size = textureSize(TEXTURE, 0);
	ivec2 px = clamp(ivec2(UV * vec2(size)), ivec2(0), size - 1);
	int idx = int(texelFetch(TEXTURE, px, 0).r * 255.0 + 0.5);
	vec3 b = texelFetch(beam_tex, px, 0).rgb;
	if (b.r > 0.0) {
		float c = cos(beam_angle);
		float s = sin(beam_angle);
		float I = 0.0;
		if (b.b > 0.3 && b.b < 0.7) {
			// Hof um die Lampe: blitzt, wenn der Strahl zur Kamera zeigt
			I = pow(max(s, 0.0), 8.0);
		} else {
			// Seitenansicht: sichtbare Länge des Strahls = Anteil, der zu dieser Seite zeigt
			float dir = (b.b < 0.5) ? -c : c;
			if (dir > 0.0) {
				I = (1.0 - smoothstep(dir - beam_soft, dir, b.g)) * (0.45 + 0.55 * dir);
			}
		}
		float level = b.r * I * beam_gain;
		float th = (BAYER[(px.y % 4) * 4 + (px.x % 4)] + 0.5) / 16.0;
		float fl = floor(level);
		float fr = clamp((level - fl - 0.5) / beam_band + 0.5, 0.0, 1.0);
		int lv = int(floor(fl + fr + th));
		if (level >= beam_cut && lv >= 1) {
			idx = int(texelFetch(lut_tex, ivec2(idx, min(lv, beam_levels) - 1), 0).r * 255.0 + 0.5);
		}
	}
	COLOR = texelFetch(palette_tex, ivec2(idx, 0), 0);
}
