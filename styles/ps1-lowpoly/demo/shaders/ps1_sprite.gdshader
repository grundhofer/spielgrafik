// Sprites im PS1-Stil: Rauchwölkchen (zur Kamera gedreht) und Rundschatten (liegend).
// Kleine Textur mit Nearest, 1-Bit-Alpha, Eckpunkte gerundet. Halbtransparenz nur als fester
// Mischmodus der Konsole (Hintergrund/2 + Sprite/2 bei tint.a = 0.5). Ausblenden nicht stufenlos,
// sondern per Raster (Bayer 4×4 auf Bildschirmpixel), wie es Spiele der Zeit oft taten.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_never, fog_disabled, shadows_disabled, blend_mix;

#include "res://shaders/ps1_common.gdshaderinc"

uniform sampler2D tex : source_color, filter_nearest;
uniform vec4 tint : source_color = vec4(1.0, 1.0, 1.0, 0.5);
uniform float visible = 1.0;      // 0..1: Anteil der Rasterpunkte, die gezeichnet werden
uniform bool billboard = true;
uniform bool lit = false;

varying vec3 v_light;
varying float v_fog;
varying flat float v_ot;                 // als Ganzes sortiert (Mittelpunkt)

void vertex() {
	vec3 center = (MODEL_MATRIX * vec4(0.0, 0.0, 0.0, 1.0)).xyz;
	vec4 view;
	if (billboard) {
		float sx = length(MODEL_MATRIX[0].xyz);
		float sy = length(MODEL_MATRIX[1].xyz);
		view = VIEW_MATRIX * vec4(center, 1.0);
		view.xy += VERTEX.xy * vec2(sx, sy);
	} else {
		view = MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	}
	v_light = lit ? ps1_light(center, normalize(CAMERA_POSITION_WORLD - center), 1.0) : vec3(1.0);
	v_fog = ps1_fog(-view.z);
	v_ot = -(VIEW_MATRIX * vec4(center, 1.0)).z;
	POSITION = ps1_snap(PROJECTION_MATRIX * view);
}

const float BAYER[16] = float[](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);

void fragment() {
	vec4 t = texture(tex, UV);
	ivec2 p = ivec2(FRAGCOORD.xy) % 4;
	if (t.a < 0.5 || visible * 16.0 <= BAYER[p.y * 4 + p.x]) {
		discard;
	}
	ALBEDO = mix(t.rgb * tint.rgb * v_light, ps1_fog_color.rgb, v_fog);
	ALPHA = tint.a;
	DEPTH = ps1_ot > 0.5 ? ps1_ot_depth(v_ot, PROJECTION_MATRIX) : FRAGCOORD.z;
}
