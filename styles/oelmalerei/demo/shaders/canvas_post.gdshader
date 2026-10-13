// Nachbearbeitung nur für das Gemälde (nicht für das Dialogpanel):
// leichtes Pinselstrich-Flimmern (Boil), Leinwandstruktur, warme Vignette.
shader_type canvas_item;
#include "res://shaders/noise.gdshaderinc"

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float time_s = 0.0;
uniform float boil_fps = 6.0;
uniform float boil_px = 1.0;          // Sprungweite in ganzen Pixeln
// Kantenmaske (prep.py, step_edges): 1 = lange Linie/Kante (Mast, Leuchtturmkante), dort kein Sprung,
// sonst zerfallen solche Linien bei jedem Flimmerschritt zu Zickzack. Gilt für das Gemälde (1080 x 720 links).
uniform sampler2D edge_mask : filter_linear, hint_default_black;
uniform vec2 mask_scale = vec2(1.185185, 1.0);   // Bildschirm-UV -> Gemälde-UV (1280 / 1080)
uniform float weave = 0.028;
uniform float vignette = 0.45;
uniform vec3 vignette_color : source_color = vec3(0.10, 0.05, 0.06);

void fragment() {
	vec2 res = 1.0 / SCREEN_PIXEL_SIZE;
	vec2 p = SCREEN_UV * res;
	float st = floor(time_s * boil_fps);
	vec2 n = vec2(vnoise(p * vec2(0.035, 0.11) + st * 13.1), vnoise(p * vec2(0.11, 0.035) + st * 7.7 + 3.0)) - 0.5;
	// ganze Pixel springen lassen (Pixelmitte), damit nichts weichgezeichnet wird
	vec2 muv = SCREEN_UV * mask_scale;
	float em = muv.x < 1.0 ? texture(edge_mask, muv).r : 0.0;
	vec2 jump = clamp(round(n * 2.6 * boil_px * (1.0 - em)), vec2(-boil_px), vec2(boil_px));
	vec3 c = texture(screen_tex, (floor(p) + 0.5 + jump) * SCREEN_PIXEL_SIZE).rgb;
	// Leinwand: Leinenbindung als feines Kreuzmuster, unregelmäßig moduliert
	float wv = sin(p.x * 1.9 + vnoise(p * 0.07) * 3.0) * sin(p.y * 2.05 + vnoise(p.yx * 0.07) * 3.0);
	wv *= 0.6 + 0.8 * vnoise(p * 0.02);
	c *= 1.0 + weave * wv;
	// Vignette in warmem Dunkel (wie ein Firnis-Rand), Mittelpunkt im sichtbaren Bildteil
	vec2 d = (SCREEN_UV - vec2(0.38, 0.48)) * vec2(1.25, 1.0);
	float v = smoothstep(0.30, 0.95, length(d)) * vignette;
	c = mix(c, vignette_color, v);
	COLOR = vec4(c, 1.0);
}
