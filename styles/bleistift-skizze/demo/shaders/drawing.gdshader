// Hintergrund: die KI-Bleistiftzeichnung (Papier = Weiß) wird auf das karierte Blatt multipliziert, so scheinen
// Karo, Fasern und Wolkigkeit des Papiers überall durch. Line-Boil und Papierzahn aus boil.gdshaderinc.
// Rand: Die Zeichnung hört nicht an einer Kante auf, sondern läuft aus wie eine Skizze: eine Schwelle steigt
// zum Rand hin (mit unregelmäßigem Verlauf), helle Striche verschwinden zuerst, satte reichen weiter.
shader_type canvas_item;
render_mode blend_mul;
#include "res://shaders/boil.gdshaderinc"

uniform vec2 size = vec2(1216.0, 538.0);
uniform vec4 fade_px = vec4(46.0, 22.0, 56.0, 40.0);   // links, oben, rechts, unten
uniform float fade_noise = 18.0;

varying vec2 world_pos;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

void fragment() {
	vec2 p = UV * size;
	float pressure;
	ivec2 ip = clamp(ivec2(floor(p)) + boil_offset(p, pressure), ivec2(0), ivec2(size) - 1);
	vec3 ink = 1.0 - texelFetch(TEXTURE, ip, 0).rgb;
	ink = on_tooth(ink * pressure, world_pos);

	// Auslaufender Rand: Abstand zum Rand je Seite relativ zur Breite des Auslaufs, mit grobem Rauschen
	float w = (texture(boil_tex, p / 900.0 + vec2(0.37, 0.71)).r - 0.5) / 0.18;
	float w2 = (texture(boil_tex, p / 130.0 + vec2(0.11, 0.53)).g - 0.5) / 0.18;
	float n = fade_noise * (0.75 * w + 0.35 * w2);
	float e = min(min((p.x + n) / fade_px.x, (p.y + n) / fade_px.y),
				  min((size.x - p.x + n) / fade_px.z, (size.y - p.y + n) / fade_px.w));
	float th = 0.86 * (1.0 - smoothstep(0.0, 1.0, e));
	ink = max(ink - th, vec3(0.0));

	COLOR = vec4(1.0 - clamp(ink, 0.0, 1.0), 1.0);
}
