// Für Regen, Schnee und Spritzer (GPUParticles2D): Dichte über die Teilchennummer (feste Reihenfolge,
// so wird Regen dichter, statt überall gleichzeitig einzublenden), Farbe vom Zustand, Laternenlicht nach Lage.
shader_type canvas_item;

uniform float density = 0.0;     // 0..1 Anteil sichtbarer Teilchen
uniform vec4 tint = vec4(0.7, 0.75, 0.85, 0.4);
uniform vec2 lantern_pos = vec2(379.4, 293.3);
uniform float lantern_i = 0.0;
uniform vec2 window_pos = vec2(162.0, 382.6);
uniform float window_i = 0.0;
uniform float flash = 0.0;
uniform vec2 screen_size = vec2(1280.0, 720.0);
uniform float sway_amp = 0.0;    // seitliches Pendeln (Schnee), in Teilchen-Pixeln
uniform float time = 0.0;

varying float vis;

void vertex() {
	float h = fract(float(INSTANCE_ID) * 0.6180339887 + 0.137) * 0.94;
	vis = smoothstep(h, h + 0.06, density);   // density 0 -> keins sichtbar, 1 -> alle
	// Pendeln aus Teilchennummer und Zeit-Uniform statt Turbulenz: Turbulenz lief nicht bei jedem Start gleich
	float h2 = fract(float(INSTANCE_ID) * 0.7548776662 + 0.31);
	VERTEX.x += sway_amp * sin(time * (0.9 + 1.4 * h2) + h2 * 37.0);
}

void fragment() {
	vec4 t = texture(TEXTURE, UV);
	vec2 sp = SCREEN_UV * screen_size;
	float lit = exp(-length(sp - lantern_pos) / 110.0) * lantern_i * 1.8
		+ exp(-length(sp - window_pos) / 90.0) * window_i * 0.9;
	vec3 c = tint.rgb + vec3(1.0, 0.72, 0.4) * lit + vec3(0.8, 0.85, 1.0) * flash * 0.6;
	COLOR = vec4(c, t.a * tint.a * vis * COLOR.a);
}
