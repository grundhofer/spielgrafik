// Konturen als Nachbearbeitung (Forward+): ein bildschirmfüllendes Rechteck (QuadMesh 2×2 vor der
// Kamera) liest Tiefe, Normalen und Material-ID der deckenden Geometrie und zeichnet Linien
//  - an Tiefensprüngen (Silhouetten, siehe outline_common.gdshaderinc),
//  - an Knicken (Normalen weichen um mehr als normal_threshold ab),
//  - an Farbgrenzen (Material-ID in ROUGHNESS, siehe toon.gdshader).
// Linienfarbe = abgedunkelte Farbe darunter, gemischt mit Tinte. Mobile/Compatibility haben keinen
// Normalenpuffer: dort setzt main.gd outline_post_depth.gdshader ein (nur Silhouetten).
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#include "res://shaders/outline_common.gdshaderinc"

uniform sampler2D nr_tex : hint_normal_roughness_texture, filter_nearest, repeat_disable;
uniform float normal_threshold = 0.35;  // 1 - N·N
uniform float id_lines = 1.0;

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

int id_at(vec2 uv) {
	float w = texture(nr_tex, uv).a;
	if (w > 0.5) {
		w = 1.0 - w;   // Godot kodiert "dynamisches Objekt" als 1 - Rauheit
	}
	w /= (127.0 / 255.0);
	return int(floor(w * 16.0));
}

vec3 normal_at(vec2 uv) {
	return normalize(texture(nr_tex, uv).xyz * 2.0 - 1.0);
}

void fragment() {
	float zc;
	vec3 wc;
	vec2 ox;
	vec2 oy;
	float sky;
	float e = silhouette(SCREEN_UV, VIEWPORT_SIZE, INV_PROJECTION_MATRIX, INV_VIEW_MATRIX, zc, wc, ox, oy, sky);

	// Knicke und Farbgrenzen: nur zur rechten/unteren Seite prüfen (sonst doppelt breit);
	// Nachbarn, die deutlich weiter hinten liegen, gehören zur Silhouette und sind oben schon erfasst.
	vec3 nc = normal_at(SCREEN_UV);
	int ic = id_at(SCREEN_UV);
	vec2 offs[2] = {ox, oy};
	for (int k = 0; k < 2; k++) {
		vec2 uv = SCREEN_UV + offs[k];
		float dn = depth_at(uv);
		if (dn <= 0.0000001) {
			continue;
		}
		float zn = -view_pos(uv, dn, INV_PROJECTION_MATRIX).z;
		if (abs(zn - zc) > 0.08 * zc) {
			continue;
		}
		vec3 nn = normal_at(uv);
		e = max(e, step(normal_threshold, 1.0 - dot(nc, nn)));
		if (id_lines > 0.5 && id_at(uv) != ic) {
			e = max(e, 1.0);
		}
	}
	ALBEDO = line_color(SCREEN_UV);
	ALPHA = finish(e, zc, wc, sky);
}
