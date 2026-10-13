// Ausgabe der Ego-Ansicht: Wo nichts gezeichnet wurde (Alpha 0), steht der Himmel. Er hängt nur am
// Blickwinkel (Spalte -> Winkel, 4 Wiederholungen je Umdrehung) und an der Bildzeile (Horizont =
// Bildmitte): Er scrollt waagrecht mit, nie senkrecht. Alle übrigen Pixel werden auf die nächste
// Palettenfarbe eingerastet (in Forward+ ist das schon die richtige Farbe; Mobile rechnet mit 10 Bit,
// Compatibility anders gerundet).
shader_type canvas_item;

uniform sampler2D palette : filter_nearest;     // 256 x 5, Zeile 0
uniform sampler2D sky : filter_nearest;         // 256 x 128 Indizes, Horizont in Zeile 100
uniform float yaw = 0.0;                        // Blickrichtung, rechts positiv (Bogenmaß)
uniform vec2 view_size = vec2(320.0, 168.0);

void fragment() {
	vec2 px = floor(UV * view_size);
	vec4 s = texture(TEXTURE, UV);
	if (s.a < 0.5) {
		float half_w = view_size.x * 0.5;
		float ang = yaw + atan((px.x + 0.5 - half_w) / half_w);
		float u = fract(ang / 6.28318530718 * 4.0);
		int col = int(floor(u * 256.0)) & 255;
		int row = clamp(int(px.y) - int(view_size.y * 0.5) + 100, 0, 127);
		int idx = int(texelFetch(sky, ivec2(col, row), 0).r * 255.0 + 0.5);
		COLOR = vec4(texelFetch(palette, ivec2(idx, 0), 0).rgb, 1.0);
	} else {
		vec3 best = vec3(0.0);
		float bd = 1e9;
		for (int i = 0; i < 255; i++) {
			vec3 p = texelFetch(palette, ivec2(i, 0), 0).rgb;
			vec3 d = p - s.rgb;
			float dd = dot(d, d);
			if (dd < bd) {
				bd = dd;
				best = p;
			}
		}
		COLOR = vec4(best, 1.0);
	}
}
