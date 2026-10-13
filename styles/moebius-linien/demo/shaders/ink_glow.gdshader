// Lichtschein wie im Comic: ein blasser Hof mit harter Kante und ein Kranz kurzer Tuschestriche,
// die vom Licht weg zeigen. Billboard (zeigt immer zur Kamera); burst (0..1) streckt die Striche und
// vergrößert den Hof (Laterne flackert, Leuchtfeuer blitzt). Strichbreite in Pixeln über fwidth.
// Das Rechteck liegt um offset_m zur Kamera hin versetzt, damit Laternengehäuse und Turm es nicht
// zerschneiden.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

global uniform vec4 ink_color;   // linear (globale Farben werden nicht aus sRGB umgerechnet)

uniform vec4 halo : source_color = vec4(1.0, 0.95, 0.68, 0.5);
uniform float burst = 0.5;
uniform float halo_r = 0.2;           // Hofradius in UV (Rechteck 0..1)
uniform int rays = 12;
uniform float ray_r0 = 0.26;
uniform float ray_r1 = 0.36;          // bei burst 0
uniform float ray_r1_max = 0.49;      // bei burst 1
uniform float ray_px = 1.5;
uniform float spin = 0.0;
uniform float offset_m = 0.4;
uniform float lines_on = 1.0;

void vertex() {
	float s = length(MODEL_MATRIX[0].xyz);
	vec3 cam_dir = normalize(INV_VIEW_MATRIX[3].xyz - MODEL_MATRIX[3].xyz);
	vec4 origin = vec4(MODEL_MATRIX[3].xyz + cam_dir * offset_m, 1.0);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0] * s, INV_VIEW_MATRIX[1] * s, INV_VIEW_MATRIX[2] * s, origin);
}

void fragment() {
	vec2 p = UV - 0.5;
	float r = length(p);
	float fw = max(fwidth(r), 1e-5);
	float hr = halo_r * (0.85 + 0.3 * burst);
	float in_halo = 1.0 - smoothstep(hr - fw, hr + fw, r);
	// Strahlen: abwechselnd lang und kurz
	float ang = atan(p.y, p.x) + spin;
	float sector = 6.28318 / float(rays);
	float k = floor(ang / sector + 0.5);
	float a_k = k * sector;
	float long_ray = mod(k, 2.0);
	float r1 = mix(ray_r1, ray_r1_max, burst) * mix(0.8, 1.0, long_ray);
	float r0 = ray_r0 * (0.95 + 0.1 * burst);
	vec2 dir = vec2(cos(a_k - spin), sin(a_k - spin));
	float t = clamp(dot(p, dir), r0, r1);
	float d = length(p - dir * t);
	float ray = 1.0 - smoothstep(ray_px * 0.5 * fw - fw * 0.5, ray_px * 0.5 * fw + fw * 0.5, d);
	ray *= step(0.05, burst + 0.05) * lines_on;
	vec3 col = mix(halo.rgb, ink_color.rgb, ray);
	ALBEDO = col;
	ALPHA = clamp(max(in_halo * halo.a, ray), 0.0, 1.0);
}
