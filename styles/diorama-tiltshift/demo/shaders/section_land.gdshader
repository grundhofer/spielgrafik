// Schnittwand des Inselstücks (SectionLand): Erdschichten wie bei einem aufgeschnittenen Modell.
// UV = (Umfangsmeter, Höhe in m), UV2 = (Oberkante der Säule in m, Art der Oberfläche: 0 Kai, 1 Gras,
// 2 Sand, 3 Fels). Unter dem Kai geschnittene Pflasterplatten auf Kies, sonst Mutterboden mit Rand in der
// Farbe der Oberfläche; darunter überall Erde mit Kieseln, Lehmband, Fels. Die Bodenschichten folgen der
// Oberkante (Tiefe d unter der Oberfläche), die Felsbänke liegen waagrecht: So zeigt auch die hohe Schnittwand
// des Westhügels über die ganze Höhe Schichten (Fels ab 1,7 m unter der Oberkante, darin ein zweites Lehmband
// und ein Kiesband). Beim Kai (Oberkante 0) ist d = -(y + wob), das Bild bleibt dort wie zuvor.
// glTF dreht V um (v' = 1 - v): Höhe und Art werden deshalb als 1 - UV.y bzw. 1 - UV2.y gelesen.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

#include "res://shaders/dio_noise.gdshaderinc"

uniform vec4 topsoil : source_color = vec4(0.22, 0.15, 0.10, 1.0);
uniform vec4 earth : source_color = vec4(0.48, 0.34, 0.22, 1.0);
uniform vec4 clay : source_color = vec4(0.62, 0.47, 0.30, 1.0);
uniform vec4 rock : source_color = vec4(0.38, 0.36, 0.35, 1.0);
uniform vec4 grass : source_color = vec4(0.30, 0.48, 0.17, 1.0);
uniform vec4 sand : source_color = vec4(0.80, 0.68, 0.47, 1.0);
uniform vec4 masonry : source_color = vec4(0.55, 0.53, 0.50, 1.0);
uniform vec4 mortar : source_color = vec4(0.30, 0.28, 0.27, 1.0);

