// Kopf des lebenden Porträts: Lider, Blick und Mund als Verformung im Texturraum des Kopfes.
// Die Kopf-Polygon2D wird zusätzlich vom Skeleton2D verformt (Drehen, Nicken, Neigen, Ohren);
// weil Lider und Mund hier im Texturraum entstehen, folgen sie dieser Verformung ohne eigene Ebene.
//
// Daten je Spalte der Kopftextur (Pixel), von tools/prep.py aus Porträt und KI-Bearbeitung gemessen:
//   eyecols[x]   = (obere Kante des Auges samt Kontur, untere Kante, Lidlinie des geschlossenen Auges,
//                   obere Kante der inneren Öffnung ohne Kontur, negativ = Spalte ohne Öffnung); x < 0: kein Auge
//   mouthcols[x] = (Oberkante des offenen Mundinnenraums in der Bearbeitung, dessen Höhe,
//                   Ober- und Unterkante der Lachlinie im Porträt); x < 0: kein Mund
// mask_tex: G/B = linkes/rechtes Auge (weich, für die Überblendung zum geschlossenen Auge); R wird nicht mehr
// genutzt (Mundbereich, nur Prüfbild). faces_tex: KI-Bearbeitung (Augen zu, Mund auf).
shader_type canvas_item;

uniform sampler2D faces_tex : filter_linear, repeat_disable;
uniform sampler2D mask_tex : filter_linear, repeat_disable;
uniform vec2 tex_size = vec2(512.0);
uniform vec4 eyecols[400];
uniform vec4 mouthcols[400];
uniform float eye_open_l : hint_range(0.0, 1.0) = 1.0;
uniform float eye_open_r : hint_range(0.0, 1.0) = 1.0;
uniform float mouth_open : hint_range(0.0, 1.0) = 0.0;
uniform vec2 gaze = vec2(0.0);         // Blickrichtung: Iris im Augenweiß verschieben (Pixel)
uniform vec4 sclera : source_color = vec4(0.93, 0.9, 0.84, 1.0);
uniform float eye_split_x = 256.0;     // Spalte zwischen den Augen
uniform float lid_reach = 0.8;         // gedehnter Fellbereich über der Lidkante, Anteil der Augenhöhe
uniform float low_reach = 0.45;        // gedehnter Fellbereich unter dem Auge für das Unterlid
uniform float closed_mix = 0.2;        // darunter ganz die KI-Fassung mit geschlossenen Augen (harter Wechsel)
uniform float lower_px = 1.0;          // Stärke der unteren Augenkontur
uniform float lip_px = 1.2;            // Breite der Lippenlinie um das Mundband
uniform vec4 lip_color : source_color = vec4(0.12, 0.07, 0.06, 1.0);

varying vec4 vcol;

void vertex() {
	vcol = COLOR;
}

vec4 eye_at(float x) {
	return eyecols[clamp(int(floor(x)), 0, 399)];
}

vec4 mouth_at(float x) {
	return mouthcols[clamp(int(floor(x)), 0, 399)];
}

