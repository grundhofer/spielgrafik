// Licht auf einem gedruckten Panelbild: hellt nur die farbigen Flächen um eine Lichtquelle zur Lichtfarbe auf,
// Tuschelinien (dunkel und unbunt) bleiben schwarz. Der Druck-Shader macht daraus kleinere, hellere Punkte.
shader_type canvas_item;

uniform vec2 tex_size = vec2(822.0, 582.0);
uniform vec4 lights[4];                // x, y (Texturpixel), Radius, Stärke
uniform vec3 light_col[4];

void fragment() {
	vec3 c = COLOR.rgb;
	float ink = smoothstep(0.62, 0.82, 1.0 - max(max(c.r, c.g), c.b));
	vec2 p = UV * tex_size;
	for (int i = 0; i < 4; i++) {
		vec4 L = lights[i];
		if (L.z > 0.0) {
			float f = clamp(1.0 - length(p - L.xy) / L.z, 0.0, 1.0);
			f = pow(f, 1.4) * L.w * (1.0 - ink);
			c = mix(c, light_col[i], clamp(f, 0.0, 1.0));
		}
	}
	COLOR.rgb = c;
}
