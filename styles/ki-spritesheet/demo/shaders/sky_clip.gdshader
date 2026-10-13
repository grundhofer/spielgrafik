shader_type canvas_item;
// Möwen nur vor freiem Himmel: G von bg_mask.png (prep_bg.py, Flutfüllung von oben, die an den dunklen
// Konturen stoppt). Dach, Schornstein, Leuchtturm, Felsen, Laterne und Pfahl liegen außerhalb, die Möwen
// fliegen also hinter ihnen durch. Abgetastet wird an der Lage im Bild (Hintergrund liegt bei 0,0 in 1280×720),
// nicht an SCREEN_UV, damit es auch bei anderer Fenstergröße stimmt.

uniform sampler2D mask_tex : filter_nearest;
varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float sky = texture(mask_tex, world / vec2(1280.0, 720.0)).g;
	COLOR.a *= sky;
}
