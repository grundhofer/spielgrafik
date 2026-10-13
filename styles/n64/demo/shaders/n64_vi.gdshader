// Videoausgabe der Konsole nachgebaut: liest das 320×240-Bild des SubViewports (3D und Oberfläche) und gibt
// es 3-fach vergrößert aus (960×720).
//  1. 16-Bit-Bildspeicher: jeder Kanal auf 5 Bit, vorher die 4×4-"Magic-Square"-Dithertabelle der Konsole
//     (Versatz 0..7 in 8-Bit-Stufen, dann die unteren 3 Bit abschneiden).
//  2. Dither-Filter der Videoeinheit: Jeder Kanal nimmt die Abweichung zu den 8 Nachbarn auf, aber höchstens
//     eine 5-Bit-Stufe je Nachbar, und mittelt sie. So verschwindet das Dithermuster auf Verläufen, Kanten
//     (größere Sprünge) bleiben.
//  3. Weich vergrößern (bilinear) und leicht waagrecht verwischen wie über das analoge Videosignal.
// Die Kantenglättung der Konsole (Abdeckung an Polygonkanten) übernimmt MSAA 4× im SubViewport.
shader_type canvas_item;
render_mode unshaded;

uniform sampler2D src : filter_nearest, repeat_disable;
uniform vec2 src_size = vec2(320.0, 240.0);
uniform float dither_on = 1.0;
uniform float filter_on = 1.0;
uniform float smooth_on = 1.0;
uniform float hblur = 0.4;          // halbe Breite der waagrechten Unschärfe in Quellpixeln

const int MAGIC[16] = int[16](0, 6, 1, 7, 4, 2, 5, 3, 3, 5, 2, 4, 7, 1, 6, 0);

vec3 fb(ivec2 p) {
	// Bildspeicher an Pixel p als 5-Bit-Werte (0..31)
	p = clamp(p, ivec2(0), ivec2(src_size) - 1);
	vec3 c = texelFetch(src, p, 0).rgb;
	vec3 c8 = floor(c * 255.0 + 0.5);
	if (dither_on < 0.5) {
		return c8 / 255.0 * 31.0;
	}
	float d = float(MAGIC[(p.y & 3) * 4 + (p.x & 3)]);
	return floor(min(c8 + d, vec3(255.0)) / 8.0);
}

vec3 vi(ivec2 p) {
	vec3 c = fb(p);
	if (dither_on > 0.5 && filter_on > 0.5) {
		vec3 acc = vec3(0.0);
		for (int j = -1; j <= 1; j++) {
			for (int i = -1; i <= 1; i++) {
				if (i == 0 && j == 0) {
					continue;
				}
				acc += clamp(fb(p + ivec2(i, j)) - c, vec3(-1.0), vec3(1.0));
			}
		}
		c += acc / 8.0;
	}
	return c / 31.0;
}

vec3 bilinear(vec2 sp) {
	vec2 fl = floor(sp);
	vec2 f = sp - fl;
	ivec2 i = ivec2(fl);
	vec3 a = vi(i);
	vec3 b = vi(i + ivec2(1, 0));
	vec3 c = vi(i + ivec2(0, 1));
	vec3 d = vi(i + ivec2(1, 1));
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

void fragment() {
	vec2 sp = UV * src_size - 0.5;
	vec3 col;
	if (smooth_on > 0.5) {
		col = 0.25 * bilinear(sp - vec2(hblur, 0.0)) + 0.5 * bilinear(sp) + 0.25 * bilinear(sp + vec2(hblur, 0.0));
	} else {
		col = vi(ivec2(floor(UV * src_size)));
	}
	COLOR = vec4(col, 1.0);
}
