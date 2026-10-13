shader_type spatial;
// Fell als Schalen ("shell fur"): main.gd kopiert die Fellflächen des Dachses N-mal in ein eigenes,
// genauso geskinntes Mesh. COLOR.r = Höhe der Schale (0..1), COLOR.g = Fellänge an dieser Stelle
// (kurz im Gesicht, um die Augen fast null). Die Schale wird entlang der (bereits geskinnten)
// Normale nach außen geschoben und leicht nach unten gekämmt. Im Fragment entscheidet ein Raster
// in UV-Metern, ob hier ein Haar steht (dünner werdend nach oben, zufällige Länge).
render_mode cull_back, depth_draw_opaque;

uniform vec3 fur_color : source_color = vec3(0.29, 0.25, 0.23);
uniform vec3 tip_color : source_color = vec3(0.45, 0.42, 0.40);
uniform float fur_len = 0.012;        // Meter
uniform float density = 240.0;        // Haare je Meter (Rasterweite ~4 mm)
uniform float gravity = 0.45;
uniform float thickness = 0.9;
uniform float root_dark = 0.45;

varying float v_h;
varying float v_len;

void vertex() {
	v_h = COLOR.r;
	v_len = COLOR.g;
	float L = fur_len * v_len;
	VERTEX += NORMAL * L * v_h + vec3(0.0, -1.0, 0.0) * L * gravity * v_h * v_h;
}

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void fragment() {
	vec2 cell = UV * density;
	vec2 id = floor(cell);
	vec2 f = fract(cell) - 0.5;
	vec2 c = vec2(hash(id), hash(id + 17.31)) - 0.5;
	float d = length(f - c * 0.45);
	float len = 0.45 + 0.55 * hash(id + 3.17);
	float rel = v_h / len;
	float r = 0.5 * thickness * (1.0 - rel);
	if (v_len < 0.02 || rel > 1.0 || d > r) {
		discard;
	}
	float occ = mix(root_dark, 1.0, v_h);
	vec3 col = mix(fur_color, tip_color, smoothstep(0.45, 1.0, rel)) * (0.82 + 0.36 * hash(id + 9.0));
	ALBEDO = col * occ;
	ROUGHNESS = 0.72;
	SPECULAR = 0.3;
	AO = occ;
	AO_LIGHT_AFFECT = 0.4;
	RIM = 0.5;
	RIM_TINT = 0.7;
}
