// Gemeinsame Bausteine des N64-Looks (globale Uniforms in project.godot, gesetzt von main.gd).
//
// n64_tex():   3-Punkt-Filter wie im Texturfilter der Konsole: Aus den vier Nachbartexeln werden nur drei
//              gemischt (das Dreieck, in dem der Abtastpunkt liegt), mit Mipmaps zwischen zwei Stufen
//              überblendet (trilinear). texelFetch umgeht Godots Sampler; n64_three_point = 0 schaltet zum
//              Vergleich auf gewöhnliches bilineares Filtern mit vier Texeln.
// n64_fog():   Nebel je Eckpunkt aus der Tiefe (wird über das Dreieck interpoliert wie auf der Konsole).
// n64_light(): Licht je Eckpunkt (Gouraud): Himmels- und Bodenlicht, Abendsonne, Fensterlicht, Laterne.

global uniform float n64_three_point;
global uniform float n64_mip;
global uniform float n64_fog_on;
global uniform float n64_vc_on;
global uniform vec4 n64_fog_color;
global uniform vec2 n64_fog_range;
global uniform float n64_fog_max;
global uniform vec4 n64_sky_light;
global uniform vec4 n64_ground_light;
global uniform vec3 n64_sun_dir;
global uniform vec4 n64_sun_color;
global uniform float n64_sun_energy;
global uniform vec4 n64_window_color;
global uniform vec3 n64_window_pos;
global uniform vec4 n64_lantern_color;
global uniform vec3 n64_lantern_pos;
global uniform float n64_lantern_energy;
global uniform float n64_lantern_range;
global uniform float n64_time;
global uniform float n64_tex_nearest;   // Messschalter: Texel ohne Filter (wie ohne Bilinearfilter)
global uniform float n64_debug;          // Messschalter: 1/2/3 zeigt gebackenes AO/Sonne/Fenster ohne Textur

vec4 n64_fetch(sampler2D t, ivec2 p, ivec2 sz, int lod) {
	vec2 w = mod(vec2(p), vec2(sz));
	return texelFetch(t, ivec2(w), lod);
}

vec4 n64_filter_level(sampler2D t, vec2 uv, int lod) {
	ivec2 sz = textureSize(t, lod);
	vec2 pp = uv * vec2(sz) - 0.5;
	vec2 fl = floor(pp);
	vec2 f = pp - fl;
	ivec2 i = ivec2(fl);
	if (n64_tex_nearest > 0.5) {
		return n64_fetch(t, ivec2(floor(uv * vec2(sz))), sz, lod);
	}
	vec4 a = n64_fetch(t, i, sz, lod);
	vec4 b = n64_fetch(t, i + ivec2(1, 0), sz, lod);
	vec4 c = n64_fetch(t, i + ivec2(0, 1), sz, lod);
	vec4 d = n64_fetch(t, i + ivec2(1, 1), sz, lod);
	if (n64_three_point > 0.5) {
		if (f.x + f.y <= 1.0) {
			return a + f.x * (b - a) + f.y * (c - a);
		}
		return d + (1.0 - f.x) * (c - d) + (1.0 - f.y) * (b - d);
	}
	return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

vec4 n64_tex(sampler2D t, vec2 uv) {
	vec2 sz0 = vec2(textureSize(t, 0));
	if (n64_mip < 0.5) {
		return n64_filter_level(t, uv, 0);
	}
	vec2 dx = dFdx(uv * sz0);
	vec2 dy = dFdy(uv * sz0);
	float rho = max(length(dx), length(dy));
	float max_lod = log2(min(sz0.x, sz0.y));
	float lod = clamp(log2(max(rho, 1e-6)), 0.0, max_lod);
	int l0 = int(floor(lod));
	float fr = lod - float(l0);
	vec4 c0 = n64_filter_level(t, uv, l0);
	if (fr < 0.002 || float(l0) >= max_lod) {
		return c0;
	}
	return mix(c0, n64_filter_level(t, uv, l0 + 1), fr);
}

float n64_fog(float depth) {
	if (n64_fog_on < 0.5) {
		return 0.0;
	}
	float f = clamp((depth - n64_fog_range.x) / (n64_fog_range.y - n64_fog_range.x), 0.0, 1.0);
	return f * n64_fog_max;
}

vec3 n64_hemi(vec3 n) {
	return mix(n64_ground_light.rgb, n64_sky_light.rgb, clamp(n.y * 0.5 + 0.5, 0.0, 1.0));
}

// Punktlicht je Eckpunkt mit weichem Abfall bis range.
float n64_point(vec3 p, vec3 n, vec3 lp, float range) {
	vec3 l = lp - p;
	float d = length(l);
	if (d >= range) {
		return 0.0;
	}
	float ndl = max(dot(n, l / max(d, 1e-4)), 0.0);
	float x = d / range;
	float fall = (1.0 - x * x) * (1.0 - x * x) / (1.0 + 0.8 * d * d);
	return (0.3 + 0.7 * ndl) * fall;
}

vec3 n64_lantern(vec3 p, vec3 n) {
	return n64_lantern_color.rgb * n64_lantern_energy * n64_point(p, n, n64_lantern_pos, n64_lantern_range);
}
