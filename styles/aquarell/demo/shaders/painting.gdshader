shader_type canvas_item;
// Gemälde: Im Wasser verschiebt sich die gemalte Spiegelung zeilenweise ein wenig (ruhiges Kräuseln).
uniform sampler2D water_mask : filter_linear;
uniform float time_s = 0.0;
uniform vec2 tex_size = vec2(1280.0, 720.0);
uniform float amp_px = 2.0;

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

void fragment() {
	float m = texture(water_mask, UV).r;
	float y = UV.y * tex_size.y;
	// Wellen laufen langsam; nach unten (näher) länger und stärker
	float depth = clamp((y - 380.0) / 200.0, 0.0, 1.0);
	float off = 0.6 * sin(y * 0.55 - time_s * 1.7) + 0.4 * sin(y * 0.23 + time_s * 1.1 + 1.3);
	off *= amp_px * (0.5 + depth);
	// Am ausgefransten Papierrand nicht verschieben (sonst wackelt der Rand in den Wasserzeilen): Alpha immer
	// unverschoben abtasten, Farbe nur dort verschieben, wo das Gemälde in ±4 px ringsum deckt.
	vec2 px4 = vec2(4.0 / tex_size.x, 0.0);
	float inside = min(texture(TEXTURE, UV - px4).a, texture(TEXTURE, UV + px4).a);
	float k = m * smoothstep(0.9, 1.0, inside);
	vec4 c = texture(TEXTURE, UV + vec2(off * k / tex_size.x, 0.0));
	c.a = texture(TEXTURE, UV).a;
	COLOR = c * vcol;
}
