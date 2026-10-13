// Jugendstil – Schornsteinrauch als Ornamentband (Line2D, UV.x entlang 0..1, UV.y quer 0..1), gefärbt wie die
// Salbei-Wolkenbänder des Plakats: flache Fläche, gleich starke dunkle Kontur, eine abgesetzte Innenlinie. Die
// Innenlinie läuft als flache Welle das Band entlang nach außen (der Shader verschiebt das Muster entlang der
// Linie) und trennt eine hellere Ober- von einer dunkleren Unterseite; vor der Spitze läuft sie aus.
// Kantenglättung: Alpha über den Abstand zum Bandrand in Bildschirmpixeln (Gradient von UV.y), die Kontur hat
// über die ganze Länge dieselbe Pixelbreite; am spitzen Ende laufen beide Konturen zu einem dunklen Punkt zusammen.
shader_type canvas_item;

uniform float t = 0.0;
uniform vec3 key_col = vec3(0.129, 0.122, 0.055);
uniform vec3 sage_a = vec3(0.56, 0.55, 0.40);    // wie die hellen Salbei-Wolkenbänder
uniform vec3 sage_b = vec3(0.46, 0.48, 0.36);    // wie die dunkleren
uniform float line_px = 2.0;
uniform float flow = 0.5;

void fragment() {
	float v = UV.y;
	float u = UV.x;
	float gv = max(length(vec2(dFdx(v), dFdy(v))), 1e-4);    // UV.y je Bildschirmpixel
	float edge = min(v, 1.0 - v) / gv;                       // Abstand zum Bandrand in Pixeln
	float fade = 1.0 - smoothstep(0.78, 0.9, u);
	float vc = 0.34 + 0.08 * sin(6.2831853 * (4.0 * u - flow * t));
	vec3 col = mix(sage_a, sage_b, smoothstep(vc - gv * 0.5, vc + gv * 0.5, v) * fade);
	float w_in = line_px * 0.5 * fade;
	float k_in = (1.0 - smoothstep(w_in - 0.5, w_in + 0.5, abs(v - vc) / gv)) * fade;
	float k_out = 1.0 - smoothstep(line_px - 0.5, line_px + 0.5, edge);
	col = mix(col, key_col, max(k_out, k_in));
	COLOR = vec4(col, clamp(edge, 0.0, 1.0) * COLOR.a);
}
