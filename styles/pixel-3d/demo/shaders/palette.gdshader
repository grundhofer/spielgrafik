// Palette einrasten: jeder Pixel des 3D-Bildes bekommt die nächste Farbe aus palette.png
// (Abstand in OKLab, also nach wahrgenommener Helligkeit und Farbe). Läuft auf dem Sprite2D, das
// den SubViewport "World" dreifach vergrößert zeigt; die Nearest-Abtastung hält die Pixel scharf.
shader_type canvas_item;

uniform sampler2D palette : filter_nearest, repeat_disable;
uniform int count = 1;
uniform float enabled = 1.0;

vec3 srgb_to_linear(vec3 c) {
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c));
}

vec3 oklab(vec3 srgb) {
	vec3 c = srgb_to_linear(srgb);
	float l = 0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b;
	float m = 0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b;
	float s = 0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b;
	l = pow(max(l, 0.0), 1.0 / 3.0);
	m = pow(max(m, 0.0), 1.0 / 3.0);
	s = pow(max(s, 0.0), 1.0 / 3.0);
	return vec3(0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
		1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
		0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s);
}

void fragment() {
	vec3 c = texture(TEXTURE, UV).rgb;
	if (enabled > 0.5) {
		vec3 lab = oklab(c);
		float best = 1e9;
		vec3 pick = c;
		for (int i = 0; i < count; i++) {
			vec3 p = texelFetch(palette, ivec2(i, 0), 0).rgb;
			vec3 d = oklab(p) - lab;
			d.x *= 1.3;   // Helligkeit etwas stärker gewichten als Farbton
			float dd = dot(d, d);
			if (dd < best) {
				best = dd;
				pick = p;
			}
		}
		c = pick;
	}
	COLOR = vec4(c, 1.0);
}
