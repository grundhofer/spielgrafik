shader_type spatial;
// Voxel-Material: flache Farbe je Voxel aus der Vertexfarbe (sRGB-Werte, hier nach linear umgerechnet),
// Voxel-AO je Flächenecke im Alphakanal (0, 1/3, 2/3, 1 -> Helligkeit 0,38 ... 1,0).
// Dezente Voxelkante: jede Würfelfläche hat UV 0..1; ein schmaler Rand wird etwas dunkler (wie die
// Kantenoption in Voxel-Renderern). Wird die Fläche auf dem Bild kleiner als etwa 7 px, blendet die Kante
// aus (sonst Moiré). Emission (Glas) als Faktor auf die Voxelfarbe. use_color: feste Farbe (Rauch).
render_mode cull_back;

uniform float ao_strength : hint_range(0.0, 1.0) = 1.0;
uniform float edge_strength : hint_range(0.0, 1.0) = 0.32;
uniform float edge_width = 0.07;
uniform float emission_energy = 0.0;
uniform float roughness_v : hint_range(0.0, 1.0) = 0.9;
uniform float use_color = 0.0;
uniform vec4 flat_color : source_color = vec4(1.0);

vec3 srgb_to_linear(vec3 c) {
	return mix(pow((c + vec3(0.055)) / vec3(1.055), vec3(2.4)), c / vec3(12.92), lessThan(c, vec3(0.04045)));
}

void fragment() {
	vec3 c = use_color > 0.5 ? flat_color.rgb : srgb_to_linear(COLOR.rgb);
	float ao = use_color > 0.5 ? 1.0 : clamp(COLOR.a, 0.0, 1.0);
	float aof = mix(1.0, mix(0.38, 1.0, ao), ao_strength);
	vec2 e2 = min(UV, 1.0 - UV);
	float e = min(e2.x, e2.y);
	float w = max(fwidth(UV.x), fwidth(UV.y));
	float edge = 1.0 - smoothstep(edge_width - w, edge_width + w, e);
	edge *= 1.0 - smoothstep(0.09, 0.16, w);
	ALBEDO = c * aof * (1.0 - edge_strength * edge);
	ROUGHNESS = roughness_v;
	SPECULAR = 0.25;
	EMISSION = c * emission_energy * (1.0 - 0.6 * edge);
}
