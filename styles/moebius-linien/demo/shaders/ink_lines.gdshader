// Tuschelinien als Nachbearbeitung (Forward+): ein bildschirmfüllendes Rechteck vor der Kamera
// (QuadMesh 2×2, POSITION im Clip-Raum) liest Tiefe, Normalen und Material-ID der deckenden
// Geometrie und zeichnet schwarze Linien
//  - an Tiefensprüngen (Silhouetten, 2 px nah, 1 px fern; siehe ink_lines_common.gdshaderinc),
//  - an Knicken (Normalen weichen um mehr als crease_threshold ab; Falten, Kanten, Felsfacetten),
//  - an Farbgrenzen (Material-ID in ROUGHNESS, siehe ink.gdshader),
//  - auf der Figur zusätzlich Faltenlinien: schon 1 cm Tiefensprung und schwache Wölbungsknicke
//    zählen, damit Schalende, Ärmel und Schulter wie gezeichnet abgesetzt sind.
// Dazu Papierkorn über das ganze Bild. Mobile/Compatibility haben keinen Normalenpuffer: dort setzt
// main.gd ink_lines_depth.gdshader ein (nur Silhouetten).
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/ink_lines_common.gdshaderinc"

uniform sampler2D nr_tex : hint_normal_roughness_texture, filter_nearest, repeat_disable;
uniform float crease_threshold = 0.3;   // 1 - N·N
uniform float inner_width = 1.25;       // Abtastabstand der Innenlinien in Pixeln
uniform float id_lines = 1.0;           // Vergleichsschalter --no-ids
uniform int figure_min_id = 16;         // Material-IDs der Figur (ink.gdshader, main.gd: BADGER_PALETTE)
uniform float figure_gap = 0.01;        // m: auf der Figur zählen schon kleine Tiefensprünge (Schal vor Weste)
uniform float fold_threshold = 0.03;    // Faltenlinien der Figur: schwache Knicke, nur wo die Fläche sich wölbt
uniform float fold_lines = 1.0;         // Vergleichsschalter --no-folds
uniform float debug = 0.0;              // 1 = Linienarten als Farben (rot Silhouette, grün Knick, blau ID)

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

int id_at(vec2 uv) {
	float w = texture(nr_tex, uv).a;
	if (w > 0.5) {
		w = 1.0 - w;   // Godot kodiert dynamische Objekte als 1 - Rauheit (7 Bit); Befund aus toon-cel
	}
	w /= (127.0 / 255.0);
	return int(floor(w * 32.0));
}

vec3 normal_at(vec2 uv) {
	return normalize(texture(nr_tex, uv).xyz * 2.0 - 1.0);
}

void fragment() {
	vec2 px = 1.0 / VIEWPORT_SIZE;
	vec2 uv = snap_uv(wobble_uv(SCREEN_UV, px, FRAGCOORD.xy), VIEWPORT_SIZE);
	float zc = lin_z(uv, INV_PROJECTION_MATRIX);
	float sky = step(2900.0, zc);   // Kamera far = 3000 m; unabhängig von der Tiefenrichtung des Renderers
	int ic = id_at(uv);
	float gap = (ic >= figure_min_id) ? figure_gap : min_gap;
	float e = silhouette(uv, VIEWPORT_SIZE, zc, INV_PROJECTION_MATRIX, gap);
	float e_in = 0.0;
	float dbg_c = 0.0;
	float dbg_i = 0.0;

	// Knicke und Farbgrenzen: nur zur rechten und unteren Seite prüfen (sonst doppelt breit);
	// Nachbarn deutlich weiter hinten gehören zur Silhouette und sind oben schon erfasst.
	vec3 nc = normal_at(uv);
	vec2 offs[2] = {vec2(px.x * inner_width, 0.0), vec2(0.0, px.y * inner_width)};
	for (int k = 0; k < 2; k++) {
		vec2 un = uv + offs[k];
		float zn = lin_z(un, INV_PROJECTION_MATRIX);
		if (zn > 2900.0) {
			continue;
		}
		if (abs(zn - zc) > 0.08 * zc) {
			continue;
		}
		vec3 nn = normal_at(un);
		float cr = smoothstep(crease_threshold, crease_threshold * 1.4, 1.0 - dot(nc, nn));
		// Faltenlinien nur auf der Figur: dreht sich die Fläche in Laufrichtung vom Blick weg (Wölbung:
		// nach rechts nimmt x der Sichtraum-Normale zu, nach unten nimmt y ab), genügt ein schwacher
		// Knick. So bekommen Schalende, Ärmel und Schulter Linien wie gezeichnete Falten; Mulden geben
		// am Modell kaum etwas her (ausprobiert).
		float bulge = (k == 0) ? (nn.x - nc.x) : (nc.y - nn.y);
		if (fold_lines > 0.5 && ic >= figure_min_id && bulge > 0.0) {
			cr = max(cr, smoothstep(fold_threshold, fold_threshold * 1.5, 1.0 - dot(nc, nn)));
		}
		e_in = max(e_in, cr);
		dbg_c = max(dbg_c, cr);
		if (id_lines > 0.5 && id_at(un) != ic) {
			e_in = 1.0;
			dbg_i = 1.0;
		}
	}
	e = max(e, e_in * inner_alpha);
	vec4 c = compose(SCREEN_UV, FRAGCOORD.xy, e, zc, sky);
	if (debug > 0.5) {
		c.rgb = vec3(silhouette(uv, VIEWPORT_SIZE, zc, INV_PROJECTION_MATRIX, gap), dbg_c, dbg_i) * (1.0 - sky);
	}
	ALBEDO = c.rgb;
	ALPHA = 1.0;
}
