// Synthwave-Himmel als Funktion der Blickrichtung (Welt): Verlauf, Sterne, Streifensonne, Wolkenbänder.
// Wird für den Himmel und (mit gespiegelter Richtung) für das Spiegelbild im Wasser benutzt.
// Keine Ableitungen (fwidth): die Funktion läuft in Verzweigungen; Kantenglättung über px_rad.

uniform vec2 sun_azel = vec2(-0.05, 0.03);   // Azimut (0 = Blick der Kamera, +x rechts), Höhe; Bogenmaß
uniform float sun_r = 0.13;                   // Radius der Sonne, Bogenmaß
uniform float px_rad = 0.00107;               // Winkel eines Bildpunkts in der Bildmitte

vec3 lin(vec3 c) {
	return pow(c, vec3(2.2));
}

vec3 horizon_col() {
	return lin(vec3(1.0, 0.33, 0.55));
}

vec3 sky_grad(float e) {
	// e = Höhe in Grad
	vec3 c0 = lin(vec3(1.0, 0.36, 0.52)) * 1.15;  // Horizont
	vec3 c1 = lin(vec3(0.74, 0.12, 0.47));        // 2°
	vec3 c2 = lin(vec3(0.33, 0.06, 0.40));        // 6°
	vec3 c3 = lin(vec3(0.13, 0.035, 0.26));       // 14°
	vec3 c4 = lin(vec3(0.035, 0.012, 0.10));      // 30°
	vec3 c = c0;
	c = mix(c, c1, smoothstep(0.0, 2.0, e));
	c = mix(c, c2, smoothstep(2.0, 6.0, e));
	c = mix(c, c3, smoothstep(6.0, 14.0, e));
	c = mix(c, c4, smoothstep(14.0, 32.0, e));
	return c;
}

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.xx + p3.yz) * p3.zy);
}

// Wolkenbank: waagerechte Streifenwolke um die Höhe e0 (Grad) mit halber Dicke h (Grad), Ausdehnung a0..a1 (Grad
// Azimut), Drift in Grad/s. Unterkante gerade (Synthwave-Streifen), Oberkante in flachen Buckeln.
float cloud_band(float azd, float eld, float e0, float h, float a0, float a1, float drift, float time, float seed,
		out float rim) {
	float a = azd - drift * time;
	float taper = smoothstep(a0, a0 + 9.0, a) * (1.0 - smoothstep(a1 - 9.0, a1, a));
	float lump = 0.5 + 0.3 * sin(a * 0.23 + seed) + 0.2 * sin(a * 0.61 + seed * 2.3);
	float top = e0 + h * taper * lump * 2.0;
	float bottom = e0 - h * taper * 0.35;
	float px = degrees(px_rad);
	float inside = smoothstep(bottom - px, bottom + px, eld) * (1.0 - smoothstep(top - px, top + px, eld));
	inside *= step(0.05, taper);
	rim = inside * (1.0 - smoothstep(0.0, 2.5 * px, eld - bottom));
	return inside;
}

vec3 sky(vec3 d, float time, bool refl) {
	float el = asin(clamp(d.y, -1.0, 1.0));
	float az = atan(d.x, -d.z);
	float eld = degrees(el);
	float azd = degrees(az);
	vec3 c = sky_grad(max(eld, 0.0));

	// Sterne (Zellen in Azimut/Höhe), funkeln mit fester Phase
	if (eld > 3.0) {
		vec2 cell = vec2(azd, eld) / 1.15;
		vec2 ci = floor(cell);
		float pick = hash12(ci + 17.0);
		if (pick < 0.16) {
			vec2 sp = ci + 0.15 + 0.7 * hash22(ci + 3.0);
			float dpx = length((cell - sp) * 1.15) / degrees(px_rad);
			float tw = 0.55 + 0.45 * sin(time * (1.3 + 2.5 * hash12(ci + 9.0)) + 6.283 * hash12(ci + 5.0));
			float b = (0.35 + 1.4 * hash12(ci + 1.0)) * tw * smoothstep(3.0, 9.0, eld);
			c += lin(vec3(0.75, 0.85, 1.0)) * b * exp(-dpx * dpx * 1.4);
		}
	}

	// Sonne mit Streifen: untere Hälfte in waagerechte Bänder geschnitten, die nach unten breiter werden
	vec2 sp = vec2((az - sun_azel.x) * cos(el), el - sun_azel.y) / sun_r;
	float r = length(sp);
	float pr = px_rad / sun_r;
	float disc = 1.0 - smoothstep(1.0 - pr, 1.0 + pr, r);
	float yy = sp.y;
	float k = clamp((0.5 - yy) / 1.5, 0.0, 1.0);
	float period = 0.13;
	float ph = fract((yy + time * 0.03) / period);
	float gap = 0.06 + k * 0.6;
	float ppx = pr / period;
	float stripe = k > 0.0 ? smoothstep(gap - ppx, gap + ppx, ph) : 1.0;
	float tt = clamp(yy * 0.5 + 0.5, 0.0, 1.0);
	vec3 sun_c = mix(lin(vec3(1.0, 0.16, 0.55)), lin(vec3(1.0, 0.45, 0.22)), smoothstep(0.0, 0.55, tt));
	sun_c = mix(sun_c, lin(vec3(1.0, 0.86, 0.32)), smoothstep(0.5, 1.0, tt));
	float sun_a = disc * stripe;
	c = mix(c, sun_c * 1.25, sun_a);
	// Schein um die Sonne
	c += lin(vec3(1.0, 0.25, 0.5)) * 0.32 * exp(-max(r - 1.0, 0.0) * 2.2) * (1.0 - disc);

	// Wolkenbänder vor der Sonne (dunkelviolett, Unterkante pink beleuchtet)
	float rim0;
	float rim1;
	float rim2;
	float c0 = cloud_band(azd, eld, 7.0, 0.95, -48.0, 2.0, 0.3, time, 1.0, rim0);
	float c1 = cloud_band(azd, eld, 3.0, 0.6, 10.0, 46.0, -0.22, time, 4.0, rim1);
	float c2 = cloud_band(azd, eld, 16.0, 1.1, 16.0, 62.0, 0.25, time, 7.0, rim2);
	float cl = max(c0, max(c1, c2));
	float rim = max(rim0, max(rim1, rim2));
	vec3 cloud_c = lin(vec3(0.16, 0.04, 0.26)) * mix(1.0, 0.55, smoothstep(2.0, 16.0, eld));
	c = mix(c, cloud_c, cl * 0.93);
	c += lin(vec3(1.0, 0.32, 0.66)) * rim * 0.75;
	return c;
}
