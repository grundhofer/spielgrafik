// Himmel und Wasser hinter allen Papierebenen: farbiger Grund des Schattentheaters.
// Himmel: Dämmerungsverlauf mit Sternen und feinem Papierkorn. Wasser: gespiegelter, abgedunkelter
// Himmel mit Spiegelung der fernen Küste und der Landzunge, Glitzerstrichen und Lichtsäule unter dem
// Leuchtfeuer. Verschiebungen nur um ganze Pixel (sonst verwischen die Striche).
shader_type canvas_item;

uniform float t = 0.0;
uniform vec2 size = vec2(1280.0, 720.0);
uniform float horizon = 278.5;
uniform float quay = 574.0;
uniform float wl[80];          // Wasserlinie der Landzunge je 16-px-Spalte (0 = keine)
uniform vec2 lamp = vec2(1137.0, 118.0);
uniform float lamp_flash = 0.0;
uniform sampler2D far_tex : filter_linear;
uniform sampler2D head_tex : filter_linear;
uniform vec3 far_refl = vec3(0.70, 0.42, 0.48);
uniform vec3 head_refl = vec3(0.42, 0.25, 0.38);

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec3 sky_col(float y) {
	float h = clamp(y / horizon, 0.0, 1.0);
	vec3 c0 = vec3(0.075, 0.075, 0.19);
	vec3 c1 = vec3(0.19, 0.14, 0.33);
	vec3 c2 = vec3(0.49, 0.26, 0.45);
	vec3 c3 = vec3(0.86, 0.44, 0.38);
	vec3 c4 = vec3(0.97, 0.69, 0.42);
	vec3 c5 = vec3(1.0, 0.86, 0.58);
	vec3 c = mix(c0, c1, smoothstep(0.0, 0.38, h));
	c = mix(c, c2, smoothstep(0.30, 0.68, h));
	c = mix(c, c3, smoothstep(0.60, 0.86, h));
	c = mix(c, c4, smoothstep(0.82, 0.96, h));
	c = mix(c, c5, smoothstep(0.95, 1.0, h));
	return c;
}

void fragment() {
	vec2 px = floor(UV * size) + 0.5;
	float y = px.y;
	// Texturen vor allen Verzweigungen abtasten
	float d = max(y - horizon, 0.0);
	float depth = clamp(d / (quay - horizon), 0.0, 1.0);
	float row = floor(y / 2.0);
	float wob = floor(2.6 * sin(row * 0.83 + t * 1.7) * (0.35 + 1.4 * depth) + 0.5);
	float far_a = texture(far_tex, vec2(px.x + wob, 2.0 * horizon - y) / size).a;
	int ci = clamp(int(px.x / 16.0), 0, 79);
	int cj = clamp(ci + 1, 0, 79);
	float fx = clamp(px.x / 16.0 - float(ci) - 0.5, 0.0, 1.0);
	float hw = mix(wl[ci], wl[cj] > 0.0 ? wl[cj] : wl[ci], fx);
	float head_a = texture(head_tex, vec2(px.x + wob, 2.0 * hw - y + 2.0) / size).a;

	vec3 c;
	if (y < horizon) {
		c = sky_col(y);
		// Sterne: ein Stern je Zelle mit 35 % Wahrscheinlichkeit, nur im dunklen oberen Himmel
		vec2 cell = floor(px / 26.0);
		float r = hash12(cell + 7.0);
		vec2 sp = cell * 26.0 + vec2(hash12(cell + 1.3), hash12(cell + 4.1)) * 22.0 + 2.0;
		float sd = length(px - sp);
		float tw = 0.55 + 0.45 * sin(t * (1.3 + 2.4 * hash12(cell + 9.0)) + r * 40.0);
		float big = step(0.9, hash12(cell + 2.2));
		float star = (1.0 - smoothstep(0.5 + big * 0.6, 1.2 + big * 0.9, sd)) * step(r, 0.35);
		star *= tw * (1.0 - smoothstep(horizon * 0.25, horizon * 0.62, y));
		c = mix(c, vec3(1.0, 0.93, 0.78), star * 0.9);
	} else {
		// Wasser als heller Grund hinter der Puppe: spiegelt das Abendlicht, zum Kai hin rosig-mauve
		vec3 w0 = vec3(1.0, 0.82, 0.56);
		vec3 w1 = vec3(0.95, 0.60, 0.46);
		vec3 w2 = vec3(0.78, 0.47, 0.53);
		vec3 w3 = vec3(0.56, 0.34, 0.48);
		c = mix(w0, w1, smoothstep(0.0, 0.2, depth));
		c = mix(c, w2, smoothstep(0.15, 0.6, depth));
		c = mix(c, w3, smoothstep(0.55, 1.0, depth));
		float fa = far_a * step(2.0 * horizon - y, horizon);
		c = mix(c, far_refl, fa * 0.6 * (1.0 - depth));
		float ha = head_a * step(hw, y) * step(1.0, hw);
		c = mix(c, head_refl, ha * 0.55);
		// Glitzerstriche: Bänder von 2 px, je Zelle ein Strich, der auf- und abblendet
		float band = floor(y / 2.0);
		float cw = mix(26.0, 90.0, depth);
		float xs = px.x + floor(t * 9.0 * (1.0 - 0.5 * depth)) * (mod(band, 2.0) * 2.0 - 1.0);
		float cx = floor(xs / cw);
		float h1 = hash12(vec2(cx, band));
		float h2 = hash12(vec2(cx + 31.0, band));
		float len = mix(4.0, 22.0, h2) * (0.6 + depth);
		float off = h1 * (cw - len);
		float inx = step(off, xs - cx * cw) * step(xs - cx * cw, off + len);
		float blink = smoothstep(0.35, 1.0, sin(t * (0.9 + 1.8 * h2) + h1 * 30.0) * 0.5 + 0.5);
		float dens = step(hash12(vec2(band, 3.0)), 0.55 - 0.25 * depth);
		vec3 gl = mix(vec3(1.0, 0.93, 0.74), vec3(0.98, 0.78, 0.74), depth);
		c = mix(c, gl, inx * blink * dens * 0.6 * (1.0 - 0.4 * depth));
		// Lichtsäule unter dem Leuchtfeuer (rechts) - dichtere, hellere Striche
		float col = exp(-pow((px.x - lamp.x) / (10.0 + 30.0 * depth), 2.0));
		float lh = hash12(vec2(floor((px.x + floor(t * 5.0)) / 6.0), band));
		float lflick = step(0.55, lh) * step(hw + 2.0, y);
		c = mix(c, vec3(1.0, 0.9, 0.6), col * lflick * (0.35 + 0.5 * lamp_flash));
	}
	// Papierkorn des Leuchttischs
	float g = hash12(px) - 0.5;
	float fib = hash12(vec2(floor(px.x / 3.0), floor(px.y / 9.0) + 50.0)) - 0.5;
	c *= 1.0 + g * 0.035 + fib * 0.025;
	COLOR = vec4(c, 1.0);
}
