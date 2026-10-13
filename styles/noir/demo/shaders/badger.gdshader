// Dachs-Kurier: flaches KI-Sprite mit Kissen-Normalen (scripts/build_badger.py), im Spiel hart beleuchtet.
// Licht: wenig Umgebungslicht (Nacht), Fensterlicht von links oben in Lamellenstreifen, wenn die Figur im Strahl
// steht, Laterne von rechts oben (flackert, fällt mit der Entfernung ab), Kantenlicht aus dem Gegenlicht.
// Harte Schattengrenzen über eine enge smoothstep-Schwelle auf N·L. Das Kantenlicht ist eine schmale, hart
// geschwellte Kante (äußere 1–2 px der Kissen-Normalen), oben und hinten am stärksten, und nimmt auf farbigen
// Flächen deren Farbton an: Weißes Kantenlicht auf dem dunkelroten Schal ergäbe Grau, und der Filmlook
// (post.gdshader) würde den Schal dort entsättigen.
shader_type canvas_item;

uniform sampler2D normal_tex : filter_linear;
uniform float flicker = 1.0;
uniform vec2 lantern = vec2(771.7, 191.7);
uniform vec2 window_pos = vec2(104.0, 260.0);
uniform float ambient = 0.17;
uniform float rim_gain = 0.65;
uniform vec2 rim_edge = vec2(0.74, 0.80);    // Schwelle auf 1 − N.z: nur die äußeren 1–2 px der Silhouette
uniform float accent_lift = 0.8;            // Akzentfarbe (Schal) bekommt mehr Umgebungslicht, bleibt im Dunkeln lesbar
uniform float key_gain = 1.7;
uniform float win_light = 1.05;
uniform vec2 beam_x = vec2(178.0, 429.0);   // waagerechter Bereich des Fensterstrahls auf Höhe der Figur
uniform float stripe_period = 13.0;         // Lamellenstreifen auf der Figur (Bildschirmpixel)
uniform float stripe_duty = 0.5;
uniform float stripe_slope = -0.21;         // wie der Wandfuß / die Streifen auf dem Pflaster
uniform float stripe_phase = 0.0;

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

float hard(float x, float edge) {
	return smoothstep(edge - 0.04, edge + 0.04, x);
}

void fragment() {
	vec4 alb = COLOR;
	vec3 n = normalize(texture(normal_tex, UV).rgb * 2.0 - 1.0);

	// Laterne
	vec2 dl = lantern - world;
	vec3 L = normalize(vec3(dl, 160.0));
	float att = 1.0 / (1.0 + pow(length(dl) / 520.0, 2.0));
	float key = hard(dot(n, L), 0.34) * att * flicker * key_gain;

	// Fenster: Strahl mit Lamellenstreifen (Bildschirmraum, Neigung wie auf dem Pflaster)
	vec2 dw = window_pos - world;
	vec3 W = normalize(vec3(dw, 90.0));
	float inbeam = smoothstep(beam_x.x - 6.0, beam_x.x + 6.0, world.x) * (1.0 - smoothstep(beam_x.y - 6.0, beam_x.y + 6.0, world.x));
	float f = (world.y - stripe_slope * world.x) / stripe_period + stripe_phase;
	float w = max(fwidth(f), 0.02);
	float x = fract(f);
	float stripes = smoothstep(0.0, w, x) * (1.0 - smoothstep(stripe_duty - w, stripe_duty, x));
	float win = hard(dot(n, W), 0.26) * stripes * inbeam * win_light + inbeam * 0.08;

	// Gegenlicht: schmale, harte Kante der Silhouette, oben und hinten (links, Laufrichtung rechts) am stärksten
	float edge = smoothstep(rim_edge.x, rim_edge.y, 1.0 - n.z);
	vec2 o = normalize(n.xy + vec2(0.0, 1e-4));
	float dirw = clamp(0.15 + 1.1 * max(-o.y, 0.0) + 0.7 * max(-o.x, 0.0), 0.0, 1.0);
	float rim = edge * rim_gain * dirw;

	// Farbe der Albedo: auf gesättigten Flächen (Schal) Kantenlicht im eigenen Farbton, Umgebungslicht angehoben
	float amx = max(max(alb.r, alb.g), alb.b);
	float sat = (amx - min(min(alb.r, alb.g), alb.b)) / max(amx, 1e-3);
	float accent = smoothstep(0.3, 0.6, sat);
	vec3 rim_col = mix(vec3(1.0), alb.rgb / max(amx, 1e-3), accent);

	vec3 c = alb.rgb * (ambient * (1.0 + accent_lift * accent) + key + win) + rim * rim_col * (1.0 - 0.5 * inbeam);
	COLOR = vec4(c, alb.a);
}
