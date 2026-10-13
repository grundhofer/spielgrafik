shader_type canvas_item;
// Gezeichneter Hintergrund + Wasserglitzer als kurze, hart begrenzte Lichtstriche (Zeichentrick-Effekt).
// mask_tex.r = Wasser (aus prep_bg.py). Zeit kommt als Uniform aus main.gd (aufsummiertes delta).

uniform sampler2D mask_tex : filter_linear;
uniform float t = 0.0;
uniform vec2 size = vec2(1280.0, 720.0);
uniform vec3 glint_color = vec3(0.86, 0.96, 1.0);

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

void fragment() {
	vec4 c = texture(TEXTURE, UV);
	float m = texture(mask_tex, UV).r;
	vec2 px = UV * size;
	// Zeilen von 4 px; weiter unten (näher) längere Striche
	float row = floor(px.y / 4.0);
	float depth = clamp((px.y - 345.0) / 190.0, 0.0, 1.0);
	float len = mix(9.0, 30.0, depth);
	float hr = hash(vec2(row, 3.0));
	float drift = (hr - 0.5) * 6.0;
	float x = (px.x + t * drift) / len + hr * 17.0;
	float cell = floor(x);
	float f = fract(x);
	float hc = hash(vec2(row, cell));
	// jeder Strich blinkt mit eigener Phase: an für etwa ein Drittel der Zeit
	float phase = fract(t * (0.35 + 0.4 * hc) + hc * 7.0);
	float on = step(0.86, hc) * step(phase, 0.32);
	float inrow = step(1.0, mod(px.y, 4.0)) * step(mod(px.y, 4.0), 2.6);
	float streak = on * step(0.15, f) * step(f, 0.85) * inrow;
	c.rgb = mix(c.rgb, glint_color, streak * smoothstep(0.4, 0.9, m) * 0.85);
	COLOR = c;
}
