// Bildrand leicht abdunkeln und kühl tönen (gemalte Bildwirkung, lenkt den Blick zur Mitte)
shader_type canvas_item;

uniform float strength = 0.55;
uniform vec3 tint = vec3(0.02, 0.05, 0.08);

void fragment() {
	vec2 d = (UV - vec2(0.5, 0.46)) * vec2(1.0, 1.25);
	float v = smoothstep(0.38, 0.85, length(d));
	COLOR = vec4(tint, v * strength);
}
