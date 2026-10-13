// Ölfarben-Shader für Figuren. Die Pinselstriche sind schon in die Textur gemalt (prep.py, paint_strokes);
// der Shader sorgt nur noch für das Lebendige:
//  - "Boil": 8-mal pro Sekunde springen strichförmige Flecken um ganze Texel (kein Weichzeichnen),
//    sodass die Striche flimmern wie bei gemalter Einzelbild-Animation.
//  - Relief: Strichrauschen hellt die zur Lichtquelle zeigenden Grate auf (schwach).
//  - Kantenlicht: Pixel, deren Nachbar in Lichtrichtung transparent ist, bekommen einen gebrochenen warmen Strich.
//  - Umgebungsfarbe vom Skript (in Laternennähe wärmer).
//  - Farbangleichung an das Gemälde: Sättigung leicht zur Szenenpalette ziehen, Lichter dämpfen und Schatten
//    ins stumpfe Violett des Hintergrunds drehen (sonst wirkt die Figur heller und bunter, wie aufgeklebt).
// Ein Kuwahara-Filter (Radius 2 und 3) wurde getestet und wieder entfernt: bei 152 px Figurenhöhe löscht er
// den Augenstreifen und die Paketschnur.
shader_type canvas_item;
#include "res://shaders/noise.gdshaderinc"

uniform float time_s = 0.0;          // vom Skript gesetzt (deterministisch)
uniform float boil_fps = 8.0;
uniform float boil_texels = 1.0;     // Sprungweite in ganzen Texeln
uniform float boil_stop_v = 0.86;    // ab dieser Höhe (UV.y, vom Skript aus walk.json) springen keine Texel mehr:
                                     // die Füße bleiben am Boden ruhig, Standfuß und Fußlinie zittern nicht
uniform vec3 tint = vec3(1.0);       // Lichtfarbe der Umgebung (vom Skript)
uniform vec2 light_dir = vec2(-0.7, -0.7);   // Richtung zur Lichtquelle im Bild (vom Skript)
uniform vec3 rim_color : source_color = vec3(1.0, 0.72, 0.42);
uniform float rim = 0.6;             // Stärke des Kantenlichts (vom Skript)
uniform float rim_texels = 2.0;
uniform float strokes = 0.06;        // Stärke des Relief-Rauschens
uniform float sat_pull = 0.16;       // Anteil Entsättigung
uniform vec3 scene_col : source_color = vec3(0.36, 0.29, 0.25);  // mittlere Farbe des Kais (gemessen in bg.png)
uniform float scene_pull = 0.06;     // Farbton zur Szenenfarbe ziehen (bei gleicher Helligkeit)
uniform vec3 shadow_col : source_color = vec3(0.32, 0.22, 0.44); // stumpfes Violett der Schatten im Gemälde
uniform float shadow_pull = 0.32;    // wie stark dunkle Töne ins Violett gedreht werden
uniform float highlight_cut = 0.12;  // Lichter dämpfen (Hemd, Fell)

varying vec4 vcol;

void vertex() {
	vcol = COLOR;                    // nur Vertexfarbe/Modulate; in fragment() enthält COLOR schon die Textur
}

float stroke_noise(vec2 q, float st) {
	// gestreckte Flecken entlang einer Richtung, die sich über die Figur langsam dreht
	float ang = vnoise(q * 0.03 + vec2(4.0, 1.0)) * 3.1416;
	vec2 d = vec2(cos(ang), sin(ang));
	vec2 r = vec2(dot(q, d), dot(q, vec2(-d.y, d.x)));
	return vnoise(r * vec2(0.09, 0.42) + st * 3.71);
}

void fragment() {
	vec2 px = TEXTURE_PIXEL_SIZE;
	float st = floor(time_s * boil_fps);
	vec2 q = UV / px;
	// Boil: strichförmige Flecken verschieben die Abtastung um -1, 0 oder +1 Texel (Texelmitte, also scharf)
	vec2 n = vec2(vnoise(q * vec2(0.09, 0.22) + st * 17.31), vnoise(q * vec2(0.22, 0.09) + st * 9.13 + 5.0)) - 0.5;
	float feet = smoothstep(boil_stop_v - 0.03, boil_stop_v, UV.y);
	vec2 jump = clamp(round(n * 2.6 * boil_texels * (1.0 - feet)), vec2(-boil_texels), vec2(boil_texels));
	vec2 uv = (floor(q) + 0.5 + jump) * px;
	vec4 c = texture(TEXTURE, uv);
	vec3 rgb = c.rgb;

	// Farbangleichung an das Gemälde (vor dem Kantenlicht, das warm bleiben soll)
	const vec3 W = vec3(0.299, 0.587, 0.114);
	float lum = dot(rgb, W);
	rgb = mix(rgb, vec3(lum), sat_pull);
	rgb = mix(rgb, scene_col * (lum / dot(scene_col, W)), scene_pull);
	float shade = 1.0 - smoothstep(0.08, 0.42, lum);
	rgb = mix(rgb, shadow_col * (lum / dot(shadow_col, W)), shade * shadow_pull);
	rgb *= 1.0 - highlight_cut * smoothstep(0.45, 0.9, lum);

	// Relief: Grate zur Lichtseite hin heller, dahinter dunkler
	vec2 ld = normalize(light_dir);
	float s1 = stroke_noise(q, st);
	float s2 = stroke_noise(q - ld * 1.6, st);
	rgb *= 1.0 + strokes * ((s1 - 0.5) * 1.2 + (s1 - s2) * 2.5);

	// Kantenlicht zur Lichtquelle hin, vom Strichrauschen unterbrochen
	float a_l = 0.5 * texture(TEXTURE, uv + ld * rim_texels * px).a
			+ 0.5 * texture(TEXTURE, uv + ld * rim_texels * 2.0 * px).a;
	float edge = clamp(c.a - a_l, 0.0, 1.0) * smoothstep(0.35, 0.6, s1 + 0.15);
	rgb = mix(rgb, rgb * 0.4 + rim_color, edge * rim);

	float a = smoothstep(0.3, 0.7, c.a);           // harter, gemalter Rand statt weicher Kante
	COLOR = vec4(rgb * tint, a) * vcol;
}
