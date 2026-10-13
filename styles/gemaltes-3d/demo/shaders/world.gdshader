// Hafen und Dachs: Farbvorlage für die Nachbearbeitung, keine Texturen.
// Der Shader liefert, was ein Maler vor dem Malen festlegt: klare Licht- und Schattenformen
// (weicher Zweiton statt Lambert-Verlauf, warmes Licht, kühle violette Schatten aus dem
// Umgebungslicht), große Farbflecken und kleinere Tupfer auf jeder Fläche, aus denen der
// Kuwahara-Filter später Pinselflächen macht. Kein Glanz. Das Kaipflaster (paving = 1) wird als
// lockere Pflastersteine angedeutet, statt das modellierte Fugenraster zu zeigen.
// Für die Steuerkamera gibt er stattdessen die Steuerwerte aus (paint_common.gdshaderinc).
shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_disabled;

#include "res://shaders/paint_common.gdshaderinc"

uniform vec3 albedo : source_color = vec3(0.6);
uniform float variation = 0.14;          // Helligkeitsschwankung der großen Flecken (Anteil)
uniform float var_scale = 1.1;           // Größe der Flecken in Metern
uniform float temp_shift = 0.06;         // Flecken etwas wärmer bzw. kühler
uniform float dab_amount = 0.10;         // kleinere Tupfer (Helligkeit und Farbton)
uniform float dab_scale = 0.22;          // Größe der Tupfer in Metern
uniform vec3 emission_color : source_color = vec3(0.0);
uniform float emission_energy = 0.0;
uniform float wrap = 0.3;                // Licht greift um die Form herum
uniform float terminator = 0.3;          // Breite des Übergangs Licht/Schatten (0 = harte Kante)
uniform vec3 rim_color : source_color = vec3(1.0, 0.7, 0.45);
uniform float rim = 0.0;                 // warme Lichtkante (Figur)
uniform float paving = 0.0;              // 1 = Kaipflaster: Oberseiten flach beleuchtet, Steine angedeutet
uniform float paving_cell = 0.5;         // m
uniform float ctrl_size = 0.5;           // Steuerkarte R: Pinselgröße
uniform float ctrl_edge = 0.5;           // Steuerkarte B: Kantenstärke
uniform float stroke_cell_px = 2.4;      // Zellgröße des Strichrauschens in Pixeln (Borsten)
uniform float dab_cell_px = 6.0;         // grobe Zellen: ein Pinseltupfer breit
uniform float dab_weight = 0.6;

varying float is_ctrl;
varying vec3 world_pos;

void vertex() {
	is_ctrl = (CAMERA_VISIBLE_LAYERS & CTRL_LAYER_BIT) != 0u ? 1.0 : 0.0;
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
}

// Pflastersteine: Voronoi-Zellen in Weltkoordinaten (x, z); Rückgabe: Zufall der Zelle, Abstand zur Fuge
vec2 cobble(vec2 x) {
	vec2 n = floor(x);
	vec2 f = fract(x);
	float d1 = 8.0;
	float d2 = 8.0;
	float id = 0.0;
	for (int j = -1; j <= 1; j++) {
		for (int i = -1; i <= 1; i++) {
			vec2 g = vec2(float(i), float(j));
			vec2 o = vec2(hash12(n + g), hash12(n + g + 19.7)) * 0.8 + 0.1;
			vec2 r = g + o - f;
			float d = dot(r, r);
			if (d < d1) {
				d2 = d1;
				d1 = d;
				id = hash12(n + g + 3.3);
			} else if (d < d2) {
				d2 = d;
			}
		}
	}
	return vec2(id, sqrt(d2) - sqrt(d1));
}

void fragment() {
	// UVs der gemeinsamen Modelle sind in Metern (1 UV-Einheit = 1 m)
	vec2 p = UV;
	vec3 world_n = normalize((INV_VIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	// Kai: alles oberhalb der Pflasterunterkante (Steinoberseiten, Fasen, Fugen, Kantensteine)
	float is_pave = paving * step(-0.02, world_pos.y);
	if (is_pave > 0.5) {
		p = world_pos.xz;
	}
	float n = fbm2(p / var_scale);
	float n2 = vnoise2(p / (var_scale * 0.45) + vec2(7.3, 2.1));
	float d = vnoise2(p / dab_scale + vec2(1.3, 8.4));
	float d2 = vnoise2(p / (dab_scale * 0.7) + vec2(5.9, 0.7));
	vec3 col = albedo * (1.0 + variation * 2.0 * (n - 0.5) + dab_amount * 2.0 * (d - 0.5));
	col += (temp_shift * (n2 - 0.5) + dab_amount * 0.5 * (d2 - 0.5)) * vec3(1.0, 0.25, -0.7);

	if (is_pave > 0.5) {
		// Steine: jede Zelle eigene Helligkeit/Wärme, Fuge nur leicht dunkler
		vec2 cb = cobble(world_pos.xz / paving_cell * vec2(1.0, 1.6));
		col *= 0.86 + 0.28 * cb.x;
		col += (hash12(vec2(cb.x * 91.0, 3.0)) - 0.5) * 0.06 * vec3(1.0, 0.3, -0.6);
		col *= mix(0.72, 1.0, smoothstep(0.02, 0.12, cb.y));
		// flach beleuchten: Fasen und Fugen des Modells sollen kein Raster zeichnen
		NORMAL = normalize((VIEW_MATRIX * vec4(0.0, 1.0, 0.0, 0.0)).xyz);
	}
	col = clamp(col, 0.0, 1.0);
	float rim_f = pow(clamp(1.0 - abs(dot(NORMAL, VIEW)), 0.0, 1.0), 3.0) * rim;
	float sn = stroke_noise2(p, stroke_cell_px, dab_cell_px, dab_weight);

	ALBEDO = col * (1.0 - is_ctrl);
	ROUGHNESS = 1.0;
	SPECULAR = 0.0;
	vec3 emit = emission_color * emission_energy + rim_color * rim_f * col;
	EMISSION = mix(emit, vec3(ctrl_size, sn, ctrl_edge), is_ctrl);
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float w = (ndl + wrap) / (1.0 + wrap);
	float lit = smoothstep(0.5 - terminator * 0.5, 0.5 + terminator * 0.5, w);
	// Schlagschatten weich in die Form übernehmen
	float sh = LIGHT_IS_DIRECTIONAL ? smoothstep(0.1, 0.9, ATTENUATION) : ATTENUATION;
	DIFFUSE_LIGHT += (1.0 - is_ctrl) * LIGHT_COLOR * lit * sh / PI;
}
