shader_type canvas_item;
// Milchglasfläche hinter dem Dialog: Bildschirm aus einer groben Mipmap-Stufe (weich), abgedunkelt
// und leicht entsättigt, Ecken abgerundet, oben eine feine helle Kante.

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float alpha = 1.0;
uniform vec2 size_px = vec2(448.0, 214.0);
uniform float radius_px = 10.0;
uniform float blur_px = 14.0;
uniform float darken = 0.42;

void fragment() {
	vec2 size = size_px;
	vec2 p = UV * size;
	// abgerundetes Rechteck (Abstandsfunktion)
	// Distanzfunktion abgerundetes Rechteck nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
	vec2 q = abs(p - size * 0.5) - (size * 0.5 - vec2(radius_px));
	float d = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - radius_px;
	float mask = clamp(0.5 - d, 0.0, 1.0);
	// Weichzeichnen selbst rechnen (Ringe mit 24 Abtastungen); auf Mipmaps des Bildschirms ist
	// im Canvas-Durchgang kein Verlass (gemessen: Fläche blieb scharf)
	vec2 px = SCREEN_PIXEL_SIZE;
	vec3 bg = textureLod(screen_tex, SCREEN_UV, 0.0).rgb;
	float wsum = 1.0;
	for (int ring = 1; ring <= 3; ring++) {
		float r = blur_px * float(ring) / 3.0;
		for (int k = 0; k < 8; k++) {
			float ang = TAU * (float(k) + 0.5 * float(ring)) / 8.0;
			float w = 1.0 - 0.25 * float(ring);
			bg += textureLod(screen_tex, SCREEN_UV + vec2(cos(ang), sin(ang)) * r * px, 0.0).rgb * w;
			wsum += w;
		}
	}
	bg /= wsum;
	float g = dot(bg, vec3(0.3, 0.59, 0.11));
	bg = mix(bg, vec3(g), 0.35);
	vec3 col = bg * (1.0 - darken) + vec3(0.02, 0.025, 0.035) * darken;
	float top = smoothstep(1.5, 0.0, p.y) * 0.35;
	col += vec3(top);
	COLOR = vec4(col, mask * alpha);
}
