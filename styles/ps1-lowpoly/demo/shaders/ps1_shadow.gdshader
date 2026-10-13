// Rundschatten unter der Figur: 1-Bit-Kreis aus einer 16×16-Textur, liegend auf dem Boden, Eckpunkte
// gerundet, im Mischmodus "B/2 + F/2" der Konsole mit schwarzem F: Der Boden darunter wird halb so hell,
// das Pflaster bleibt erkennbar.
// Vorher subtraktiv (B − F). Auf dem abendlichen Pflaster (etwa 0,12 | 0,07 | 0,07 linear, Fugen 0,02) fielen
// bei einem Abzug von 0,08–0,10 Grün und Blau auf null, und unter den Füßen blieb ein schwarzer Streifen.
// Sortiert wird der Schatten wie der Kaiboden je Pixel (+0,28 m, knapp vor dem Boden mit +0,3 m): Er liegt
// immer über dem Boden und hinter den Füßen.
shader_type spatial;
render_mode blend_mix, unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled;

#include "res://shaders/ps1_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest;

varying float v_ot;

void vertex() {
	v_ot = -(MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).z + 0.28;
	POSITION = ps1_snap(PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0));
}

void fragment() {
	if (texture(tex, UV).a < 0.5) {
		discard;
	}
	ALBEDO = vec3(0.0);
	ALPHA = 0.5;            // B/2 + F/2 mit F = Schwarz
	DEPTH = ps1_ot > 0.5 ? ps1_ot_depth(v_ot, PROJECTION_MATRIX) : FRAGCOORD.z;
}
