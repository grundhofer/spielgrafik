// Alter Filmabzug über dem ganzen Bild: Zweistreifen-Farbe (rot-orange und blaugrün, kein Blau, kein Gelb),
// entsättigt und verblasst, Korn je Filmbild, Helligkeitsflimmern, Kratzer, Staub, Fussel, Vignette,
// Bildstandschwankung um ganze Pixel und eine Irisblende. Alle Zufallswerte kommen als Uniforms aus main.gd
// (RandomNumberGenerator mit festem Seed) oder aus einem Hash über die Bildnummer.
shader_type canvas_item;

uniform sampler2D screen_tex : hint_screen_texture, filter_nearest;
uniform float frame = 0.0;
uniform vec2 weave = vec2(0.0);       // ganze Pixel
uniform float flicker = 1.0;
uniform float strip_mix = 0.8;        // Anteil der Zweistreifen-Umrechnung
uniform float saturation = 0.8;
uniform float grain = 0.075;
uniform vec4 scratch0 = vec4(-100.0, 0.0, 1.0, 0.0);  // x (px), Deckkraft, Breite (px), hell(1)/dunkel(0)
uniform vec4 scratch1 = vec4(-100.0, 0.0, 1.0, 0.0);
uniform vec4 hair = vec4(-100.0, -100.0, 0.0, 0.0);   // Mitte x, y, Radius, Deckkraft
uniform float dust_seed = 0.0;
uniform float dust_amount = 0.10;     // Anteil der Zellen mit Staubkorn
uniform vec3 iris = vec3(640.0, 360.0, 2000.0);       // Mitte (px), Radius (px)
uniform vec2 screen_px = vec2(1280.0, 720.0);

// Hash without Sine – Copyright (c) 2014 David Hoskins, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt)
float hash(vec2 p) {
	// hash12 nach Dave Hoskins: kleine Faktoren zuerst, damit große Eingaben (Bildnummer) nicht an der
	// Gleitkommagenauigkeit scheitern (sonst senkrechte Streifen im Korn nach einigen Sekunden)
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

vec3 two_strip(vec3 c) {
	// Rotauszug ~ R, Grünauszug ~ G mit etwas B; Abzug: blaugrüner Farbstoff aus dem Rotauszug,
	// rot-oranger aus dem Grünauszug. Blau wird zu dunklem Blaugrün, Gelb zu Pfirsich, Violett zu Braun.
	float r = c.r;
	float g = 0.78 * c.g + 0.22 * c.b;
	return vec3(r, 0.95 * g + 0.05 * r, 0.80 * g + 0.07 * r);
}

void fragment() {
	vec2 px = SCREEN_UV * screen_px;
	vec3 c = texture(screen_tex, SCREEN_UV - weave / screen_px).rgb;  // Pixelmitte bleibt Pixelmitte
	c = mix(c, two_strip(c), strip_mix);
	float l = dot(c, vec3(0.299, 0.587, 0.114));
	c = mix(vec3(l), c, saturation);
	// verblasster Abzug: Schwarz angehoben, warmer Filmträger, weiche Lichter
	c = c * vec3(0.90, 0.89, 0.86) + vec3(0.050, 0.038, 0.025);
	c *= flicker;
	// Korn: Klumpen von 2 px, zwei Oktaven, in den Mitteltönen am stärksten
	vec2 gp = floor(px / 2.0);
	float n = hash(gp + vec2(frame * 17.13, frame * 31.7)) - 0.5;
	n += 0.5 * (hash(floor(px) + vec2(frame * 7.7, frame * 3.1)) - 0.5);
	c += n * grain * (0.55 + 0.9 * l * (1.0 - l));
	// Kratzer: senkrechte Linien, leicht gewellt
	for (int i = 0; i < 2; i++) {
		vec4 s = (i == 0) ? scratch0 : scratch1;
		float x = s.x + sin(px.y * 0.013 + s.x) * 1.6;
		float a = s.y * clamp(1.0 - abs(px.x - x) / s.z, 0.0, 1.0);
		a *= 0.75 + 0.25 * hash(vec2(floor(px.y / 7.0), s.x));
		c = mix(c, (s.w > 0.5) ? vec3(0.96, 0.93, 0.84) : c * 0.35, a);
	}
	// Staub: je Zelle von 64 px höchstens ein unregelmäßiges dunkles Korn
	vec2 cell = floor(px / 64.0);
	float h0 = hash(cell + dust_seed);
	if (h0 < dust_amount) {
		vec2 ctr = (cell + 0.2 + 0.6 * vec2(hash(cell + dust_seed + 3.1), hash(cell + dust_seed + 7.9))) * 64.0;
		float rad = 1.2 + 2.6 * hash(cell + dust_seed + 11.3);
		vec2 d = (px - ctr) * vec2(1.0, 0.6 + 0.8 * hash(cell + dust_seed + 5.5));
		float ang = atan(d.y, d.x);
		float wob = 1.0 + 0.22 * sin(ang * 2.0 + h0 * 40.0) + 0.16 * sin(ang * 5.0 + h0 * 91.0);
		float a = clamp(rad * wob - length(d) + 0.5, 0.0, 1.0);
		c = mix(c, vec3(0.08, 0.06, 0.05), a * 0.85);
	}
	// Fussel: dünner Bogen
	if (hair.w > 0.0) {
		vec2 d = px - hair.xy;
		float ang = atan(d.y, d.x);
		float ring = abs(length(d) - hair.z);
		float a = clamp(1.2 - ring, 0.0, 1.0) * step(0.4, sin(ang * 1.3 + hair.x)) * hair.w;
		c = mix(c, vec3(0.06, 0.05, 0.04), a);
	}
	// Vignette (oval, Ecken dunkler) und abgerundetes Bildfenster
	vec2 q = (SCREEN_UV - 0.5) * vec2(1.0, 0.85);
	float v = smoothstep(0.78, 0.30, length(q));
	c *= mix(0.55, 1.0, v);
	// Abgerundetes Rechteck (Außenabstand) nach Inigo Quilez – Copyright (c) Inigo Quilez, MIT-Lizenz (siehe THIRD_PARTY_NOTICES.txt), https://iquilezles.org/articles/distfunctions2d/
	vec2 e = abs(px - screen_px * 0.5) - (screen_px * 0.5 - vec2(26.0));
	float corner = length(max(e, 0.0)) - 26.0;
	c *= clamp(1.0 - corner / 3.0, 0.0, 1.0);
	// Irisblende
	float ir = iris.z - length(px - iris.xy);
	c *= clamp(ir + 0.5, 0.0, 1.0);
	COLOR = vec4(clamp(c, 0.0, 1.0), 1.0);
}
