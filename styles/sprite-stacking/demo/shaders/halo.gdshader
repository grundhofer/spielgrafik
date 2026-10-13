// Lichthof um Laterne, Fenster und Leuchtfeuer: additiver Kreis, gerastert in wenigen Stufen.
shader_type canvas_item;
render_mode unshaded, blend_add;

uniform vec4 halo_color : source_color = vec4(1.0, 0.72, 0.38, 1.0);
instance uniform float intensity = 1.0;

float bayer4(ivec2 p) {
	int x = p.x & 3, y = p.y & 3;
	int m[16] = int[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
	return (float(m[y * 4 + x]) + 0.5) / 16.0;
}

void fragment() {
	float r = length(UV - 0.5) * 2.0;
	float i = clamp(1.0 - r, 0.0, 1.0);
	i = i * i * intensity;
	ivec2 p = ivec2(floor(FRAGCOORD.xy));
	float lvl = step(bayer4(p), i * 1.4) * 0.5 + step(0.55, i) * 0.5;
	COLOR = vec4(halo_color.rgb * lvl * 0.42, 1.0);
}
