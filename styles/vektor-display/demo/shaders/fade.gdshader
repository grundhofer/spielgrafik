// Nachleuchten, Schritt 1: der Phosphorpuffer verliert jedes Bild einen festen Anteil (multiplikativ).
shader_type canvas_item;
render_mode blend_mul, unshaded;

uniform float keep = 0.6;

void fragment() {
	COLOR = vec4(vec3(keep), 1.0);
}
