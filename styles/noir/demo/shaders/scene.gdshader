// Hintergrund der Noir-Demo: KI-Bild (schwarzweiß) plus alle Umgebungseffekte, die im Bild selbst liegen:
// flackernde Laterne samt Spiegelung, Jalousienlicht auf dem Pflaster, ziehender Nebel, Leuchtturmstrahl im Nebel,
// Flimmern der Spiegelungen auf Wasser und nassem Pflaster. Zeit t kommt aus dem Skript (aufsummiertes delta).
shader_type canvas_item;

#include "res://shaders/window.gdshaderinc"

uniform sampler2D fx_mask : filter_linear;                   // R Laterne, G Lichtfeld, B Wasser
uniform sampler2D aux_mask : filter_linear;                  // R Ferne (Nebel, Strahl), G Pflaster
uniform sampler2D noise_tex : filter_linear, repeat_enable;  // R/G Nebel, B fein
uniform float t = 0.0;
uniform float flicker = 1.0;                // Laterne, 1 = Grundhelligkeit
uniform vec2 lantern = vec2(771.7, 191.7);
uniform vec2 lamp = vec2(1135.0, 110.0);    // Leuchtfeuer
uniform float beam_phi = 0.0;               // Drehwinkel des Leuchtfeuers (0 = zur Kamera)
uniform float quay_y = 468.3;
uniform vec2 view_size = vec2(1280.0, 720.0);

varying vec2 world;

void vertex() {
	world = (MODEL_MATRIX * vec4(VERTEX, 0.0, 1.0)).xy;
}

float beam_light(vec2 p) {
	// Ein Strahl dreht sich um die senkrechte Achse: auf dem Bildschirm schwenkt er seitlich, seine sichtbare
	// Länge folgt |sin|, zur Kamera hin wird er heller (cos > 0).
	float sx = sin(beam_phi);
	float toward = cos(beam_phi);
	vec2 dir = normalize(vec2(sign(sx) + 1e-4, 0.035));
	vec2 v = p - lamp;
	float along = dot(v, dir);
	float perp = abs(dot(v, vec2(-dir.y, dir.x)));
	float len = 980.0 * abs(sx) + 40.0;
	float width = 3.0 + along * 0.075;
	float core = smoothstep(width, width * 0.25, perp);
	float body = smoothstep(0.0, 26.0, along) * (1.0 - smoothstep(len * 0.35, len, along));
	float strength = 0.38 * (0.45 + 0.55 * max(toward, 0.0)) * (1.0 - 0.6 * max(-toward, 0.0));
	return core * body * strength;
}

void fragment() {
	vec2 p = world;
	vec4 m = texture(fx_mask, UV);
	vec4 aux = texture(aux_mask, UV);
	float far = aux.r;

	// Flimmern: Spiegelungen auf dem Wasser und der Laternenschein auf dem nassen Pflaster werden waagerecht
	// versetzt (Wellen bzw. Regentropfen auf der Wasserhaut des Pflasters).
	float dx = 0.0;
	dx += m.b * (sin(p.y * 0.83 + t * 2.3) + 0.6 * sin(p.y * 1.71 - t * 3.4)) * 1.1;
	float refl = m.r * step(quay_y + 6.0, p.y);
	dx += refl * (sin(p.y * 0.37 + t * 5.3) * 1.4 + sin(p.y * 1.13 - t * 7.9) * 0.7);
	vec3 c = texture(TEXTURE, UV + vec2(dx, 0.0) / view_size).rgb;

	// Laterne: Glas, Schein und Spiegelung mit der Flackerhelligkeit; dazu ein Lichthof im Regen.
	c += m.r * (flicker - 1.0) * (c * 1.5 + vec3(0.06));
	float dl = length(p - lantern);
	c += vec3(0.20 * flicker * flicker) * exp(-dl * dl / (2.0 * 46.0 * 46.0)) * (1.0 - 0.35 * step(quay_y, p.y));
	c += vec3(0.06 * flicker) * exp(-dl * dl / (2.0 * 150.0 * 150.0));

	// Jalousienlicht auf dem Pflaster
	c += win_floor_light(p, c) * aux.g;

	// Nebel: zwei Lagen Rauschen, die langsam nach rechts ziehen, im Band um den Horizont; heller nahe den
	// Lichtern (Gegenlicht).
	vec2 q = p / view_size;
	float n1 = texture(noise_tex, q * vec2(1.6, 2.2) + vec2(t * 0.012, 0.0)).r;
	float n2 = texture(noise_tex, q * vec2(3.1, 4.6) + vec2(t * 0.027, 0.013)).g;
	float fogd = smoothstep(0.38, 0.85, 0.62 * n1 + 0.38 * n2);
	float band = smoothstep(170.0, 300.0, p.y) * (1.0 - smoothstep(420.0, 475.0, p.y));
	float fog = band * fogd * far * 0.28;
	c = mix(c, vec3(0.36 + 0.28 * m.g), fog);

	// Leuchtturmstrahl im Nebel und Aufblitzen der Lampe, wenn der Strahl zur Kamera zeigt.
	float beam = beam_light(p) * (0.55 + 0.9 * fogd) * far;
	float flash = pow(max(cos(beam_phi), 0.0), 10.0);
	float dlh = length(p - lamp);
	c += vec3(beam);
	c += vec3(0.85 * flash + 0.10) * exp(-dlh * dlh / (2.0 * (6.0 + 22.0 * flash) * (6.0 + 22.0 * flash)));

	COLOR = vec4(c, 1.0);
}
