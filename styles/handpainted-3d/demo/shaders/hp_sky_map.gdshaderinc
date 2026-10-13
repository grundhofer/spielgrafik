// Gemeinsame Abbildung des gemalten Himmels (sky.png, Unterkante = Horizont) auf Blickrichtungen.
// Zylindrisch: u nach Azimut (Mitte sky_az_center, Breite sky_az_span), v nach Höhenwinkel (0 = Horizont,
// 1 - sky_el_top = obere Bildkante). Unter dem Horizont: unterste Bildzeile.
// Benutzt von hp_sky.gdshader (Himmel) und hp_water.gdshader (Spiegelung).
uniform sampler2D sky_tex : source_color, filter_linear_mipmap, repeat_disable;
uniform float sky_az_center = 9.0;    // Grad, positiv = nach links (Azimut = atan(-x, -z))
uniform float sky_az_span = 100.0;    // Grad über die Bildbreite
uniform float sky_el_top = 46.0;      // Grad an der oberen Bildkante
uniform float sky_drift = 0.0;        // Grad, Wolkendrift (aus dem Skript)

vec2 sky_uv(vec3 d) {
	float az = degrees(atan(-d.x, -d.z));
	float el = degrees(asin(clamp(d.y, -1.0, 1.0)));
	float u = 0.5 - (az - sky_az_center - sky_drift) / sky_az_span;
	float v = 1.0 - el / sky_el_top;
	return vec2(u, clamp(v, 0.0, 0.997));
}

vec3 sky_color(vec3 d) {
	vec2 uv = sky_uv(d);
	// Ränder links/rechts gespiegelt fortsetzen (sollten nicht im Bild liegen)
	uv.x = 1.0 - abs(mod(uv.x, 2.0) - 1.0);
	return textureLod(sky_tex, uv, 0.0).rgb;
}
