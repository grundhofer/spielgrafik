// Abendhimmel für den Voxel-Hafen: Verlauf in vier Zonen, Glut am Horizont, Sterne als kleine Quadrate
// (Zellen in Richtungskoordinaten), die im 1/5-s-Takt funkeln. Unter dem Horizont Meeresfarbe.
shader_type sky;

uniform float time_s = 0.0;
uniform vec3 top_col : source_color = vec3(0.07, 0.10, 0.27);
uniform vec3 mid_col : source_color = vec3(0.28, 0.24, 0.48);
uniform vec3 low_col : source_color = vec3(0.80, 0.47, 0.50);
uniform vec3 glow_col : source_color = vec3(1.0, 0.66, 0.36);
uniform vec3 sea_col : source_color = vec3(0.10, 0.20, 0.30);
uniform float star_cells = 260.0;

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void sky() {
	vec3 d = EYEDIR;
	float y = d.y;
	vec3 c = mix(glow_col, low_col, smoothstep(0.0, 0.07, y));
	c = mix(c, mid_col, smoothstep(0.05, 0.25, y));
	c = mix(c, top_col, smoothstep(0.22, 0.6, y));
	// Glut links (Sonne gerade untergegangen, Westen = -x)
	float side = clamp(-d.x * 0.5 + 0.5, 0.0, 1.0);
	c += glow_col * 0.35 * side * (1.0 - smoothstep(0.0, 0.16, y));
	// Sterne: quadratische Zellen im Winkelraum
	vec2 a = vec2(atan(d.x, -d.z), asin(clamp(y, -1.0, 1.0))) * star_cells / 3.14159;
	vec2 ci = floor(a);
	float h = hash12(ci);
	float star = step(0.9965, h) * smoothstep(0.16, 0.4, y);
	vec2 f = fract(a);
	float inside = step(0.25, f.x) * step(f.x, 0.75) * step(0.25, f.y) * step(f.y, 0.75);
	float tw = 0.65 + 0.35 * step(0.5, hash12(ci + floor(time_s * 5.0)));
	c += vec3(1.0, 0.95, 0.85) * star * inside * tw * 1.4;
	if (y < 0.0) {
		c = mix(glow_col * 0.5, sea_col, smoothstep(-0.02, -0.12, y));
	}
	COLOR = c;
}
