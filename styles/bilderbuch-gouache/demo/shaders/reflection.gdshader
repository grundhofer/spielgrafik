shader_type canvas_item;
// Spiegelbild eines Boots: gespiegeltes Sprite, nur unterhalb der Wasserlinie, zur Wasserfarbe hin gemischt und in
// waagerechte Pinselbänder zerlegt (wie gemalte Spiegelungen in Gouache: kurze Striche statt glatter Spiegel).

uniform float water_y = 500.0;
uniform float t = 0.0;
uniform float phase = 0.0;
uniform vec4 water_col : source_color = vec4(0.22, 0.38, 0.5, 1.0);
uniform float mix_water = 0.5;
uniform float strength = 0.55;
uniform float fade_px = 34.0;
varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float d = world_pos.y - water_y;
	float band = floor(d / 3.0);
	float off = sin(band * 1.9 + t * 2.4 + phase) * 2.0 * TEXTURE_PIXEL_SIZE.x;
	vec4 c = texture(TEXTURE, UV + vec2(off, 0.0));
	float vis = step(0.5, d) * (1.0 - smoothstep(0.0, fade_px, d));
	float gap = step(0.3, fract(band * 0.618 + 0.21));
	c.rgb = mix(c.rgb, water_col.rgb, mix_water);
	COLOR = vec4(c.rgb, c.a * vis * strength * mix(0.45, 1.0, gap));
}
