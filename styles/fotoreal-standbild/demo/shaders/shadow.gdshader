shader_type canvas_item;
render_mode blend_mul;
// Schatten des Dachses auf dem Kai, multiplikativ: R Kontaktschatten (Umgebungslicht, immer da),
// G Schlagschatten von der Laterne weg (stärker, wenn die Laterne heller brennt).
uniform float contact_k = 0.55;
uniform float cast_k = 0.30;
uniform float lantern = 1.0;
uniform vec3 tint = vec3(0.85, 0.9, 1.0);   // Schatten im Blaulicht leicht kühl
uniform bool enabled = true;

void fragment() {
	vec4 s = texture(TEXTURE, UV);
	float dark = enabled ? clamp(s.r * contact_k + s.g * cast_k * lantern, 0.0, 0.85) : 0.0;
	COLOR = vec4(mix(vec3(1.0), vec3(1.0) - tint, dark), 1.0);
}
