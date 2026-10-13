// Vorgerenderte Karte: Palettenindex (R) und Leuchtstufe (G) aus bg.png, Wasserfolge als Überlagerung,
// Strahl des Leuchtfeuers als Lichtzuschlag, Schlagschatten des Dachses aus seinem Blatt (B-Kanal), nur dort,
// wo das Tiefenbild den Boden zeigt.
shader_type canvas_item;
render_mode blend_disabled, unshaded;

#include "res://shaders/palette_light.gdshaderinc"

uniform sampler2D water_tex : filter_nearest;     // Palettenindex der Wasserfolge (L8), beschnitten
uniform sampler2D water_mask : filter_nearest;    // wo die Folge gilt (L8)
uniform ivec4 water_rect;                          // x0, y0, x1, y1 in Kartenpixeln
uniform bool water_on = true;
uniform sampler2D beam_tex : filter_nearest;      // Strahl, halbe Auflösung (L8)
uniform float beam_gain = 1.1;
uniform sampler2D badger_tex : filter_nearest;
uniform ivec2 sh_map_origin;
uniform ivec2 sh_sheet_origin;
uniform ivec2 cell_size = ivec2(112, 76);
uniform float shadow_mul = 0.55;
uniform bool shadow_on = true;
// Auswahlring (Ellipse 2:1 auf dem Boden, 1 px Linie) unter der aktiven Figur
uniform vec2 ring_c;
uniform vec2 ring_ab = vec2(12.0, 6.0);
uniform int ring_idx = 2;
uniform bool ring_on = true;

float ring_f(vec2 q) {
	vec2 e = (q - ring_c) / ring_ab;
	return dot(e, e) - 1.0;
}

void fragment() {
	ivec2 p = ivec2(floor(UV * map_size));
	vec4 b = texelFetch(TEXTURE, p, 0);
	int idx = int(round(b.r * 255.0));
	int emis = int(round(b.g * 255.0));
	ivec2 wq = p - water_rect.xy;
	if (water_on && p.x >= water_rect.x && p.y >= water_rect.y && p.x < water_rect.z && p.y < water_rect.w) {
		float wm = texelFetch(water_mask, wq, 0).r;
		float wi = texelFetch(water_tex, wq, 0).r;
		if (wm > 0.5) {
			idx = int(round(wi * 255.0));
		}
	}
	vec4 bm = texelFetch(beam_tex, p / 2, 0);
	float d = decode_depth(p);
	vec2 pc = vec2(p) + 0.5;
	float l = light_at(world_at(pc, d));
	ivec2 q = p - sh_map_origin;
	if (shadow_on && q.x >= 0 && q.y >= 0 && q.x < cell_size.x && q.y < cell_size.y) {
		vec4 s = texelFetch(badger_tex, sh_sheet_origin + q, 0);
		if (s.b > 0.5 && abs(d - plane_depth(pc)) < 0.08) {
			l *= shadow_mul;
		}
	}
	l += bm.r * beam_gain;
	if (ring_on && abs(d - plane_depth(pc)) < 0.08) {
		vec2 c0 = vec2(p);
		float f0 = ring_f(c0), f1 = ring_f(c0 + vec2(1.0, 0.0));
		float f2 = ring_f(c0 + vec2(0.0, 1.0)), f3 = ring_f(c0 + vec2(1.0, 1.0));
		if (min(min(f0, f1), min(f2, f3)) < 0.0 && max(max(f0, f1), max(f2, f3)) > 0.0) {
			idx = ring_idx;
			emis = 10;
		}
	}
	int row = row_for(l, p);
	if (emis > 0) {
		row = max(row, emis);
	}
	COLOR = vec4(lut_color(idx, row), 1.0);
}
