// Filmlook über der ganzen Szene (nicht über der Oberfläche): Lichthof um helle Lichter (Halation über die
// Mipmaps des Bildschirms), strenges Schwarzweiß mit Rot als einziger Farbe, leichtes Belichtungsflackern,
// Vignette und Filmkorn. Korn und Flackern hängen nur von der Bildnummer ab (deterministisch).
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float frame = 0.0;
uniform float exposure = 1.0;
uniform float grain = 0.055;
uniform float vignette = 0.42;
uniform float halation = 0.30;

float h1(vec2 p) {
	return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void fragment() {
	vec2 uv = SCREEN_UV;
	vec3 c = textureLod(screen_tex, uv, 0.0).rgb;
	vec3 b1 = textureLod(screen_tex, uv, 3.0).rgb;
	vec3 b2 = textureLod(screen_tex, uv, 5.0).rgb;
	vec3 bloom = max(b1 - 0.62, 0.0) * 0.8 + max(b2 - 0.55, 0.0) * 0.8;
	c += vec3(dot(bloom, vec3(0.333))) * halation;

	// Nur Rot bleibt farbig (Schal); alles andere auf Helligkeit
	float mx = max(c.r, max(c.g, c.b));
	float mn = min(c.r, min(c.g, c.b));
	float sat = (mx - mn) / max(mx, 1e-3);
	float redness = smoothstep(0.22, 0.42, sat) * smoothstep(0.0, 0.05, c.r - max(c.g, c.b) * 1.3);
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(vec3(l), c, redness);

	c *= exposure;
	vec2 d = uv - 0.5;
	d.x *= 1.25;
	c *= 1.0 - vignette * smoothstep(0.30, 0.95, length(d));

	// Korn: zwei Oktaven Wertrauschen je Bild, stärker in den Mitteltönen
	vec2 px = floor(FRAGCOORD.xy);
	float g = h1(px + vec2(frame * 17.13, frame * 3.71)) + h1(floor(px * 0.5) + vec2(frame * 5.3, 1.7));
	g = g - 1.0;
	float lum = dot(c, vec3(0.333));
	c += g * grain * (0.35 + 0.65 * (1.0 - abs(lum - 0.45) * 1.6));
	COLOR = vec4(clamp(c, 0.0, 1.0), 1.0);
}
