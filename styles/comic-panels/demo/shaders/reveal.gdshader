// Panel erscheint: Papierfläche mit wachsenden Löchern auf einem 45°-Raster (große Rasterpunkte), von links oben
// nach rechts unten. progress 0 = ganz Papier, 1 = Panel ganz sichtbar.
shader_type canvas_item;

uniform vec2 rect_size = vec2(400.0, 300.0);
uniform float progress = 0.0;
uniform float cell = 26.0;

void fragment() {
	vec2 p = UV * rect_size;
	vec2 q = vec2(p.x + p.y, p.y - p.x) * 0.70710678 / cell;
	vec2 c = floor(q) + 0.5;
	float diag = (UV.x + UV.y) * 0.5;
	float local = clamp(progress * 1.7 - diag * 0.7, 0.0, 1.0);
	float r = local * 0.75;
	float d = length(q - c);
	float hole = 1.0 - smoothstep(r - 0.04, r + 0.04, d);
	COLOR = vec4(1.0, 1.0, 1.0, 1.0 - hole);
}
