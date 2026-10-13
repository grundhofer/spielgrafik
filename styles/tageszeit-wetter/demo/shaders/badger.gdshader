// Dachs (Vorderansicht aus dem Referenzblatt): Atmen und Gewicht verlagern im vertex(), Schalende weht
// quer, Lider blinzeln; danach dieselbe Farb-LUT wie der Hintergrund, Laternenlicht und Nebel.
shader_type canvas_item;

#include "res://shaders/common.gdshaderinc"

uniform sampler2D scarf_tex : filter_linear, repeat_disable;
uniform sampler2D lids_tex : filter_linear, repeat_disable;
uniform sampler2D noise_tex : filter_linear, repeat_enable;   // dieselbe Rauschtextur wie der Hintergrund
uniform vec2 tex_size = vec2(116.0, 175.0);
uniform float feet_y = 173.7;
uniform float scarf_root_y = 64.6;
uniform float scarf_tip_y = 104.4;
uniform float breath = 0.0;      // -1..1
uniform float sway = 0.0;        // px am Kopf
uniform float scarf_off = 0.0;   // px an der Schalspitze
uniform float blink = 0.0;       // 0 offen .. 1 zu
uniform vec3 irr = vec3(0.38, 0.23, 0.01);   // Bestrahlung durch die Laterne am Standort (aus prep.py)
uniform float lantern_i = 0.0;
uniform float fog_dist = 0.06;   // Entfernung der Figur für den Nebel (0 nah .. 1 Himmel)
uniform float wet = 0.0;

void vertex() {
	// Ursprung liegt an den Füßen (offset), daher bleiben die Füße beim Strecken und Scheren stehen
	float h = clamp(-VERTEX.y / feet_y, 0.0, 1.2);
	VERTEX.y *= 1.0 + breath * 0.011;
	VERTEX.x += sway * h;
}

void fragment() {
	vec4 body = texture(TEXTURE, UV);
	vec2 p = UV * tex_size;
	float s = clamp((p.y - scarf_root_y) / (scarf_tip_y - scarf_root_y), 0.0, 1.0);
	vec4 sc = texture(scarf_tex, UV - vec2(scarf_off * s * s / tex_size.x, 0.0));
	vec3 alb = mix(body.rgb, sc.rgb, sc.a);
	float a = max(body.a, sc.a);
	vec4 lid = texture(lids_tex, UV);
	alb = mix(alb, lid.rgb, lid.a * blink);
	alb *= 1.0 - 0.18 * wet;
	vec3 c = grade(alb);
	// Laternenlicht: links (zur Laterne) stärker, nach oben etwas mehr (Laterne hängt höher)
	float side = mix(1.3, 0.7, UV.x) * mix(0.9, 1.15, 1.0 - UV.y);
	c += alb * irr * lantern_i * side;
	// Nebel wie im Hintergrund (bg.gdshader), mit denselben ziehenden Schwaden an derselben Bildstelle
	vec2 px = SCREEN_UV * vec2(1280.0, 720.0);
	float fn = texture(noise_tex, vec2(px.x / 600.0 + time * 0.07, px.y / 170.0 + time * 0.012)).g;
	float fn2 = texture(noise_tex, vec2(px.x / 260.0 - time * 0.11, px.y / 70.0)).r;
	float ff = fog_amount(fog_dist, 0.45 + 0.9 * fn + 0.35 * fn2);
	float wisp = smoothstep(0.45, 0.85, fn * 0.7 + fn2 * 0.5) * fog * 0.4 * smoothstep(0.6, 1.0, fog_front);
	ff = ff + 0.7 * wisp * (1.0 - ff);
	c = mix(c, fog_col, clamp(ff, 0.0, 1.0));
	if (flash > 0.0) {
		// wie bg.gdshader: kaltes, entsättigtes Blitzlicht
		float bl = dot(alb, vec3(0.299, 0.587, 0.114));
		c = mix(c, mix(vec3(bl), alb, 0.35) * vec3(0.86, 0.93, 1.10) * 1.1, flash * 0.6);
	}
	COLOR = vec4(c, a);
}
