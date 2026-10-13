shader_type canvas_item;
// Ortskarte oben links: schräges Band, das nach rechts ausläuft, mit Akzentstreifen links.
uniform vec2 size = vec2(430.0, 64.0);
uniform vec4 band_color : source_color = vec4(0.07, 0.07, 0.2, 0.78);
uniform vec4 accent_color : source_color = vec4(0.99, 0.62, 0.48, 1.0);
uniform float reveal = 1.0;   // 0..1 Wischen von links

void fragment() {
	vec2 p = UV * size;
	float slant = (size.y - p.y) * 0.35;
	float right = size.x - 70.0 + slant;
	float body = step(p.x, right);
	float fade = 1.0 - smoothstep(right - 150.0, right, p.x);
	float a = band_color.a * (0.35 + 0.65 * fade) * body;
	vec4 c = vec4(band_color.rgb, a);
	// Akzent: schmaler schräger Streifen links
	float ax = p.x - slant;
	float acc = step(14.0, ax) * step(ax, 20.0);
	c = mix(c, accent_color, acc);
	// feine helle Linie unten
	float line = step(size.y - 2.0, p.y) * step(p.x, right) * (0.25 + 0.75 * fade);
	c = mix(c, vec4(1.0, 0.92, 0.88, 0.9), line);
	float rv = step(p.x, reveal * (size.x + 40.0) - slant);
	COLOR = vec4(c.rgb, c.a * rv) * COLOR.a;
}
