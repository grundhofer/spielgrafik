// Himmel + Meer aus EINER Clean Plate. Zeilenweise Parallaxe: Himmelszeilen bewegen sich kaum (f_sky),
// Meereszeilen vom Horizont (f_far) bis zur Kaikante (f_near) immer schneller, wie eine Bodenebene.
// Dazu Wellen (waagerechtes Versetzen, nach vorn stärker) und Glitzern im Abendlicht.
shader_type canvas_item;

uniform float cam_x = 0.0;
uniform float time_s = 0.0;
uniform vec2 tex_size = vec2(1454.0, 975.0);
uniform float horizon = 463.4;      // Texturzeile des Horizonts
uniform float quay = 685.0;         // Texturzeile der Kaikante
uniform float f_sky = 0.04;
uniform float f_far = 0.12;
uniform float f_near = 0.62;
uniform float glint = 1.0;

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void fragment() {
	vec2 px = UV * tex_size;
	float depth = clamp((px.y - horizon) / (quay - horizon), 0.0, 1.0);
	bool sea = px.y > horizon + 0.5;
	float f = sea ? mix(f_far, f_near, depth) : f_sky;
	vec2 q = px;
	q.x += cam_x * f;
	if (sea) {
		// Wellen: lange, flache Züge, vorn höher und langsamer
		float k = mix(0.9, 0.18, depth);
		float w = sin(px.y * k + time_s * mix(2.2, 1.1, depth)) + 0.5 * sin(px.y * k * 2.3 - time_s * 1.7 + px.x * 0.004);
		q.x += w * mix(0.6, 3.2, depth);
		q.y += 0.35 * sin(px.x * 0.02 + time_s * 1.3) * depth;
		q.y = max(q.y, horizon + 1.0);
	}
	vec4 c = texture(TEXTURE, q / tex_size);
	if (sea) {
		// Glitzern: kurze waagerechte Lichtstriche, nur im hellen Abendlicht des Wassers
		vec2 cell = vec2(floor((q.x) / mix(6.0, 22.0, depth)), floor(px.y / mix(1.5, 5.0, depth)));
		float h = hash(cell);
		float tw = 0.5 + 0.5 * sin(time_s * (2.0 + 3.0 * h) + h * 40.0);
		float lum = dot(c.rgb, vec3(0.3, 0.5, 0.2));
		float warm = clamp((c.r - c.b) * 3.0 + 0.2, 0.0, 1.0);
		float s = step(0.965, h) * pow(tw, 6.0) * smoothstep(0.35, 0.6, lum) * (1.0 - depth * 0.6);
		c.rgb += s * glint * mix(vec3(0.8, 0.9, 1.0), vec3(1.6, 1.1, 0.6), warm);
	}
	COLOR = c;
}