void fragment() {
	float u = UV.x;
	float y = 1.0 - UV.y;
	float top = UV2.x;
	float cls = floor(1.0 - UV2.y + 0.5);
	float below = top - y;
	float wob = (dio_fbm2(vec2(u * 0.25, 0.0)) - 0.5) * 0.7 + (dio_vnoise2(vec2(u * 1.6, 3.0)) - 0.5) * 0.12;
	float d = below - wob;

	// Bodenschichten nach Tiefe unter der Oberkante: Erde, Lehmband, Erde, ab 1,6–1,75 m Fels
	vec3 col = mix(earth.rgb, clay.rgb, smoothstep(0.35, 0.55, d) * (1.0 - smoothstep(0.95, 1.15, d)));
	// Fels in waagrechten Bänken (0,55 m) mit dunkler Fuge, jede Bank etwas anders getönt
	float sy = (y + wob * 0.4) / 0.55;
	float bank = fract(sy);
	vec3 rk = rock.rgb * (0.8 + 0.34 * dio_hash12(vec2(floor(sy), 7.0)));
	rk *= 1.0 - 0.38 * (1.0 - smoothstep(0.0, 0.08, bank));
	rk *= 0.88 + 0.24 * dio_vnoise2(vec2(u * 1.3, y * 4.0));
	col = mix(col, rk, smoothstep(1.6, 1.75, d));
	col = mix(col, rk * 0.85, smoothstep(1.95, 2.2, d) * (1.0 - smoothstep(2.6, 2.8, d)));
	// hohe Wände: zweites Lehmband und darunter ein Kiesband im Fels
	col = mix(col, clay.rgb * 0.9, smoothstep(2.85, 3.0, d) * (1.0 - smoothstep(3.3, 3.45, d)));
	float gravel_band = smoothstep(3.45, 3.55, d) * (1.0 - smoothstep(3.95, 4.1, d));
	col = mix(col, earth.rgb * 0.95, gravel_band);
	col = mix(col, earth.rgb * 0.8, (1.0 - smoothstep(0.0, 0.2, d)) * 0.5);
	// Kiesel: kleine (4 cm) überall, große (10–12 cm) in den Erdschichten und im Kiesband
	vec2 c = dio_cells(vec3(u * 5.0, y * 5.0, 0.5)).xy;
	float pebble = (1.0 - smoothstep(0.18, 0.26, c.x)) * step(0.55, c.y);
	col = mix(col, mix(rock.rgb * 1.25, rock.rgb * 0.8, c.y), pebble * 0.8);
	vec2 cb = dio_cells(vec3(u * 2.2, y * 2.2, 2.5)).xy;
	float earthy = (1.0 - smoothstep(1.55, 1.7, d)) * smoothstep(0.25, 0.35, d) + gravel_band * 2.5;
	float big = (1.0 - smoothstep(0.2, 0.27, cb.x)) * step(0.6 - 0.25 * gravel_band, cb.y) * clamp(earthy, 0.0, 1.0);
	// Steine hell (grau oder sandfarben), zur Mitte heller gewölbt, mit dunklem Saum (Erde drückt sich an)
	vec3 big_col = mix(rock.rgb * 1.75, clay.rgb * 1.15, step(0.5, fract(cb.y * 7.0))) * (0.72 + 0.4 * (1.0 - smoothstep(0.0, 0.24, cb.x)));
	float seam = smoothstep(0.17, 0.23, cb.x) * (1.0 - smoothstep(0.27, 0.33, cb.x)) * step(0.6 - 0.25 * gravel_band, cb.y) * clamp(earthy, 0.0, 1.0);
	col *= 1.0 - 0.3 * seam;
	col = mix(col, big_col, big);
	col *= 0.88 + 0.22 * dio_vnoise2(vec2(u, y) * 14.0);

	if (cls < 0.5) {
		// Kai: geschnittene Pflasterplatten (0,1 m) auf einem Kiesbett, darunter dieselben Erdschichten
		float fu = fract(u / 0.9);
		vec3 stone = masonry.rgb * (0.85 + 0.25 * dio_hash12(vec2(floor(u / 0.9), 3.0)));
		stone *= 0.94 + 0.12 * dio_vnoise2(vec2(u, y) * 30.0);
		stone = mix(mortar.rgb, stone, smoothstep(0.012, 0.025, min(fu, 1.0 - fu) * 0.9));
		vec2 g = dio_cells(vec3(u * 28.0, y * 28.0, 1.5)).xy;
		vec3 gravel = mix(mortar.rgb * 1.3, masonry.rgb, g.y) * mix(0.65, 1.0, smoothstep(0.0, 0.3, g.x));
		float pave = 1.0 - smoothstep(0.1, 0.112, below);
		float bed = 1.0 - smoothstep(0.27, 0.3 + 0.04 * dio_vnoise2(vec2(u * 4.0, 2.0)), below);
		col = mix(col, gravel, bed);
		col = mix(col, stone, pave);
	} else {
		// dunkle Muttererde dicht unter der Oberfläche, oberster Rand in der Farbe der Oberfläche
		col = mix(topsoil.rgb, col, smoothstep(0.08, 0.32 + 0.1 * dio_vnoise2(vec2(u * 3.0, 1.0)), below));
		vec3 rim_col = cls < 1.5 ? grass.rgb : (cls < 2.5 ? sand.rgb : rock.rgb);
		float rim_w = cls < 1.5 ? 0.07 : 0.04;
		col = mix(rim_col * (0.85 + 0.3 * dio_vnoise2(vec2(u * 30.0, y * 30.0))), col, smoothstep(rim_w * 0.6, rim_w, below));
	}
	ALBEDO = col;
	ROUGHNESS = 0.95;
	SPECULAR = 0.2;
}
