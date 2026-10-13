// Spiegelbild eines Boots-Cels: gespiegeltes Sprite, nur unterhalb der Wasserlinie, als flache, dunklere
// Wasserfarbe in waagerechte Streifen zerlegt, die sich auf Zweien (tick) seitlich versetzen. In den ersten
// 14 px unter der Wasserlinie ist es kräftiger (50 % Bootsfarbe, Deckkraft 0,8, ohne Lücken), damit Rumpf und
// Spiegelbild zusammenhängen; weiter unten 38 % Bootsfarbe und Deckkraft 0,55, nach unten ausblendend.
shader_type canvas_item;

uniform float waterline = 500.0;
uniform float depth = 40.0;
uniform vec4 water : source_color = vec4(0.08, 0.16, 0.3, 1.0);
uniform float tick = 0.0;
varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float d = world.y - waterline;
	float band = floor(d / 4.0);
	float shift = sin(band * 1.7 + tick * 0.9) * 2.0;
	vec4 c = texture(TEXTURE, UV + vec2(shift * TEXTURE_PIXEL_SIZE.x, 0.0));
	float near = 1.0 - smoothstep(0.0, 14.0, d);
	float gap = max(step(mod(d, 4.0), 2.99), step(d, 6.0));
	float keep = step(0.0, d) * gap * (1.0 - clamp(d / depth, 0.0, 1.0));
	float boat_share = mix(0.38, 0.5, near);
	COLOR = vec4(mix(c.rgb, water.rgb, 1.0 - boat_share), c.a * mix(0.55, 0.8, near) * keep);
}
