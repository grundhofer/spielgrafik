// Lichtkegel des Leuchtturms als waagrechter Fächer in Lampenhöhe; additiv, in zwei Stufen gerastert
// (geordnetes Dithering), damit er pixelig bleibt. UV: x = Abstand (0 an der Lampe, 1 am Ende), y = -1..1 quer.
shader_type canvas_item;
render_mode unshaded, blend_add;

uniform vec4 beam_color : source_color = vec4(1.0, 0.86, 0.58, 1.0);
uniform float strength = 0.18;

float bayer4(ivec2 p) {
	int x = p.x & 3, y = p.y & 3;
	int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
	return (float(m[y * 4 + x]) + 0.5) / 16.0;
}

void fragment() {
	float along = UV.x;
	float across = abs(UV.y) / max(UV.x, 0.001);          // 0 in der Mitte, 1 am Rand des Fächers
	float side = 1.0 - across * across;
	float i = pow(clamp(1.0 - along, 0.0, 1.0), 1.7) * side * side;
	i += 0.35 * step(across, 0.18) * (1.0 - along);        // heller Kern
	ivec2 p = ivec2(floor(FRAGCOORD.xy));
	float lvl = step(bayer4(p), i * 1.25) + step(bayer4(p + 2), i * 0.8);
	COLOR = vec4(beam_color.rgb * strength * lvl * 0.5, 1.0);
}
