// Letzte Ebene über allem (CanvasLayer 100): Bild und Oberfläche liegen als Schwarz/Weiß vor und werden
// hier auf genau zwei Farben gesetzt (Schwelle 0,5). Palette als Uniform: umschaltbar wie Monitorfarben.
// gray_preview = 1 zeigt Grautöne linear gemischt (nur zum Abstimmen der Tonkurve).
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest, repeat_disable;
uniform vec4 ink : source_color = vec4(0.11, 0.09, 0.16, 1.0);
uniform vec4 paper : source_color = vec4(0.94, 0.89, 0.78, 1.0);
uniform float gray_preview = 0.0;

void fragment() {
	float v = texture(screen_tex, SCREEN_UV).r;
	if (gray_preview > 0.5) {
		COLOR = vec4(mix(ink.rgb, paper.rgb, v), 1.0);
	} else {
		COLOR = v > 0.5 ? paper : ink;
	}
}
