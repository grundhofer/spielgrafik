shader_type spatial;
// Facettiertes Wasser: ein unregelmäßiges Dreiecksnetz (main.gd, _build_water), dessen Eckpunkte von
// wenigen Sinuswellen in Weltkoordinaten gehoben werden. Jede Facette ist flach (Normale aus den
// Ableitungen), ihre Neigung wird für das Licht überhöht (tilt_gain), damit sich die Facetten deutlich
// voneinander abheben, ohne dass die Wellen hoch werden. Dazu eine Farbe je Facette aus der
// Wellenhöhe am führenden Eckpunkt (flat varying): Kämme heller, Täler dunkler.
render_mode diffuse_lambert, specular_schlick_ggx, cull_disabled;

global uniform float lp_time;
global uniform vec4 sky_low;

uniform vec3 trough_color : source_color = vec3(0.2, 0.42, 0.56);
uniform vec3 crest_color : source_color = vec3(0.38, 0.66, 0.72);
uniform vec3 far_color : source_color = vec3(0.47, 0.45, 0.68);
uniform float amplitude = 0.14;
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float fade_start = 45.0;      // ab hier werden die Wellen flacher (das Netz wird gröber)
uniform float fade_end = 140.0;
uniform float tilt_gain = 3.0;
uniform float flat_shading = 1.0;
uniform float roughness = 0.3;
uniform float specular = 0.35;

varying vec3 wpos;
varying flat float vh;       // Wellenhöhe (−1..1) am führenden Eckpunkt: eine Farbe je Facette
varying float wave_fade;

float waves(vec2 p, float t) {
	float h = 0.0;
	h += sin(dot(p, vec2(0.62, 0.3)) + t * 1.4) * 0.42;
	h += sin(dot(p, vec2(-0.35, 0.82)) + t * 1.75 + 1.3) * 0.3;
	h += sin(dot(p, vec2(1.15, -0.62)) + t * 2.3 + 0.4) * 0.18;
	h += sin(dot(p, vec2(-1.3, -1.1)) + t * 2.9 + 2.0) * 0.1;
	return h;
}

void vertex() {
	vec3 w = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	wave_fade = 1.0 - smoothstep(fade_start, fade_end, length(w.xz - harbor_center));
	float h = waves(w.xz, lp_time);
	vh = h * wave_fade;
	VERTEX.y += h * amplitude * wave_fade;
	wpos = w + vec3(0.0, h * amplitude * wave_fade, 0.0);
}

void fragment() {
	vec3 fn = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	if (dot(fn, VERTEX) > 0.0) {
		fn = -fn;
	}
	// Neigung in Weltkoordinaten überhöhen (nur für Licht und Farbe, nicht für die Geometrie)
	vec3 wn = normalize((INV_VIEW_MATRIX * vec4(fn, 0.0)).xyz);
	float g = mix(1.0, tilt_gain, flat_shading);
	wn = normalize(vec3(wn.x * g, wn.y, wn.z * g));
	vec3 n = (VIEW_MATRIX * vec4(wn, 0.0)).xyz;
	NORMAL = normalize(mix(NORMAL, n, flat_shading));

	float dist = length(wpos.xz - vec2(-1.8, 14.5));
	float k = smoothstep(18.0, 110.0, dist);
	float hv = mix(0.0, vh, flat_shading);
	vec3 c = mix(trough_color, crest_color, smoothstep(-0.7, 0.7, hv));
	c = mix(c, far_color, k);
	ALBEDO = c;
	ROUGHNESS = roughness;
	SPECULAR = specular;
}
