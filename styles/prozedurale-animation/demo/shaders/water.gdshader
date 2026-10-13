shader_type canvas_item;
// Wasser im gemalten Hintergrund. Dieselbe Wellenfunktion wie für die Boote (scripts/waves.gd):
// h = Summe A sin(kx X + kz Z - w t + p), Z aus der Bildzeile (ebene Fläche, Kamera 2 m hoch).
uniform sampler2D mask_tex : filter_linear;
uniform vec4 w0;
uniform vec4 w1;
uniform vec4 w2;
uniform vec3 ph;
uniform float t;
uniform float horizon = 369.1;
uniform float F = 500.0;
uniform float D = 1000.0;
uniform float CX = 640.0;
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform float disp_gain = 0.35;
uniform vec3 crest_col : source_color = vec3(0.80, 0.86, 0.92);
uniform vec3 glint_col : source_color = vec3(1.0, 0.80, 0.52);
uniform float glint_x = 600.0;

float wv(vec4 w, float p, vec2 xz) {
	return w.w * sin(w.x * xz.x + w.y * xz.y - w.z * t + p);
}

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

// Weicher Strich in einer Zelle (cx: Spalte in Zellen, fy: Lage in der 3-px-Bildzeile): je Zelle eigene Länge
// und Mitte, Enden mit smoothstep ausgeblendet, zur Mitte dicker (wie ein kurzer Pinselstrich).
float stroke_a(float cx, float fy, float row, float s) {
	float cell = floor(cx);
	float fx = fract(cx);
	float half_len = 0.20 + 0.16 * hash12(vec2(cell + s, row + 17.0));
	float ctr = 0.5 + (hash12(vec2(cell + 5.0 + s, row)) - 0.5) * (1.0 - 2.0 * half_len);
	float along = abs(fx - ctr) / half_len;
	float a_len = 1.0 - smoothstep(0.25, 1.0, along);
	float thick = mix(0.34, 0.08, min(along * along, 1.0));
	float a_th = 1.0 - smoothstep(thick - 0.12, thick + 0.12, abs(fy - 0.5));
	return a_len * a_th;
}

void fragment() {
	vec2 px = UV * screen_size;
	vec4 base = texture(TEXTURE, UV);
	float m = texture(mask_tex, UV).r;
	float dy = max(px.y - horizon, 0.5);
	float Z = D / dy;
	float X = (px.x - CX) * Z / F;
	vec2 xz = vec2(X, Z);
	float h = wv(w0, ph.x, xz) + wv(w1, ph.y, xz) + wv(w2, ph.z, xz);
	float amp = w0.w + w1.w + w2.w;
	float hn = h / amp;
	// Gemalte Fläche mitbewegen: ganze Pixel, nur aus Wasserpixeln lesen
	float disp = -F * h / Z * disp_gain;
	vec2 uv2 = UV + vec2(0.0, round(disp) / screen_size.y);
	vec4 shifted = texture(TEXTURE, uv2);
	float m2 = texture(mask_tex, uv2).r;
	float wm = step(0.5, m);
	vec3 col = mix(base.rgb, shifted.rgb, wm * step(0.5, m2));
	// Wellentäler leicht dunkler, Kämme mit kurzen, weich auslaufenden Strichen (Raster in Bildzeilen gegen Flimmern)
	float row = floor(px.y / 3.0);
	float fy = fract(px.y / 3.0);
	float cellw = max(10.0, 34.0 * dy / 190.0);
	float cx = px.x / cellw + hash12(vec2(row, 7.0)) * 4.0;
	float cell = floor(cx);
	float dash = step(0.62, hash12(vec2(cell, row))) * stroke_a(cx, fy, row, 0.0);
	float crest = smoothstep(0.45, 0.85, hn) * dash;
	float trough = smoothstep(-0.3, -0.9, hn);
	float near = smoothstep(4.0, 40.0, dy);
	col *= 1.0 - 0.07 * trough * wm;
	col = mix(col, crest_col, crest * 0.55 * near * wm);
	// Glitzerbahn unter dem hellsten Teil des Abendhimmels
	float spread = 30.0 + dy * 0.9;
	float path = exp(-pow((px.x - glint_x) / spread, 2.0));
	float g = smoothstep(0.15, 0.7, hn) * step(0.45, hash12(vec2(cell + 31.0, row))) * stroke_a(cx, fy, row, 31.0);
	col = mix(col, glint_col, g * path * 0.7 * wm * (1.0 - smoothstep(60.0, 190.0, dy) * 0.6));
	COLOR = vec4(col, base.a);
}
