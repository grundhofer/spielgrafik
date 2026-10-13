// Gemeinsame Teile für Zeichnung und Figur: Line-Boil und Papierzahn.
//
// Line-Boil: Die Zeichnung wird je Fassung (phase 0..2, wechselt alle 3 Takte) um ganze Pixel versetzt
// abgetastet. Der Versatz kommt aus einem weichen, kachelbaren Rauschen (boil.png: R/G = Versatz, B = Druck),
// das je Fassung an einer anderen Stelle gelesen wird. Ganze Pixel: kein Weichzeichnen durch lineare Filterung,
// dafür kleine Knicke an den Grenzen der Versatzfelder – wie ein neu nachgezogener Strich.
// Papierzahn: helle Striche brechen auf dem Korn auf, satte Striche bleiben geschlossen.

uniform sampler2D boil_tex : repeat_enable, filter_linear;
uniform sampler2D tooth_tex : repeat_enable, filter_linear;
uniform int phase = 0;
uniform bool boil_on = true;
uniform float boil_amp = 1.0;        // Standardabweichung des Versatzes in px
uniform float boil_scale = 0.6;      // Rauschtexel je Bildpixel (kleiner = großflächigere Verzerrung)
uniform float pressure_amp = 0.10;   // Schwankung der Strichdeckung je Fassung
uniform float tooth_k = 0.5;

vec2 boil_phase_offset() {
	return vec2(float(phase) * 97.0, float(phase) * 61.0);
}

// Versatz in ganzen Pixeln und Druckfaktor an der Stelle p (Bildpixel)
ivec2 boil_offset(vec2 p, out float pressure) {
	vec3 n = texture(boil_tex, (p * boil_scale + boil_phase_offset()) / 256.0).rgb;
	if (!boil_on) {
		pressure = 1.0;
		return ivec2(0);
	}
	pressure = 1.0 + pressure_amp * (n.b - 0.5) / 0.18;
	vec2 d = (n.rg - 0.5) / 0.18 * boil_amp;
	return ivec2(round(d));
}

// Grafit (1 - Helligkeit je Kanal) auf dem Papierzahn an der Bildschirmstelle wp
vec3 on_tooth(vec3 ink, vec2 wp) {
	float tooth = texture(tooth_tex, wp / 256.0).r;
	float dark = max(ink.r, max(ink.g, ink.b));
	float grain = mix(smoothstep(0.12, 0.78, tooth) * 1.3, 1.0, smoothstep(0.3, 0.75, dark));
	return ink * mix(1.0, grain, tooth_k);
}
