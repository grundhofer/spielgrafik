shader_type canvas_item;
// Miniatur: Goldgrund schimmert, Wellenkringel kommen und gehen in Zügen, die Laterne flackert.
#include "res://shaders/gold.gdshaderinc"

uniform sampler2D mask_tex : filter_nearest;    // R = Gold, G = Wasser, B = Laternenglas
uniform sampler2D nocrest_tex : filter_nearest; // Miniatur ohne weiße Wellenkringel
uniform vec2 origin = vec2(64.0, 48.0);
uniform vec2 size = vec2(792.0, 524.0);
uniform float flick = 0.0;

void fragment() {
	// alle Texturen vor Verzweigungen abtasten (es gibt hier keine)
	vec4 base = texture(TEXTURE, UV);
	vec3 nc = texture(nocrest_tex, UV).rgb;
	vec3 m = texture(mask_tex, UV).rgb;
	vec2 q = UV * size;
	// Kringel wiegen sich zeilenweise um ganze Pixel hin und her (kein Verwischen)
	float sway = round(2.0 * sin(t * 1.7 + q.y * 0.09));
	vec2 uv_s = UV - vec2(sway, 0.0) / size;
	vec3 base_s = texture(TEXTURE, uv_s).rgb;
	vec3 nc_s = texture(nocrest_tex, uv_s).rgb;
	float wm_s = texture(mask_tex, uv_s).g;
	vec2 p = origin + q;
	vec3 col = base.rgb;
	// Wasser: Kringel kommen und gehen in Zügen, die nach links wandern (58 px/s); eine zweite, langsamere
	// Welle bricht die Regelmäßigkeit. Die Kringel-Ebene (Bild minus Bild ohne Kringel) wird verschoben.
	float wave = 0.7 * sin(q.x * 0.055 + t * 3.2 + q.y * 0.21) + 0.3 * sin(q.x * 0.021 - t * 0.9 + q.y * 0.47);
	float show = smoothstep(-0.25, 0.25, wave);
	vec3 crest = (base_s - nc_s) * wm_s;
	col = mix(col, nc + crest * show, m.g);
	// Goldgrund: Relief aus der Helligkeit des gemalten Golds (Punzsterne, Knitter)
	float lum = dot(base.rgb, vec3(0.299, 0.587, 0.114));
	float relief = clamp((lum - 0.42) * 2.6, 0.0, 1.0);
	// Phase des Aufblitzens: breite, schräge, unregelmäßige Bänder (kein Raster, das sähe wie Kacheln aus)
	float ph = 0.5 + 0.5 * sin(q.x * 0.013 + 2.0 * sin(q.y * 0.021 + q.x * 0.004));
	col = mix(col, gold_light(col, relief, ph, p), m.r);
	// Laterne
	col = mix(col, col * (0.80 + 0.45 * flick) + vec3(0.14, 0.07, 0.0) * flick, m.b);
	COLOR = vec4(col, base.a);
}
