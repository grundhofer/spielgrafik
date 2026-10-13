// Indexbild + Palette: Die Textur enthält im Rotkanal den Palettenindex (0..255), im Grünkanal die Deckkraft
// (nur beim Sprite; der Hintergrund ist voll deckend und hat G = R). Die Farbe kommt aus einer 256x1-Palette,
// die cycler.gd jedes Bild neu schreibt (Rotation der Zyklus-Bereiche, Überblendung Abend -> Nacht -> Regen,
// Lichtkegel und Flackern als berechnete Einträge). Das Bild selbst ändert sich nie.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D palette_tex : filter_nearest, repeat_disable;
uniform bool use_alpha = false;      // Sprite: Deckkraft aus dem Grünkanal
uniform bool probe = false;          // Prüflauf: Sprite in reinem Magenta (Fußmessung)
// Regen vor der Figur (nur Sprite): rain_tex ist eine szenengroße Bahnkarte (R = Regen-Eintrag, G = Bahn) mit
// denselben Bahnen und Phasen wie die Regenpixel im Hintergrund. Zeigt der Eintrag gerade den hellen Tropfenkopf
// (Deckkraft im Alphakanal der Palette, von cycler.gd mal Regenstärke geschrieben), ersetzt er das Figurpixel.
// 1-Bit über eine Bayer-Schwelle: Jedes Pixel bleibt eine Palettenfarbe, beim Einsetzen kommen die Tropfen gestaffelt.
uniform sampler2D rain_tex : filter_nearest, repeat_disable;
uniform bool rain_over = false;
const float BAYER[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	ivec2 size = textureSize(TEXTURE, 0);
	ivec2 px = clamp(ivec2(UV * vec2(size)), ivec2(0), size - 1);
	vec4 t = texelFetch(TEXTURE, px, 0);
	int idx = int(t.r * 255.0 + 0.5);
	vec4 c = texelFetch(palette_tex, ivec2(idx, 0), 0);
	ivec2 wp = clamp(ivec2(floor(world)), ivec2(0), textureSize(rain_tex, 0) - 1);
	vec4 r = texelFetch(rain_tex, wp, 0);
	vec4 rc = texelFetch(palette_tex, ivec2(int(r.r * 255.0 + 0.5), 0), 0);
	float a = 1.0;
	if (use_alpha) {
		a = t.g > 0.5 ? 1.0 : 0.0;
		float th = (BAYER[(wp.x % 4) + 4 * (wp.y % 4)] + 0.5) / 16.0;
		if (rain_over && r.g > 0.5 && rc.a > th) {
			c = rc;
		}
		if (probe) {
			c = vec4(1.0, 0.0, 1.0, 1.0);
		}
	}
	COLOR = vec4(c.rgb, a);
}