void fragment() {
	vec2 px = UV * tex_size;
	vec4 c = texture(TEXTURE, UV);
	vec4 masks = texture(mask_tex, UV);

	// ---- Mund (je Spalte): geschlossen liegt nur die Lachlinie des Porträts da. Beim Öffnen wächst aus ihrer Mitte
	// ein Band nach oben (bis uB) und unten (bis uB + h), gefüllt mit dem gestauchten Mundinnenraum der
	// KI-Bearbeitung und von einer dunklen Lippenlinie gesäumt. Das Porträt darunter wird nicht verschoben.
	vec4 mc = mouth_at(px.x);
	if (mouth_open > 0.001 && mc.x >= 0.0 && mc.y > 0.5) {
		float m = mouth_open * smoothstep(0.5, 6.0, mc.y);   // zu den Mundwinkeln hin weniger
		float ub = mc.x;
		float h = mc.y;
		float wc = 0.5 * (mc.z + mc.w);                       // Mitte der Lachlinie
		float top = mix(wc, ub, m);
		float bot = mix(wc, ub + h, m);
		float d = min(px.y - top, bot - px.y);               // Abstand zum Bandrand (innen positiv)
		float cov = clamp(d + lip_px, 0.0, 1.0);
		if (cov > 0.0) {
			float sy = ub + clamp((px.y - top) / max(bot - top, 0.001), 0.0, 1.0) * h;
			vec3 inner = texture(faces_tex, vec2(px.x, sy) / tex_size).rgb;
			vec3 col = mix(lip_color.rgb, inner, clamp(d - 0.4, 0.0, 1.0));
			c = mix(c, vec4(col, 1.0), cov * smoothstep(0.0, 0.08, mouth_open));
		}
	}

	// ---- Augen
	vec4 ec = eye_at(px.x);
	bool left = px.x < eye_split_x;
	float o = left ? eye_open_l : eye_open_r;
	if (ec.x >= 0.0) {
		bool opening = ec.w >= 0.0;     // Spalte mit innerer Öffnung (sonst Augenwinkel: nur Kontur)
		float top = opening ? ec.w : -ec.w - 1.0;  // Unterkante der Lidlinie = Oberkante der inneren Öffnung
		float bot = ec.y;               // untere Kante des Auges
		float arc = ec.z;               // hier schließen sich die Lider (Lidlinie der KI-Fassung)
		float bin = bot - lower_px;     // untere Kante der inneren Öffnung
		// Blick: innerhalb der inneren Öffnung aus verschobener Stelle lesen; was von außerhalb käme, ist Augenweiß
		if ((abs(gaze.x) > 0.01 || abs(gaze.y) > 0.01) && opening && px.y >= top && px.y <= bin) {
			vec2 s = px - gaze;
			vec4 es = eye_at(s.x);
			// weicher Übergang (1 px) an Ober- und Unterkante der Öffnung; Augenweiß unter dem Oberlid beschattet
			float inside = (es.x >= 0.0 && es.w >= 0.0) ? smoothstep(es.w, es.w + 1.0, s.y) * smoothstep(es.y - lower_px, es.y - lower_px - 1.0, s.y) : 0.0;
			vec3 scl = sclera.rgb * mix(0.8, 1.0, smoothstep(top, top + 0.5 * (bin - top), px.y));
			c = mix(vec4(scl, 1.0), texture(TEXTURE, s / tex_size), inside);
		}
		if (o < 0.999) {
			// Lider aus dem Porträt allein: bei o = closed_mix treffen sie sich auf dem Lidbogen der KI-Fassung
			float os = clamp((o - closed_mix) / (1.0 - closed_mix), 0.0, 1.0);
			float hgt = max(bot - ec.x, 1.0);
			// Oberlid gleitet von top bis arc; darüber wird das Fell samt Lidlinie gedehnt
			float lid = mix(arc, top, os);
			float y0 = ec.x - lid_reach * hgt;
			if (px.y >= y0 && px.y < lid) {
				float src = y0 + (px.y - y0) * (top - y0) / max(lid - y0, 0.001);
				c = texture(TEXTURE, vec2(px.x, src) / tex_size);
			}
			// Unterlid steigt von bin bis arc (vor allem in der zweiten Hälfte des Schließens): Fell unter dem Auge
			// samt unterer Kontur wird nach oben gedehnt, gespiegelt zum Oberlid. Keine Pixel der KI-Fassung,
			// deren Wimpernbogen läge sonst als Strichrest unter und neben dem Auge.
			float arc_lo = min(arc, bin);
			float low = mix(arc_lo, bin, smoothstep(0.0, 0.6, os));
			float y1 = bot + low_reach * hgt;
			if (px.y > low && px.y < y1) {
				float src = y1 - (y1 - px.y) * (y1 - bin) / max(y1 - low, 0.001);
				c = texture(TEXTURE, vec2(px.x, src) / tex_size);
			}
		}
	}
	// Geschlossen: ganz die KI-Fassung, weich nur am Rand der Augenmaske; kein Mischen zweier Lidbilder
	float eye_m = left ? masks.g : masks.b;
	if (eye_m > 0.002 && o < closed_mix) {
		c = mix(c, texture(faces_tex, UV), eye_m);
	}
	COLOR = c * vcol;
}
