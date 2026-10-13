// HD-2D: Pixel-Texturen auf den 3D-Modellen aus shared/3d.
// Projektion auf die dominante Achse der Normale (kein Überblenden, damit jedes Texel ein klares Quadrat bleibt),
// festes Raster für alle Flächen (globales px_per_m = Texel je Meter), Nearest mit Mipmaps.
// Die Normal Map (aus der Helligkeit der Textur gerechnet, scripts/build_textures.py) lässt Laterne und
// Fensterlicht an den Kanten der gepixelten Steine und Bretter hängen bleiben.
// Bewegte Objekte (Boote) projizieren im Objektraum, damit die Textur mitschaukelt.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

global uniform float px_per_m;

uniform sampler2D albedo_tex : source_color, filter_nearest_mipmap, repeat_enable;
uniform sampler2D normal_tex : hint_normal, filter_nearest_mipmap, repeat_enable;
uniform bool has_tex = false;
uniform bool has_normal = false;
uniform vec4 albedo : source_color = vec4(1.0);
uniform float tex_px = 64.0;            // Kantenlänge der Kachel in Texeln
uniform float density = 1.0;            // Faktor auf px_per_m (z. B. feinere Taue)
uniform float normal_strength = 0.6;
uniform float roughness : hint_range(0.0, 1.0) = 0.9;
uniform float metallic : hint_range(0.0, 1.0) = 0.0;
uniform float specular : hint_range(0.0, 1.0) = 0.3;
uniform vec3 emission = vec3(0.0);
uniform bool object_space = false;
uniform vec2 offset_m = vec2(0.0);
uniform float variation = 0.16;         // großflächige Helligkeitsschwankung gegen sichtbare Kachelwiederholung
uniform vec3 variation_tint : source_color = vec3(0.86, 0.95, 0.80);   // dunkle Flecken leicht moosig

varying vec3 p_tex;
varying vec3 n_tex;

float hash3(vec3 p) {
	p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 p) {
	vec3 i = floor(p), f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), f.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), f.x), f.y),
		mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), f.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), f.x), f.y), f.z);
}

void vertex() {
	if (object_space) {
		p_tex = VERTEX;
		n_tex = NORMAL;
	} else {
		p_tex = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
		n_tex = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	}
}

void fragment() {
	vec3 n = normalize(n_tex);
	vec3 an = abs(n);
	// Ebene wählen: oben/unten -> (x, z), Seitenwände -> (x oder z, -y). T/B: Richtung von u und v im Raum.
	vec2 pm;
	vec3 T, B;
	if (an.y >= an.x && an.y >= an.z) {
		pm = vec2(p_tex.x, p_tex.z);
		T = vec3(1.0, 0.0, 0.0);
		B = vec3(0.0, 0.0, 1.0);
	} else if (an.x >= an.z) {
		pm = vec2(-p_tex.z * sign(n.x), -p_tex.y);
		T = vec3(0.0, 0.0, -sign(n.x));
		B = vec3(0.0, -1.0, 0.0);
	} else {
		pm = vec2(p_tex.x * sign(n.z), -p_tex.y);
		T = vec3(sign(n.z), 0.0, 0.0);
		B = vec3(0.0, -1.0, 0.0);
	}
	float k = px_per_m * density / tex_px;
	vec2 uv = (pm + offset_m) * k;
	// Mip-Stufe aus der stetigen Position (die Ebenenwahl springt, die Position nicht)
	float d = max(length(dFdx(p_tex)), length(dFdy(p_tex))) * px_per_m * density;
	float lod = log2(max(d, 1e-4));
	vec4 c = has_tex ? textureLod(albedo_tex, uv, lod) : vec4(1.0);
	vec3 nm = has_normal ? textureLod(normal_tex, uv, lod).rgb * 2.0 - 1.0 : vec3(0.0, 0.0, 1.0);
	// Schwankung je Texel (Position auf das Texelraster gerastert, damit die Pixel einfarbig bleiben)
	vec3 ps = (floor(p_tex * px_per_m * density) + 0.5) / (px_per_m * density);
	float nv = vnoise(ps * 0.45) * 0.65 + vnoise(ps * 1.3 + 7.0) * 0.35;
	float shade = 1.0 + variation * (nv - 0.5) * 2.0;
	vec3 tint = mix(variation_tint, vec3(1.0), smoothstep(0.25, 0.6, nv));
	ALBEDO = c.rgb * albedo.rgb * shade * mix(vec3(1.0), tint, variation * 3.0);
	if (has_normal) {
		// Normal Map: x nach rechts (u), y nach oben im Bild (= -v); in Welt bzw. Objektraum biegen
		vec3 nw = normalize(n * nm.z + (T * nm.x - B * nm.y) * normal_strength);
		if (object_space) {
			nw = normalize((MODEL_MATRIX * vec4(nw, 0.0)).xyz);
		}
		NORMAL = normalize((VIEW_MATRIX * vec4(nw, 0.0)).xyz);
	}
	ROUGHNESS = roughness;
	METALLIC = metallic;
	SPECULAR = specular;
	EMISSION = emission;
}
