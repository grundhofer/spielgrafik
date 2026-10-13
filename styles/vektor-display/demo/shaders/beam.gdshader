// Elektronenstrahl: jede Linie ist ein Band aus Dreiecken, UV.x quer (-1..1), UV.y an den Enden (0..1).
// Helligkeit und Farbe kommen als Vertexfarbe (HDR, darf > 1 sein). Additiv in den Phosphorpuffer.
shader_type canvas_item;
render_mode blend_add, unshaded;

uniform float core_sigma = 0.2;   // Strahlkern, in Einheiten des Bandradius
uniform float halo_sigma = 0.55;  // enger Lichthof des Phosphors (der weite kommt vom Glow)
uniform float halo_gain = 0.22;
uniform float whiten = 0.5;       // helle Kerne werden weiß (überbelichteter Phosphor)

void fragment() {
	float d2 = dot(UV, UV);
	float core = exp(-d2 / (2.0 * core_sigma * core_sigma));
	float halo = exp(-d2 / (2.0 * halo_sigma * halo_sigma));
	vec3 c = COLOR.rgb;
	float peak = max(c.r, max(c.g, c.b));
	vec3 col = c * (core + halo_gain * halo) + vec3(peak) * whiten * core * core;
	COLOR = vec4(col, 1.0);
}
