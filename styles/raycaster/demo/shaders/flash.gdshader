// Aufblitzen beim Aufheben (wie der Palettenwechsel der Shooter): Die ganze Ausgabe, auch die
// Statusleiste, wird zur Palettenzeile 1 umgerechnet: floor(c·(1−f) + Gold·f + 0,5), f = 1/8.
// Dieselbe Rechnung erzeugt palette.png Zeile 1 (scripts/rc_palette.py), das Bild bleibt also
// genau in einer Palette.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float amount = 0.125;
uniform vec3 gold = vec3(215.0, 186.0, 69.0);

void fragment() {
	vec3 c = floor(texture(screen_tex, SCREEN_UV).rgb * 255.0 + 0.5);
	c = floor(c * (1.0 - amount) + gold * amount + 0.5);
	COLOR = vec4(c / 255.0, 1.0);
}
