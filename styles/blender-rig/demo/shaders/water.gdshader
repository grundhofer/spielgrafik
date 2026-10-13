// Stilneutrales Wasser für das Mesh "Sea" (Ersatz für das glTF-Material "Water").
// Grundfarbe und Rauheit kommen aus dem importierten Material (main.gd setzt sie).
// Wellen in Weltkoordinaten: langsame Dünung als Verschiebung, kleine Kräuselung nur in der Normale.
// Zeit kommt als Uniform aus dem Skript (aufsummiertes delta), nicht TIME: so bleibt die Aufnahme reproduzierbar.
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_burley, specular_schlick_ggx;

uniform vec4 albedo : source_color = vec4(0.169, 0.353, 0.420, 1.0);
uniform float roughness : hint_range(0.0, 1.0) = 0.15;
uniform float time_s = 0.0;
uniform float swell_height = 0.05;      // m; Kai liegt 0,8 m über dem Wasser, Bootsursprung auf der Wasserlinie
uniform float ripple_strength = 0.10;   // Neigung der Kräuselung
uniform vec2 harbor_center = vec2(0.0, -12.0);
uniform float swell_radius = 40.0;      // außerhalb: keine Verschiebung (dort ist das Gitter grob)
uniform float ripple_fade = 90.0;       // m Kamera-Abstand: Kräuselung blendet aus (sonst Flimmern)

varying vec3 world_pos;

// Gerichtete Sinuswelle: x = Höhe, yz = Ableitung nach Welt-x und Welt-z
vec3 wave(vec2 p, vec2 dir, float len, float amp, float speed) {
	float k = 6.2831853 / len;
	float ph = k * (dot(normalize(dir), p) - speed * time_s);
	return vec3(amp * sin(ph), amp * k * cos(ph) * normalize(dir));
}

vec3 swell(vec2 p) {
	return wave(p, vec2(0.3, 1.0), 11.0, 1.0, 1.3)
		+ wave(p, vec2(-0.6, 1.0), 17.0, 0.7, 1.7)
		+ wave(p, vec2(1.0, 0.4), 7.0, 0.35, 1.0);
}

vec2 ripples(vec2 p) {
	vec3 r = wave(p, vec2(0.2, 1.0), 2.3, 0.06, 0.9)
		+ wave(p, vec2(-0.8, 0.5), 1.7, 0.05, 0.8)
		+ wave(p, vec2(0.9, -0.3), 1.1, 0.03, 0.6)
		+ wave(p, vec2(-0.4, -1.0), 3.1, 0.07, 1.1);
	return r.yz;
}

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec3 s = swell(world_pos.xz) * swell_height * fade;
	VERTEX.y += s.x;
	world_pos.y += s.x;
	NORMAL = normalize(vec3(-s.y, 1.0, -s.z));
}

void fragment() {
	float d = length(world_pos - CAMERA_POSITION_WORLD);
	float fade = 1.0 - smoothstep(swell_radius * 0.6, swell_radius, length(world_pos.xz - harbor_center));
	vec2 g = swell(world_pos.xz).yz * swell_height * fade;
	g += ripples(world_pos.xz) * ripple_strength * (1.0 - smoothstep(ripple_fade * 0.4, ripple_fade, d));
	vec3 n_world = normalize(vec3(-g.x, 1.0, -g.y));
	NORMAL = normalize((VIEW_MATRIX * vec4(n_world, 0.0)).xyz);
	ALBEDO = albedo.rgb;
	ROUGHNESS = roughness;
	METALLIC = 0.0;
	SPECULAR = 0.5;
}
