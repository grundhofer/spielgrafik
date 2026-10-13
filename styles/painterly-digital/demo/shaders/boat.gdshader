// Boot im Wasser: unterhalb der Wasserlinie ausgeblendet (die Linie bleibt beim Schaukeln waagerecht in der Welt),
// Rumpf zur Wasserlinie hin dunkler und kühler. Mit reflection = 1 dasselbe Bild als Spiegelbild (Sprite mit
// scale.y = -1): nur der Teil über der Wasserlinie, gewellt, in Streifen gebrochen, zum Wasser getönt.
// Textur wird vor jeder Verzweigung abgetastet; COLOR-Vertexfarbe über varying.
shader_type canvas_item;

uniform float water_v = 0.8;         // Wasserlinie als UV.y
uniform float pivot_u = 0.5;         // Drehpunkt (UV.x), liegt auf der Wasserlinie
uniform float aspect = 2.0;          // Bildbreite / Bildhöhe
uniform float tilt = 0.0;            // aktuelle Drehung des Boots (rad), hält die Wasserlinie waagerecht
uniform float reflection = 0.0;
uniform float time_s = 0.0;
uniform vec3 water_tint = vec3(0.17, 0.27, 0.31);
uniform float refl_len = 0.55;       // Länge des Spiegelbilds als Anteil der Bildhöhe
uniform float refl_alpha = 0.6;

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

void fragment() {
	float wl = water_v - (UV.x - pivot_u) * aspect * tan(tilt);
	float above = wl - UV.y;                       // > 0: über der Wasserlinie
	float d = clamp(above / refl_len, 0.0, 1.0);
	vec2 uv = UV;
	uv.x += reflection * sin(UV.y * 140.0 + time_s * 2.3) * 0.006 * (0.25 + d);
	vec4 tex = texture(TEXTURE, uv);
	// Rumpf: Wasserlinie mit leichter Kräuselung, weich
	float ripple = 0.006 * sin(UV.x * 38.0 + time_s * 1.7);
	float hull_a = 1.0 - smoothstep(-0.004, 0.012, -(above + ripple));
	float wet = smoothstep(0.16, 0.0, above) * 0.45;
	vec3 hull = mix(tex.rgb, tex.rgb * water_tint * 2.2, wet);
	// Spiegelbild: nur über der Wasserlinie, nach unten auslaufend, in waagerechte Streifen gebrochen
	float streak = 0.62 + 0.38 * sin(UV.y * 420.0 + time_s * 3.1 + sin(UV.x * 23.0) * 2.0);
	float refl_a = step(0.0, above) * (1.0 - smoothstep(0.0, 1.0, d)) * refl_alpha * streak;
	vec3 refl = mix(tex.rgb, water_tint, 0.35) * 0.72;   // dunkler als das Wasser, sonst kaum sichtbar
	vec3 c = mix(hull, refl, reflection);
	float a = tex.a * mix(hull_a, refl_a, reflection);
	COLOR = vec4(c * vcol.rgb, a * vcol.a);
}
