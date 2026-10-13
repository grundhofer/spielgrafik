// Nylonfaden der Spielzeugmöwen: ein dünner Zylinder (1,2 cm), der in der Totale unter einen Pixel fällt und
// dann als gestrichelte Linie flimmern würde. Der Vertex-Shader verbreitert ihn deshalb im Kameraraum auf
// mindestens min_px Pixel und senkt die Deckkraft im selben Verhältnis (gleiche "Menge" Faden je Pixel).
// Die Pixelgröße kommt als Uniform aus main.gd: VIEWPORT_SIZE/PROJECTION_MATRIX im Vertex-Shader ergaben
// im Test keine Verbreiterung.
shader_type spatial;
render_mode unshaded, blend_mix, cull_disabled, depth_draw_never, skip_vertex_transform, fog_disabled;

uniform vec4 color : source_color = vec4(0.9, 0.92, 0.95, 0.55);
uniform float radius = 0.006;
uniform float min_px = 2.0;
uniform float m_per_px = 0.0007;    // Meter je Pixel in 1 m Abstand (main.gd setzt 2·tan(fov/2)/Bildhöhe)

varying float cover;

void vertex() {
	vec3 v = (MODELVIEW_MATRIX * vec4(VERTEX, 1.0)).xyz;
	vec3 n = normalize((MODELVIEW_MATRIX * vec4(NORMAL, 0.0)).xyz);
	float px = -v.z * m_per_px;   // Meter je Pixel in dieser Tiefe
	float want = max(radius, 0.5 * min_px * px);
	VERTEX = v + n * (want - radius);
	NORMAL = n;
	cover = radius / want;
}

void fragment() {
	ALBEDO = color.rgb;
	ALPHA = color.a * clamp(cover * 1.6, 0.08, 1.0);
}
