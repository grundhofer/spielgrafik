shader_type sky;
// Farbverlauf-Himmel: vier Farben von unten nach oben (globale Uniforms, auch vom Wasser genutzt),
// ein heller Glutstreifen am Horizont, ein warmer Schein in Richtung der Sonne und ein paar Sterne
// oben. Keine Textur. Unter dem Horizont die Horizontfarbe, abgedunkelt (das Meer deckt sie ab).

global uniform float lp_time;
global uniform vec4 sky_top;
global uniform vec4 sky_mid;
global uniform vec4 sky_low;
global uniform vec4 sky_glow;

uniform float star_density = 0.0035;
uniform float sun_glow = 0.55;

float hash(vec3 p) {
	p = fract(p * 0.3183099 + 0.1);
	p *= 17.0;
	return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

vec3 sky_color(vec3 d, vec3 sun) {
	float y = d.y;
	vec3 c;
	if (y < 0.0) {
		c = mix(sky_glow.rgb, sky_low.rgb * 0.7, smoothstep(0.0, 0.2, -y));
	} else {
		c = mix(sky_glow.rgb, sky_low.rgb, smoothstep(0.0, 0.07, y));
		c = mix(c, sky_mid.rgb, smoothstep(0.05, 0.22, y));
		c = mix(c, sky_top.rgb, smoothstep(0.16, 0.55, y));
	}
	// warmer Schein über dem Horizont in Richtung der Sonne
	vec3 sd = normalize(vec3(sun.x, 0.0, sun.z));
	float az = max(dot(normalize(vec3(d.x, 0.0, d.z)), sd), 0.0);
	float g = pow(az, 6.0) * (1.0 - smoothstep(0.0, 0.35, abs(y)));
	c = mix(c, sky_glow.rgb * 1.08, g * sun_glow);
	return c;
}

void sky() {
	vec3 c = sky_color(EYEDIR, LIGHT0_DIRECTION);
	if (!AT_CUBEMAP_PASS && EYEDIR.y > 0.12) {
		// Sterne: feste Zellen auf der Himmelskugel, nur im oberen Teil, funkeln leicht
		vec3 cell = floor(EYEDIR * 260.0);
		float h = hash(cell);
		if (h < star_density) {
			vec3 center = (cell + 0.5) / 260.0;
			float d = length(EYEDIR - normalize(center)) * 260.0;
			float tw = 0.75 + 0.25 * sin(lp_time * (2.0 + h * 900.0) + h * 4000.0);
			float s = (1.0 - smoothstep(0.12, 0.42, d)) * tw * smoothstep(0.12, 0.45, EYEDIR.y);
			c = mix(c, vec3(1.0, 0.96, 0.9), s);
		}
	}
	COLOR = c;
}
