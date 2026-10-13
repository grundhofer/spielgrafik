shader_type canvas_item;
// Vergleichsansicht: links das Codex-Bild (gpt-image), rechts das agy-Bild (Gemini) desselben Prompts.
// Eine senkrechte Trennlinie (split) wischt zwischen beiden; beim Wechsel des Bildpaars wischt eine waagerechte
// Kante (change, von oben nach unten) das nächste Paar über das alte. Beide Bilder eines Paars liegen schon
// vorab auf derselben Leinwand (gleicher Maßstab, gleicher Rand), daher genügen gemeinsame UV.

uniform sampler2D cur_a : filter_linear_mipmap, repeat_disable;
uniform sampler2D cur_b : filter_linear_mipmap, repeat_disable;
uniform sampler2D next_a : filter_linear_mipmap, repeat_disable;
uniform sampler2D next_b : filter_linear_mipmap, repeat_disable;
uniform float split_cur = 0.5;
uniform float split_next = 0.9;
uniform float change = 0.0;      // 0 = nur aktuelles Paar, 1 = nur nächstes Paar
uniform vec2 size = vec2(870.0, 580.0);
uniform vec4 line_col : source_color = vec4(0.96, 0.93, 0.86, 1.0);

float divider(float px, float split_px) {
	// 2 px helle Linie mit weichem dunklem Schatten links und rechts
	float d = abs(px - split_px);
	return 1.0 - smoothstep(0.9, 1.6, d);
}

float shade(float px, float split_px) {
	float d = abs(px - split_px);
	return 0.35 * (1.0 - smoothstep(1.5, 9.0, d));
}

void fragment() {
	vec2 uv = UV;
	vec2 p = uv * size;
	// alle Texturen vor jeder Verzweigung abtasten (Mipmap-Ableitungen)
	vec4 ca = texture(cur_a, uv);
	vec4 cb = texture(cur_b, uv);
	vec4 na = texture(next_a, uv);
	vec4 nb = texture(next_b, uv);
	float sc = split_cur * size.x;
	float sn = split_next * size.x;
	vec3 cur = mix(ca.rgb, cb.rgb, step(sc, p.x));
	cur = mix(cur, vec3(0.0), shade(p.x, sc));
	cur = mix(cur, line_col.rgb, divider(p.x, sc));
	vec3 nxt = mix(na.rgb, nb.rgb, step(sn, p.x));
	nxt = mix(nxt, vec3(0.0), shade(p.x, sn));
	nxt = mix(nxt, line_col.rgb, divider(p.x, sn));
	float edge = change * (size.y + 24.0) - 12.0;
	vec3 col = mix(cur, nxt, step(p.y, edge));
	// Wischkante: helle 2-px-Linie mit Schatten darunter, nur während des Wechsels
	float on = step(0.001, change) * step(change, 0.999);
	float de = p.y - edge;
	col = mix(col, vec3(0.0), on * 0.4 * (1.0 - smoothstep(0.0, 14.0, de)) * step(0.0, de));
	col = mix(col, line_col.rgb, on * (1.0 - smoothstep(0.9, 1.6, abs(de))));
	COLOR = vec4(col, 1.0);
}
