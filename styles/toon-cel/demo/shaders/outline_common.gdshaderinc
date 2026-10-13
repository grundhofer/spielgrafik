// Gemeinsamer Teil der Kontur-Nachbearbeitung (outline_post.gdshader für Forward+,
// outline_post_depth.gdshader für Mobile/Compatibility): Tiefe lesen, Silhouetten finden, Linienfarbe.
// 1/z ist auf einer Ebene im Bildraum linear; weicht der Nachbar stark von der Vorhersage aus Mitte und
// Gegenseite ab und liegt er weiter hinten, liegt die Mitte auf der Vorderkante. So entstehen auf flach
// gesehenen Böden keine Fehllinien.

uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform sampler2D screen_tex : hint_screen_texture, filter_nearest, repeat_disable;

uniform vec4 ink : source_color = vec4(0.11, 0.07, 0.16, 1.0);
uniform float tint = 0.45;              // 0 = reine Tinte, 1 = abgedunkelte Untergrundfarbe
uniform float darken = 0.3;
uniform float depth_threshold = 0.035;  // relativer Fehler der 1/z-Vorhersage
uniform float width_near = 2.0;         // Abtastabstand in Pixeln (≈ Linienbreite) nah ...
uniform float width_far = 1.0;          // ... und fern
uniform float width_dist = 30.0;        // m, ab hier width_far
uniform float fade_begin = 120.0;       // m
uniform float fade_end = 600.0;
uniform float water_level = -0.86;
uniform float enabled = 1.0;

float depth_at(vec2 uv) {
	return texture(depth_tex, uv).r;
}

vec3 view_pos(vec2 uv, float d, mat4 inv_proj) {
	vec4 v = inv_proj * vec4(uv * 2.0 - 1.0, d, 1.0);
	return v.xyz / v.w;
}

// Tiefensprung in Richtung off: Mitte vorn, Nachbar (uv + off) hinten, Vorhersage aus (uv - off).
float depth_edge(vec2 uv, vec2 off, float izc, mat4 inv_proj) {
	float zn = -view_pos(uv + off, depth_at(uv + off), inv_proj).z;
	float zo = -view_pos(uv - off, depth_at(uv - off), inv_proj).z;
	float izn = 1.0 / zn;
	float izo = 1.0 / zo;
	float err = abs(izn - (2.0 * izc - izo)) / izc;
	float behind = step(1.0 / izc * 1.002, zn);
	return step(depth_threshold, err) * behind;
}

// Silhouetten in vier Richtungen; gibt außerdem Abstand, Weltlage und Abtastversatz zurück.
float silhouette(vec2 uv, vec2 viewport, mat4 inv_proj, mat4 inv_view, out float zc, out vec3 wc,
		out vec2 ox, out vec2 oy, out float sky) {
	vec2 px = 1.0 / viewport;
	float dc = depth_at(uv);
	vec3 vc = view_pos(uv, dc, inv_proj);
	zc = -vc.z;
	sky = step(dc, 0.0000001);
	wc = (inv_view * vec4(vc, 1.0)).xyz;
	float w = mix(width_near, width_far, smoothstep(4.0, width_dist, zc));
	ox = vec2(px.x * w, 0.0);
	oy = vec2(0.0, px.y * w);
	float izc = 1.0 / zc;
	float e = 0.0;
	e = max(e, depth_edge(uv, ox, izc, inv_proj));
	e = max(e, depth_edge(uv, -ox, izc, inv_proj));
	e = max(e, depth_edge(uv, oy, izc, inv_proj));
	e = max(e, depth_edge(uv, -oy, izc, inv_proj));
	return e;
}

// Linie ausblenden: Himmel, unter der Wasserlinie (Wasser ist durchsichtig gerendert und liegt nicht
// im Tiefenpuffer), in großer Entfernung.
float finish(float e, float zc, vec3 wc, float sky) {
	e *= 1.0 - sky;
	e *= step(water_level, wc.y);
	e *= 1.0 - smoothstep(fade_begin, fade_end, zc);
	return e * enabled;
}

vec3 line_color(vec2 uv) {
	vec3 under = texture(screen_tex, uv).rgb;
	return mix(ink.rgb, under * darken, tint);
}
