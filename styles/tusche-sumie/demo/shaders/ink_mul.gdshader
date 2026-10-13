// Tusche-Ebene: multipliziert ihre Transmission (RGB) aufs Papier darunter, wie Tusche auf saugfähigem Papier.
// Deckung = Textur-Alpha * modulate.a * amount. Optional Pinsel-Aufzug von links nach rechts (reveal 0..1):
// jede "Borste" (Zeile) endet etwas anders, damit die Kante ausfranst. Optional nur der untere Teil der Textur
// (fade_top/fade_len in UV.y, z. B. fester Rauchansatz auf dem Schornstein); Standard: ganz sichtbar.
shader_type canvas_item;
render_mode blend_mul;

uniform float amount = 1.0;
uniform float reveal = 2.0;      // > 1: ganz sichtbar
uniform float reveal_soft = 0.06;
uniform float bristles = 36.0;
uniform float fade_top = -1.0;
uniform float fade_len = 0.25;

float hash(float n) { return fract(sin(n * 12.9898) * 43758.5453); }

void fragment() {
	float j = (hash(floor(UV.y * bristles)) - 0.5) * 0.08;
	float m = 1.0 - smoothstep(reveal - reveal_soft, reveal, UV.x + j);
	m *= smoothstep(fade_top, fade_top + fade_len, UV.y);
	float a = clamp(COLOR.a * amount * m, 0.0, 1.0);
	COLOR = vec4(mix(vec3(1.0), COLOR.rgb, a), 1.0);
}
