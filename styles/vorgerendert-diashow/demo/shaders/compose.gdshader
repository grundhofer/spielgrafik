// Knotenwechsel wie in Standbild-Erkundungsspielen auf CD-ROM:
//   Überblendung als Pixel-Auflösung: jeder Bildpunkt springt zu einem festen, zufälligen Zeitpunkt vom alten
//   ins neue Bild (in 8 Bit gab es keine Mischfarben, deshalb kein weiches Überblenden).
//   Schneller Zoom: das alte Bild wird um den angeklickten Punkt vergrößert (Nearest, grobe Pixel), danach löst
//   sich das neue Bild auf dieselbe Weise ein.
// Beide Knoten kommen als fertige 544×332-Bilder aus eigenen SubViewports (Standbild + Bildfolgen).
shader_type canvas_item;

uniform sampler2D tex_a : filter_nearest;   // alter Knoten
uniform sampler2D tex_b : filter_nearest;   // neuer Knoten
uniform float mix_p = 0.0;                  // 0 = nur alt, 1 = nur neu
uniform float zoom_a = 1.0;                 // Vergrößerung des alten Bildes
uniform vec2 zoom_center = vec2(272.0, 166.0);
uniform vec2 size = vec2(544.0, 332.0);
uniform uint seed = 1995u;

float pixel_rand(uvec2 p) {
	// Ganzzahl-Hash: fester Wert je Bildpunkt, unabhängig von Zeit und Bildrate
	uint h = p.x * 374761393u + p.y * 668265263u + seed * 2246822519u;
	h = (h ^ (h >> 13u)) * 1274126177u;
	h = h ^ (h >> 16u);
	return float(h & 0xFFFFu) / 65535.0;
}

void fragment() {
	vec2 px = floor(UV * size);
	vec2 pa = floor(zoom_center + (px + 0.5 - zoom_center) / zoom_a);
	vec4 a = texture(tex_a, (pa + 0.5) / size);
	vec4 b = texture(tex_b, (px + 0.5) / size);
	COLOR = (pixel_rand(uvec2(px)) < mix_p) ? b : a;
}
