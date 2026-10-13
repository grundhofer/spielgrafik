// Dachs-Schnittfigur im Raum: Teilbild auf einem Viereck, Umgebungstönung (Dämmerung) und zwei Lichtkanten aus dem
// Alpha: warmes Laternenlicht von der Seite der Laterne, schwaches Abendlicht von oben. Kein Tiefentest (vor dem
// Dachs liegt nichts; so sinken die Füße nicht in Unebenheiten des Reliefs ein), Reihenfolge über render_priority.
shader_type spatial;
render_mode unshaded, cull_disabled, depth_test_disabled, depth_draw_never, blend_mix, shadows_disabled, fog_disabled;

uniform sampler2D tex : source_color, filter_linear_mipmap, repeat_disable;
uniform vec2 texel = vec2(0.005);
uniform vec3 ambient = vec3(0.74, 0.76, 0.9);
uniform float shade = 1.0;
uniform vec2 lamp_dir = vec2(-0.7, -0.7);     // Richtung zur Laterne im Teilbild (y nach unten)
uniform float lamp_strength = 0.0;
uniform vec3 lamp_color = vec3(1.0, 0.64, 0.32);
uniform float sky_rim = 0.0;                  // Abendlicht von oben
uniform vec3 sky_color = vec3(0.95, 0.6, 0.45);
uniform float rim_cut = 1.0;                  // unterhalb dieser v-Koordinate keine Lichtkanten (Schnittkante)
uniform float alpha_mul = 1.0;

void fragment() {
	vec4 c = texture(tex, UV);
	vec3 col = c.rgb * ambient * shade;
	// Abtastungen außerhalb jeder Verzweigung (sonst fehlen die Ableitungen für die Mipmap-Stufe und an der Grenze
	// entsteht ein heller Strich)
	float a_l = texture(tex, UV + normalize(lamp_dir) * texel * 3.5).a;
	float a_t = texture(tex, UV + vec2(0.0, -1.0) * texel * 3.0).a;
	float on = step(UV.y, rim_cut);
	col += lamp_color * clamp(c.a - a_l, 0.0, 1.0) * lamp_strength * on;
	col += sky_color * clamp(c.a - a_t, 0.0, 1.0) * sky_rim * on;
	ALBEDO = col;
	ALPHA = c.a * alpha_mul;
}
