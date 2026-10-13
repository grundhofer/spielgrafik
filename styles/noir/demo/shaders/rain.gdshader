// Regen über der ganzen Szene (auch vor der Figur), additiv. Drei Tiefenlagen schräger Striche; sichtbar vor
// allem im Gegenlicht und im Schein der Laterne (Lichtfeld aus fx_mask.g, Laterne flackert mit). Dazu Spritzer
// auf dem Pflaster (aux_mask.g) und Ringe auf dem Wasser (fx_mask.b). Alles aus der Zeit t und festen
// Zellen-Hashes, also deterministisch.
shader_type canvas_item;
render_mode blend_add;

uniform sampler2D fx_mask : filter_linear;   // R Laterne, G Lichtfeld, B Wasser
uniform sampler2D aux_mask : filter_linear;  // G Pflaster
uniform float t = 0.0;
uniform float flicker = 1.0;
uniform vec2 lantern = vec2(771.7, 191.7);
uniform float horizon_y = 345.8;
uniform float quay_y = 468.3;
uniform float wind = 0.16;                   // Neigung der Striche (dx/dy)
uniform float amount = 1.0;
uniform vec2 view_size = vec2(1280.0, 720.0);

float h1(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

// Eine Lage Regenstriche. cell: Zellgröße (px), len: Strichlänge, speed: px/s, width: halbe Strichbreite.
float rain_layer(vec2 p, vec2 cell, float len, float speed, float width, float seed) {
	// in ein schräges Gitter drehen, damit die Striche mit dem Wind fallen
	vec2 q = vec2(p.x - wind * p.y, p.y);
	float col = floor(q.x / cell.x);
	float ofs = h1(vec2(col, seed)) * 1000.0;
	float y = q.y - t * speed + ofs;
	float row = floor(y / cell.y);
	vec2 id = vec2(col, row);
	float r = h1(id + seed * 7.3);
	if (r > 0.55) return 0.0;                  // nicht jede Zelle hat einen Tropfen
	float cx = (col + 0.2 + 0.6 * h1(id + 3.1 + seed)) * cell.x;
	float cy = fract(y / cell.y) * cell.y;
	float head = cell.y * (0.15 + 0.7 * h1(id + 9.7 + seed));
	float along = (head - cy) / len;            // 0 am Kopf, 1 am Ende des Strichs
	float a = smoothstep(0.0, 0.08, along) * (1.0 - smoothstep(0.55, 1.0, along));
	float d = abs(q.x - cx);
	return a * (1.0 - smoothstep(width * 0.5, width + 0.6, d)) * (0.55 + 0.45 * h1(id + 5.5));
}

void fragment() {
	vec2 p = UV * view_size;
	vec4 m = vec4(texture(fx_mask, UV).rgb, texture(aux_mask, UV).g);
	float dl = length(p - lantern);
	float lamp_cone = exp(-dl * dl / (2.0 * 120.0 * 120.0)) * flicker;
	float light = 0.10 + 1.25 * m.g + 0.9 * lamp_cone;

	float r = 0.0;
	r += rain_layer(p, vec2(9.0, 110.0), 26.0, 820.0, 0.45, 1.0) * 0.30;    // fern: fein, kurz
	r += rain_layer(p, vec2(17.0, 170.0), 46.0, 1150.0, 0.65, 2.0) * 0.45;  // mittel
	r += rain_layer(p, vec2(41.0, 300.0), 90.0, 1650.0, 1.0, 3.0) * 0.55;   // nah: lang, kräftig
	float c = r * light * amount;

	// Spritzer auf dem Pflaster: kurze helle Kronen, kleiner zum Horizont hin
	if (m.a > 0.01) {
		float sc = clamp((p.y - horizon_y) / 300.0, 0.25, 1.2);
		vec2 cell = vec2(26.0, 12.0) * sc;
		vec2 id = floor(p / cell);
		float ph = h1(id + 0.37);
		float per = 0.45 + 0.6 * h1(id + 4.2);
		float k = fract(t / per + ph);
		vec2 ctr = (id + vec2(0.2 + 0.6 * h1(id + 1.9), 0.5)) * cell;
		vec2 d = (p - ctr) / vec2(3.2 * sc, 1.4 * sc);
		float ring = 1.0 - smoothstep(0.6, 1.2, abs(length(d) - k * 1.6));
		float life = (1.0 - smoothstep(0.0, 0.16, k)) * step(0.35, h1(id + 8.8));
		c += ring * life * m.a * (0.18 + 1.1 * m.g + 0.7 * lamp_cone) * amount;
	}
	// Ringe auf dem Wasser: flache, wachsende Ellipsen
	if (m.b > 0.01 && p.y > horizon_y + 22.0) {
		float sc = clamp((p.y - horizon_y) / 110.0, 0.3, 1.2);
		vec2 cell = vec2(38.0, 9.0) * sc;
		float rowj = h1(vec2(floor(p.y / cell.y), 4.4)) * cell.x;   // Reihen gegeneinander versetzen
		vec2 id = floor((p + vec2(rowj, 0.0)) / cell);
		float per = 0.7 + 0.8 * h1(id + 2.3);
		float k = fract(t / per + h1(id + 6.1));
		vec2 ctr = (id + vec2(0.25 + 0.5 * h1(id + 7.7), 0.5)) * cell - vec2(rowj, 0.0);
		vec2 d = (p - ctr) / vec2(1.0, 0.28);
		float rad = (1.0 + k * 7.0) * sc;
		float ring = 1.0 - smoothstep(0.0, 0.9, abs(length(d) - rad));
		float life = (1.0 - k) * step(0.72, h1(id + 3.3));
		c += ring * life * m.b * (0.10 + 0.8 * m.g) * amount;
	}
	COLOR = vec4(vec3(c), 1.0);
}
