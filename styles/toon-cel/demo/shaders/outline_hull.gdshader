// Umgedrehte Hülle (inverted hull) für die Figur: zweiter Durchgang (next_pass) mit
// cull_front; jeder Eckpunkt wird im Bildraum entlang seiner projizierten Normale um
// width_px Pixel nach außen geschoben. Die Linie ist so unabhängig vom Abstand gleich breit.
// Die Normalen des Dachses sind weich (siehe shared/3d/badger_notes.md), die Hülle hat deshalb
// nur an Tasche, Paket und Mützenschirm kleine Lücken; dort greift die Nachbearbeitung.
shader_type spatial;
render_mode unshaded, cull_front, depth_draw_opaque, fog_disabled, shadows_disabled;

uniform vec4 ink : source_color = vec4(0.11, 0.07, 0.16, 1.0);
uniform float width_px = 2.5;
uniform float max_world = 0.012;  // m: Obergrenze; in der Totale (14 mm je Pixel) wird die Hülle so unter 1 px schmal
uniform int material_id = 15;

void vertex() {
	vec4 clip = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	vec3 n_view = normalize(MODELVIEW_NORMAL_MATRIX * NORMAL);
	vec2 n_clip = (PROJECTION_MATRIX * vec4(n_view, 0.0)).xy;
	float len = length(n_clip);
	if (len > 0.0001) {
		n_clip /= len;
	}
	// Pixel -> Clip-Raum: 2 / Bildgröße, mal w für die perspektivische Teilung
	vec2 off = n_clip * width_px * 2.0 / VIEWPORT_SIZE * clip.w;
	// Obergrenze in Metern: dieselbe Verschiebung in Weltmaßen (Abstand · Pixelwinkel)
	float px_m = clip.w * 2.0 / (VIEWPORT_SIZE.y * PROJECTION_MATRIX[1][1]);
	float scale = min(1.0, max_world / max(px_m * width_px, 0.00001));
	clip.xy += off * scale;
	POSITION = clip;
}

void fragment() {
	ALBEDO = ink.rgb;
	ROUGHNESS = (float(material_id) + 0.5) / 16.0;
}
