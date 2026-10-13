// Handbemalte Figur (Dachs-Kurier) ohne eigene Textur: die "aufgemalte" Beleuchtung entsteht im Shader.
//  - Farbe je Material (kräftige, warme Palette in main.gd)
//  - Pinseltupfer: weiche Flecken aus brush.png über die Mesh-UVs (1 UV-Einheit = 1 m), ±brush_amount
//  - Verlauf über die Höhe der Figur: Füße dunkler und violetter, Kopf heller (wie aufgemalt)
//  - Unterseiten dunkler (gemalte Verdeckung), Oberseiten wärmer
//  - gebackene Verdeckung aus Blender (Vertexfarbe, blender/bake_badger_ao.py): violett in Falten, unter Schal
//    und Mütze, zwischen Arm und Körper (R nah, G fern), wie die Fugen am Hafen
//  - aufgemalte helle Oberkante: Flächen, die nach oben kippen (Mützendeckel, Schultern, Paketoberseite);
//    dunkle, violette Formkante an der lichtabgewandten Silhouette
//  - Licht: in 4 weichen Stufen (dunkel kühl, hell warm) statt stufenlos, ohne Glanz, Schlagschatten violett
//    getönt; Lichtkante (Rim) in Abendorange
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert, specular_disabled;

uniform vec3 albedo : source_color = vec3(1.0);
uniform sampler2D brush : hint_default_white, filter_linear_mipmap, repeat_enable;
uniform float brush_scale = 1.6;       // Kacheln je Meter (Tupfer etwa 8 cm, bei 140 px Figur 10-12 px)
uniform float brush_amount = 0.38;
uniform float height_dark = 0.80;      // Helligkeit an den Füßen (Kopf = 1)
uniform vec3 low_tint : source_color = vec3(0.86, 0.80, 0.98);
uniform float under_dark = 0.22;
uniform vec3 rim_color : source_color = vec3(1.0, 0.68, 0.38);
uniform float rim_strength = 0.9;
uniform vec3 rim_dir = vec3(-0.75, 0.35, -0.55);   // Richtung, aus der die Lichtkante kommt (Welt)
uniform float wrap = 0.55;
uniform vec3 shadow_tint : source_color = vec3(0.62, 0.55, 0.85);
uniform float gloss = 0.0;             // gemalter Glanzpunkt (Messing, Nase, Augen)
uniform vec3 emission_color : source_color = vec3(0.0);
uniform bool has_ao = true;
uniform float ao_near = 1.0;
uniform float ao_far = 0.75;
uniform vec3 ao_tint : source_color = vec3(0.36, 0.24, 0.56);
uniform float ao_lo = 0.4;            // Verdeckung unter diesem Wert = volle Tönung
uniform float edge_paint = 0.5;        // gemalte dunkle Formkante an der lichtabgewandten Silhouette
uniform float top_edge = 0.55;
uniform vec3 top_color : source_color = vec3(1.0, 0.92, 0.74);
uniform float bands = 3.0;             // Stufen der Schattierung: 0, 1/3, 2/3, 1
uniform float band_soft = 0.22;        // Breite des weichen Übergangs (Anteil einer Stufe)
uniform vec3 band_cool = vec3(0.80, 0.80, 1.06);   // Farbe der dunklen Stufen
uniform vec3 band_warm = vec3(1.06, 0.99, 0.90);   // Farbe der hellen Stufen

varying float height01;
varying vec3 world_normal;

void vertex() {
	height01 = clamp(VERTEX.y / 1.0, 0.0, 1.0);
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	float b = texture(brush, UV * brush_scale).r;       // 0..1, Mittel 0,5
	vec3 col = albedo * (1.0 + brush_amount * (b - 0.5) * 2.0);
	// Höhenverlauf: unten dunkler und kühler
	float h = smoothstep(0.0, 0.95, height01);
	col *= mix(low_tint * height_dark, vec3(1.0), h);
	// Unterseiten dunkel, Oberseiten warm
	float ny = world_normal.y;
	col *= 1.0 - under_dark * clamp(-ny, 0.0, 1.0);
	col *= 1.0 + 0.10 * clamp(ny, 0.0, 1.0) * vec3(1.0, 0.92, 0.8);
	// gebackene Verdeckung, violett gemalt
	if (has_ao) {
		float occ = mix(1.0, COLOR.r, ao_near) * mix(1.0, COLOR.g, ao_far);
		occ = smoothstep(ao_lo, 1.0, occ);   // gespreizt: die Vorderseite ist kaum verdeckt, Falten sollen sitzen
		col *= mix(ao_tint, vec3(1.0), occ);
	}
	// aufgemalte helle Oberkante: am stärksten, wo die Form nach oben umkippt (Schulter, Mützenrand, Paketkante)
	float top = smoothstep(0.30, 0.62, ny) * (1.0 - 0.45 * smoothstep(0.82, 0.98, ny));
	if (has_ao) {
		top *= smoothstep(0.55, 0.85, COLOR.g);   // nicht in verdeckten Falten
	}
	col = mix(col, max(col * 1.55, col + vec3(0.06)) * top_color, top * top_edge);
	// Lichtkante (warm, zum Abendlicht) und gemalte dunkle Formkante (violett, auf der anderen Seite)
	vec3 n_view = NORMAL;
	float fres = 1.0 - clamp(dot(n_view, VIEW), 0.0, 1.0);
	float side = clamp(dot(world_normal, normalize(rim_dir)) * 0.9 + 0.45, 0.0, 1.0);
	col = mix(col, col * ao_tint, smoothstep(0.5, 0.85, fres) * (1.0 - side) * edge_paint);
	ALBEDO = col;
	ROUGHNESS = 1.0;
	METALLIC = 0.0;
	float rim = smoothstep(0.45, 0.75, fres) * side;
	// gemalter Glanzpunkt: harte, kleine Spitze zur Kamera-oben
	float g = gloss * smoothstep(0.82, 0.9, dot(n_view, normalize(VIEW + vec3(0.0, 0.6, 0.0))));
	EMISSION = rim_color * rim * rim_strength * (0.35 + 0.65 * col) + vec3(g) + emission_color;
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	if (LIGHT_IS_DIRECTIONAL) {
		float d = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0);
		d *= mix(0.55, 1.0, ATTENUATION);                    // Schlagschatten: eine Stufe tiefer
		float x = d * bands;
		float q = (floor(x) + smoothstep(0.5 - band_soft, 0.5 + band_soft, fract(x))) / bands;
		vec3 sh = mix(shadow_tint, vec3(1.0), ATTENUATION);
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * q * mix(band_cool, band_warm, q) * sh;
	} else {
		float d = clamp(ndl * 0.6 + 0.4, 0.0, 1.0);
		DIFFUSE_LIGHT += LIGHT_COLOR / PI * d * ATTENUATION;
	}
}
