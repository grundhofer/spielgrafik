shader_type canvas_item;
// Stehendes VN-Sprite: Überblendung zwischen zwei Mimik-Fassungen (gleiche Silhouette, nur das Gesicht
// unterscheidet sich), Abendtönung und warmes Kantenlicht von der Seite des Horizonts.
// TEXTURE ist die aktuelle Fassung, tex_b die nächste; mix_b blendet über.

uniform sampler2D tex_b : filter_linear, repeat_disable;
uniform float mix_b = 0.0;
uniform vec3 tint = vec3(1.0);            // Multiplikation (Abendlicht)
uniform vec3 shadow_tint = vec3(1.0);     // dunkle Töne kühler
uniform vec3 rim_color = vec3(1.0, 0.72, 0.5);
uniform float rim = 0.0;                  // Stärke des Kantenlichts (additiv)
uniform vec2 rim_dir = vec2(1.0, -0.4);   // Richtung zum Licht (Bildschirm)
uniform float rim_px = 5.0;               // Kantenlicht reicht so weit von der Silhouette nach innen (Texel)
uniform float line_px = 2.5;              // Breite der dunklen Außenkontur (Texel): dort kein Kantenlicht
uniform float line_lum = 0.2;             // dunklere Pixel sind Linien (Kontur, Innenlinien) und bleiben dunkel

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

void fragment() {
	vec4 a = texture(TEXTURE, UV);
	vec4 b = texture(tex_b, UV);
	vec4 c = mix(a, b, mix_b);
	// Abendtönung: helle Töne warm, dunkle Töne kühl (wie ein Overlay im VN-Skript)
	float lum = dot(c.rgb, vec3(0.299, 0.587, 0.114));
	vec3 col = c.rgb * mix(shadow_tint, tint, smoothstep(0.15, 0.75, lum));
	// Kantenlicht nur innerhalb der Kontur: Richtung Licht liegt nach line_px noch Figur (der Pixel gehört nicht
	// zur Außenkontur), nach rim_px aber schon Transparenz; Linienpixel (dunkel) bleiben unverändert.
	vec2 d = normalize(rim_dir) * TEXTURE_PIXEL_SIZE;
	float inside = texture(TEXTURE, UV + d * line_px).a;
	float outside = 1.0 - texture(TEXTURE, UV + d * rim_px).a;
	float notline = smoothstep(line_lum, line_lum + 0.12, lum);
	float edge = clamp(outside, 0.0, 1.0) * inside * notline * c.a;
	col += rim_color * edge * rim;
	COLOR = vec4(col, c.a) * vcol;
}
