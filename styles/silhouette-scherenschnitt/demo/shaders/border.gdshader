// Spitzenborte des Textfelds als Scherenschnitt: Papierstreifen mit Bogenkante oben, Lochreihe und
// Rautenreihe, alles als Löcher, durch die das Licht (warmer Ton) fällt.
shader_type canvas_item;

uniform vec2 rect_size = vec2(1280.0, 20.0);
uniform vec4 paper : source_color = vec4(0.07, 0.045, 0.09, 1.0);
uniform vec4 light : source_color = vec4(0.93, 0.62, 0.36, 1.0);
uniform float period = 16.0;

void fragment() {
	vec2 p = UV * rect_size;
	float x = mod(p.x, period) - period * 0.5;
	// Bogenkante oben: Halbkreise von unten
	float arc = length(vec2(x, p.y - 6.5)) - period * 0.5;
	float edge = smoothstep(-0.6, 0.6, -arc) + step(6.5, p.y);
	edge = clamp(edge, 0.0, 1.0);
	// Lochreihe (versetzt)
	float x2 = mod(p.x + period * 0.5, period) - period * 0.5;
	float hole = 1.0 - smoothstep(1.4, 2.3, length(vec2(x2, p.y - 6.0)));
	// Rautenreihe
	float dia = 1.0 - smoothstep(2.4, 3.2, abs(x) + abs(p.y - 13.5) * 1.6);
	// feine Linie unten
	float line = 1.0 - smoothstep(0.4, 1.1, abs(p.y - 18.0));
	float cut = max(max(hole, dia), line);
	vec4 c = mix(paper, light, cut);
	COLOR = vec4(c.rgb, edge);
}
