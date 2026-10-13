shader_type canvas_item;
// Gemeinsames Korn über Foto und Figur (nicht über der Oberfläche): Das KI-Foto hat stehendes Sensorrauschen, der
// Dachs keines. Ein bewegtes Korn über beidem macht daraus eine Aufnahme. Korn hängt nur von der Bildnummer ab
// (deterministisch), stärker in den Mitteltönen, leicht farbig wie Sensorrauschen.
uniform sampler2D screen_tex : hint_screen_texture, filter_linear;
uniform float frame = 0.0;
uniform float grain = 0.030;
uniform bool enabled = true;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float h1(vec2 p) {
	// Hash ohne sin: in allen Renderern gleich
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void fragment() {
	vec3 c = texture(screen_tex, SCREEN_UV).rgb;
	if (enabled) {
		vec2 px = floor(FRAGCOORD.xy);
		float f = mod(frame, 997.0);
		float g = h1(px + vec2(f * 37.0, f * 11.0)) + h1(px * 1.0 + vec2(13.7, f * 23.0)) - 1.0;
		float gc = h1(px + vec2(f * 5.0, 91.0)) - 0.5;
		float l = dot(c, vec3(0.299, 0.587, 0.114));
		float amt = grain * (0.45 + 1.6 * l * (1.0 - l));
		c += vec3(g + gc * 0.25, g, g - gc * 0.25) * amt;
	}
	COLOR = vec4(c, 1.0);
}
