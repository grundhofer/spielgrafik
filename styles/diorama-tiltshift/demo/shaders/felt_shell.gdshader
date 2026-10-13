// Streugras/Filz als Schalen (shell texturing): dieselbe Fläche mehrfach, jede Schale ein Stück entlang der
// Normale angehoben; nur Pixel, in denen eine "Faser" so hoch reicht, bleiben stehen. Ergibt den flauschigen
// Rand von Modellbau-Streugras. main.gd hängt shells Kopien als next_pass an das Grasmaterial.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://shaders/dio_noise.gdshaderinc"

uniform vec4 albedo : source_color = vec4(0.4, 0.55, 0.25, 1.0);
uniform vec4 tip : source_color = vec4(0.7, 0.75, 0.4, 1.0);
uniform float layer = 0.5;          // 0..1 (Anteil der Faserhöhe)
uniform float height = 0.06;        // m, volle Faserhöhe
uniform float density = 55.0;       // Fasern je m
uniform float fade_near = 25.0;     // ab hier dünnt der Flaum aus (sonst flimmert er in der Totale)
uniform float fade_far = 60.0;

varying vec3 obj_pos;
varying float up;

void vertex() {
	obj_pos = VERTEX;
	VERTEX += NORMAL * height * layer;
	up = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz).y;
}

void fragment() {
	vec3 cell = floor(obj_pos * density);
	vec3 f = fract(obj_pos * density) - 0.5;
	float h = dio_hash13(cell);                 // Länge dieser Faser
	float r = length(f.xz);
	float d = length(VERTEX);
	float far = smoothstep(fade_near, fade_far, d);
	// Faser verjüngt sich nach oben; nur auf flachen Flächen (Gras), an steilen Kanten kürzer
	float len = h * mix(0.4, 1.0, smoothstep(0.55, 0.9, up));
	float thick = mix(0.45, 0.15, layer);
	if (layer > len * (1.0 - far) || r > thick) {
		discard;
	}
	float shade = mix(0.55, 1.0, layer) * (0.85 + 0.3 * dio_hash13(cell + 7.0));
	ALBEDO = mix(albedo.rgb, tip.rgb, layer * layer) * shade;
	ROUGHNESS = 1.0;
	SPECULAR = 0.1;
	RIM = 0.6;
	RIM_TINT = 0.7;
}
