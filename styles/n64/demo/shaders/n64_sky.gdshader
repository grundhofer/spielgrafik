// Abendhimmel im N64-Look: Farbverlauf nach Höhe, ein Wolkenband (128×32) und Sterne (64×32), beide
// 3-Punkt-gefiltert und dadurch weich. Am Horizont genau die Nebelfarbe, damit Meer und Inseln im Dunst
// verschwinden.
shader_type sky;

#include "res://shaders/n64_common.gdshaderinc"

uniform sampler2D clouds : source_color, filter_nearest, repeat_enable;
uniform sampler2D stars : source_color, filter_nearest, repeat_enable;     // 256×128, zweimal herum
uniform vec4 c_low : source_color = vec4(0.88, 0.52, 0.48, 1.0);     // ca. 6°
uniform vec4 c_mid : source_color = vec4(0.62, 0.4, 0.62, 1.0);     // ca. 16°
uniform vec4 c_high : source_color = vec4(0.25, 0.3, 0.6, 1.0);    // ca. 32°
uniform vec4 c_top : source_color = vec4(0.08, 0.12, 0.32, 1.0);     // Zenit
uniform float cloud_top_deg = 20.0;
uniform float cloud_repeat = 3.0;
uniform float star_from_deg = 22.0;

void sky() {
	vec3 d = normalize(EYEDIR);
	float el = degrees(asin(clamp(d.y, -1.0, 1.0)));
	float az = atan(d.x, -d.z);                              // 0 = Blickrichtung der Hauptkamera (−Z)
	vec3 hz = n64_fog_color.rgb;
	// Abendglühen: zur Sonne hin (links hinten) heller und gelber
	vec2 sun_h = normalize(-n64_sun_dir.xz);
	float toward = max(dot(normalize(d.xz + 1e-5), sun_h), 0.0);
	vec3 low = mix(c_low.rgb, hz, 0.25 * toward);
	vec3 c;
	if (el <= 0.0) {
		c = hz;
	} else if (el < 6.0) {
		c = mix(hz, low, smoothstep(0.0, 6.0, el));
	} else if (el < 16.0) {
		c = mix(low, c_mid.rgb, smoothstep(6.0, 16.0, el));
	} else if (el < 32.0) {
		c = mix(c_mid.rgb, c_high.rgb, smoothstep(16.0, 32.0, el));
	} else {
		c = mix(c_high.rgb, c_top.rgb, smoothstep(32.0, 75.0, el));
	}
	// Sterne
	if (el > star_from_deg) {
		vec2 suv = vec2(az / 6.2831853 * 2.0, 1.0 - (el - star_from_deg) / (90.0 - star_from_deg));
		vec4 s = n64_filter_level(stars, suv, 0);
		c += s.rgb * s.a * smoothstep(star_from_deg, star_from_deg + 12.0, el) * 0.9;
	}
	// Wolkenband über dem Horizont
	if (el > 0.0 && el < cloud_top_deg) {
		vec2 cuv = vec2(az / 6.2831853 * cloud_repeat + 0.13, el / cloud_top_deg);
		cuv.y = 1.0 - cuv.y;
		vec4 cl = n64_filter_level(clouds, cuv, 0);
		float near_hz = smoothstep(0.0, 4.0, el);
		c = mix(c, mix(hz, cl.rgb, near_hz), cl.a * 0.9);
	}
	COLOR = c;
}
