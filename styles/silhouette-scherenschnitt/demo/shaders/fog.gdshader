// Nebelstreifen zwischen den Papierebenen wie durchscheinendes Seidenpapier: oben eine wellige, scharf
// geschnittene Kante, nach unten auslaufend, langsam seitlich driftend (ganze Pixel).
shader_type canvas_item;

uniform float t = 0.0;
uniform vec2 rect_size = vec2(1280.0, 120.0);
uniform vec4 tint : source_color = vec4(0.95, 0.62, 0.50, 1.0);
uniform float density = 0.35;
uniform float edge_y = 30.0;      // mittlere Lage der Oberkante im Rechteck
uniform float edge_amp = 8.0;
uniform float speed = 6.0;        // px/s
uniform float fade = 1.0;         // 1 = nach unten auslaufend, 0 = flach
uniform float seed = 0.0;

void fragment() {
	vec2 p = floor(UV * rect_size) + 0.5;
	float x = p.x + floor(t * speed);
	float e = edge_y + edge_amp * (0.55 * sin(x * 0.011 + seed) + 0.3 * sin(x * 0.027 + 1.7 * seed)
		+ 0.15 * sin(x * 0.061 + 3.1 * seed));
	float inside = smoothstep(e - 0.7, e + 0.7, p.y);
	float k = clamp((p.y - e) / max(rect_size.y - e, 1.0), 0.0, 1.0);
	float a = density * inside * mix(1.0, 1.0 - k, fade);
	COLOR = vec4(tint.rgb, a);
}
