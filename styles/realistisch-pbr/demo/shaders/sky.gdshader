shader_type sky;
// HDRI-Himmel (Poly Haven, CC0) mit zwei Auflösungen:
//  - sky_full (1024×512, ganzes Panorama) für Umgebungslicht und Spiegelungen (Radiance-Cubemap)
//  - sky_band (Ausschnitt aus dem 4k-HDRI, -8° bis 40° Höhe, ±80° um die Blickrichtung) für den
//    sichtbaren Himmel hinter der Szene. So bleibt der Hintergrund scharf, ohne das ganze 4k-Bild
//    mitzuliefern.
#include "res://sky/sky_params.gdshaderinc"

uniform sampler2D sky_full : filter_linear, repeat_enable;
uniform sampler2D sky_band : filter_linear_mipmap, repeat_disable;
uniform float exposure = 1.0;
uniform float bg_exposure = 1.0;      // nur der sichtbare Hintergrund (nicht das Umgebungslicht)
uniform vec3 grade = vec3(1.0);       // Farbabgleich des Himmels
// Abendstimmung: das HDRI ist ein bedeckter Sonnenuntergang; zum Zenit hin kühler und dunkler,
// am Horizont wärmer (wirkt auch auf Umgebungslicht und Spiegelungen, weil es im Cubemap-Pass gilt)
uniform vec3 zenith_tint = vec3(1.0);
uniform vec3 horizon_tint = vec3(1.0);
uniform float tint_curve = 0.5;

vec2 pano_uv(vec3 d) {
	float u = fract(atan(d.x, -d.z) / TAU + SKY_U_OFFSET);
	float v = acos(clamp(d.y, -1.0, 1.0)) / PI;
	return vec2(u, v);
}

void sky() {
	vec3 d = normalize(EYEDIR);
	vec2 uv = pano_uv(d);
	vec3 c = texture(sky_full, uv).rgb;
	if (!AT_CUBEMAP_PASS) {
		vec2 b = vec2((uv.x - BAND_U.x) / (BAND_U.y - BAND_U.x), (uv.y - BAND_V.x) / (BAND_V.y - BAND_V.x));
		// Ableitungen aus der Richtung statt aus uv (atan-Naht liegt hinter der Kamera)
		vec3 cb = textureLod(sky_band, b, 0.0).rgb;
		float inside = smoothstep(0.0, 0.04, b.x) * smoothstep(1.0, 0.96, b.x)
				* smoothstep(0.0, 0.05, b.y) * smoothstep(1.0, 0.95, b.y);
		c = mix(c, cb, inside) * bg_exposure;
	}
	float e = pow(clamp(d.y, 0.0, 1.0), tint_curve);
	c *= mix(horizon_tint, zenith_tint, e);
	COLOR = c * exposure * grade;
}
