// Hintergrund: gemaltes KI-Bild; Wasser bewegt sich zeilenweise um ganze Pixel, Wellenkämme hellen kurze Striche
// auf, helle Spiegelungen glitzern.
// masks: R = Wasser (0..1, weich), G = helle Spiegelung (Glitzerstellen), B = frei.
shader_type canvas_item;

uniform sampler2D masks : filter_linear, repeat_disable;
uniform float time = 0.0;
uniform vec2 size = vec2(1280.0, 720.0);
uniform float horizon = 330.0;
uniform float near = 560.0;
uniform float ripple = 0.08;        // Helligkeit der Wellenkämme (Anteil)

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash(vec2 p) {
	// nur Multiplikation und fract (sin-Hashes rechnen je Renderer verschieden)
	vec3 q = fract(vec3(p.xyx) * 0.1031);
	q += dot(q, q.yzx + 33.33);
	return fract((q.x + q.y) * q.z);
}

void fragment() {
	vec2 px = floor(UV * size);
	vec4 m = texture(masks, UV);
	float depth = clamp((px.y - horizon) / max(near - horizon, 1.0), 0.0, 1.0);
	vec4 c = texture(TEXTURE, UV);
	if (m.r > 0.01) {
		// Zeilenwellen: Verschiebung in ganzen Pixeln, vorn stärker, Wellenlänge wächst zum Betrachter
		float row = px.y;
		float w1 = sin(row * mix(0.9, 0.35, depth) + time * 1.9);
		float w2 = sin(row * mix(0.37, 0.16, depth) - time * 1.3 + 1.7);
		float amp = mix(1.0, 3.6, depth);
		float dx = floor((w1 * 0.6 + w2 * 0.4) * amp + 0.5);
		vec2 suv = (px + vec2(dx, 0.0) + 0.5) / size;
		vec4 w = texture(TEXTURE, suv);
		// nur aus Wasser lesen: sonst wandern Takelage, Masten und Pfahlkanten als Doppelbild ins Wasser
		float ms = texture(masks, suv).r;
		c = mix(c, w, m.r * ms);
		// Wellenkämme: kurze waagerechte Lichtstriche, die mit den Zeilenwellen wandern (sonst bleibt glattes,
		// texturarmes Wasser beim Verschieben fast unverändert)
		float crest = smoothstep(0.35, 0.95, w1) * smoothstep(0.1, 0.9, sin(px.x * mix(0.09, 0.035, depth) + row * 2.3 - time * 0.7));
		float trough = smoothstep(0.45, 0.95, -w2) * 0.6;
		c.rgb *= 1.0 + m.r * (ripple * crest - ripple * 0.7 * trough);
		// Glitzern: kurze waagerechte Striche auf hellen Spiegelungen, je Zelle eigener Takt
		vec2 cell = floor(px / vec2(mix(3.0, 7.0, depth), 2.0));
		float ph = hash(cell) * 6.2831 + time * (2.0 + 3.0 * hash(cell + 7.0));
		float sp = pow(max(0.0, sin(ph)), 24.0) * m.g;
		c.rgb += vec3(1.0, 0.86, 0.6) * sp * 0.7;
	}
	COLOR = c;
}
