// Lichtkegel des Leuchtturms wie gezeichnet: blasse, durchscheinende Fläche, die zum Ende ausläuft,
// und zwei Tuschelinien an den Rändern (dort, wo die Kegelwand quer zum Blick steht, N·V ≈ 0).
// cull_back: nur die vordere Hälfte, sonst addieren sich Vorder- und Rückwand.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_back, shadows_disabled, fog_disabled;

global uniform vec4 ink_color;   // linear (globale Farben werden nicht aus sRGB umgerechnet)

uniform vec4 fill : source_color = vec4(1.0, 0.97, 0.82, 0.55);
uniform float length_m = 30.0;
uniform float edge_px = 1.5;
uniform float intensity = 1.0;
uniform float lines_on = 1.0;

varying float along;

void vertex() {
	along = clamp(VERTEX.y / length_m + 0.5, 0.0, 1.0);   // 0 an der Lampe, 1 am fernen Ende
}

void fragment() {
	float ndv = abs(dot(normalize(NORMAL), normalize(VIEW)));
	float fw = max(fwidth(ndv), 1e-4);
	float edge = 1.0 - smoothstep(fw * edge_px * 0.6, fw * (edge_px * 0.6 + 1.0), ndv);
	edge *= (1.0 - smoothstep(0.55, 0.95, along)) * lines_on;
	float a = fill.a * intensity * pow(clamp(1.0 - along, 0.0, 1.0), 1.4);
	ALBEDO = mix(fill.rgb, ink_color.rgb, edge);
	ALPHA = clamp(max(a, edge * 0.9 * intensity), 0.0, 1.0);
}
