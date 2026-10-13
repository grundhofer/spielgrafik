// Schrift wird wie mit dem Pinsel geschrieben: Aufdecken von links nach rechts (Bildschirm-x), Kante je Zeile
// leicht versetzt. reveal_x < 0: verborgen, groß: ganz sichtbar.
shader_type canvas_item;

uniform float reveal_x = 99999.0;
uniform float soft = 40.0;
varying vec2 wpos;

float hash(float n) { return fract(sin(n * 12.9898) * 43758.5453); }

void vertex() {
	wpos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	float j = (hash(floor(wpos.y / 3.0)) - 0.5) * 18.0;
	float m = 1.0 - smoothstep(reveal_x - soft, reveal_x, wpos.x + j);
	COLOR.a *= m;
}
