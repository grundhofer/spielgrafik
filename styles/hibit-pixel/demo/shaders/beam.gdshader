// Leuchtfeuer: sich drehender Lichtkegel, von der Seite gesehen. Die sichtbare Länge folgt |cos(Winkel)|,
// der Kegel weitet sich und läuft spitz aus; Helligkeit in Stufen mit Dithering nur an den Stufengrenzen.
// Additiv über Himmel und Fernem, vom Nahen verdeckt (Zeichenreihenfolge).
shader_type canvas_item;
render_mode blend_add, unshaded;

uniform vec2 origin = vec2(575.0, 88.0);
uniform float dirx = 1.0;          // cos(Winkel): Richtung und Verkürzung
uniform float strength = 1.0;
uniform float max_len = 330.0;
uniform vec3 beam_color : source_color = vec3(1.0, 0.88, 0.62);
uniform vec2 screen = vec2(640.0, 360.0);

float bayer4(vec2 p) {
	int x = int(mod(floor(p.x), 4.0));
	int y = int(mod(floor(p.y), 4.0));
	float m[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
	return (m[x + y * 4] + 0.5) / 16.0;
}

void fragment() {
	vec2 p = floor(UV * screen) + 0.5;
	vec2 d = p - origin;
	float len = abs(dirx) * max_len;
	float along = d.x * sign(dirx);
	float across = abs(d.y - along * 0.025);
	float halfw = 1.2 + along * 0.085;
	float inside = step(0.0, along) * step(along, len);
	float tip = 1.0 - clamp(along / max(len, 1.0), 0.0, 1.0);
	float edge = clamp(1.0 - across / max(halfw, 0.1), 0.0, 1.0);
	float v = inside * pow(tip, 1.3) * pow(edge, 0.8) * strength;
	// 5 Stufen, Dither nur im schmalen Übergang
	float s = v * 5.0;
	float t = clamp((fract(s) - 0.5) / 0.3 + 0.5, 0.0, 1.0);
	float q = (floor(s) + (t > bayer4(p) ? 1.0 : 0.0)) / 5.0;
	COLOR = vec4(beam_color * q * 0.85, 1.0);
}
