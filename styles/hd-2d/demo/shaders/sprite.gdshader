// HD-2D: Pixel-Sprite als Billboard in der 3D-Szene.
// - Dreht sich nur um die Hochachse; im Kamerabild zur Bildebene (keine Verzerrung am Bildrand), im
//   Schattendurchgang zum Licht (die Figur wirft ihren vollen Umriss als Schatten).
//   Unterschieden wird über die Kameraposition: main.gd setzt view_cam_pos auf die Spielkamera.
// - Nearest, Alpha-Schnitt (schreibt Tiefe: Tiefenunschärfe und Umgebungsverdeckung greifen auch am Sprite).
// - Licht: weiches Umgreifen (Sprites haben keine echte Normale), Kantenlicht von Lichtern hinter der Figur
//   an den Umrisspixeln (Rim), keine Eigenschatten (shadows_disabled), sonst schattiert der eigene
//   Schatten-Billboard die Figur.
shader_type spatial;
render_mode cull_disabled, depth_draw_opaque, shadows_disabled, specular_disabled, diffuse_lambert;

global uniform vec3 view_cam_pos;

uniform sampler2D tex : source_color, filter_nearest, repeat_disable;
uniform vec2 tex_px = vec2(68.0, 64.0);      // Größe eines Einzelbildes in Pixeln
uniform float hframes = 1.0;
uniform float frame = 0.0;
uniform bool flip_h = false;
uniform vec4 modulate : source_color = vec4(1.0);
uniform float wrap = 0.55;                   // 0 = Lambert, 1 = von allen Seiten gleich hell
uniform float rim_strength = 1.6;
uniform float ambient_boost = 0.0;           // zusätzliches Grundlicht (Lesbarkeit der Figur)
uniform vec3 emission_color : source_color = vec3(0.0);
uniform float glint_energy = 0.0;
uniform bool silhouette = false;             // Messlauf: Farben der Textur ohne Licht (Messbilder)

varying float rim_edge;

void vertex() {
	vec3 origin = MODEL_MATRIX[3].xyz;
	vec3 fwd;
	if (distance(CAMERA_POSITION_WORLD, view_cam_pos) < 0.01) {
		fwd = INV_VIEW_MATRIX[2].xyz;                       // zur Bildebene der Spielkamera
	} else {
		fwd = CAMERA_POSITION_WORLD - origin;                // Schattendurchgang: zum Licht
		if (PROJECTION_MATRIX[3][3] != 0.0) {
			fwd = INV_VIEW_MATRIX[2].xyz;                    // Sonne (orthografischer Schatten)
		}
	}
	fwd.y = 0.0;
	fwd = normalize(fwd);
	vec3 right = normalize(cross(vec3(0.0, 1.0, 0.0), fwd));
	vec3 sx = right * length(MODEL_MATRIX[0].xyz);
	vec3 sy = vec3(0.0, 1.0, 0.0) * length(MODEL_MATRIX[1].xyz);
	vec3 sz = fwd * length(MODEL_MATRIX[2].xyz);
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(vec4(sx, 0.0), vec4(sy, 0.0), vec4(sz, 0.0), vec4(origin, 1.0));
	MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	vec2 uv = UV;
	if (flip_h) {
		uv.x = 1.0 - uv.x;
	}
	UV = vec2((floor(frame + 0.5) + uv.x) / hframes, uv.y);
}

void fragment() {
	vec4 c = texture(tex, UV);
	// Kantenpixel: ein Nachbartexel ist durchsichtig (für das Kantenlicht)
	vec2 ts = vec2(1.0 / (tex_px.x * hframes), 1.0 / tex_px.y);
	float e = 0.0;
	e += step(texture(tex, UV + vec2(ts.x, 0.0)).a, 0.5);
	e += step(texture(tex, UV - vec2(ts.x, 0.0)).a, 0.5);
	e += step(texture(tex, UV + vec2(0.0, ts.y)).a, 0.5);
	e += step(texture(tex, UV - vec2(0.0, ts.y)).a, 0.5);
	rim_edge = clamp(e, 0.0, 1.0);
	ALBEDO = c.rgb * modulate.rgb;
	ALPHA = c.a * modulate.a;
	ALPHA_SCISSOR_THRESHOLD = 0.5;
	// Glanzpunkt im Auge (reinweiße Pixel) leuchtet leicht selbst, sonst geht er in der Dämmerung unter
	float glint = step(0.9, min(c.r, min(c.g, c.b)));
	EMISSION = c.rgb * emission_color + c.rgb * ambient_boost + c.rgb * glint * glint_energy;
	if (silhouette) {
		ALBEDO = vec3(0.0);
		EMISSION = c.rgb;
	}
}

void light() {
	float ndl = dot(NORMAL, LIGHT);
	float d = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0);
	DIFFUSE_LIGHT += LIGHT_COLOR * ATTENUATION * d / PI;
	// Gegenlicht: Lichter hinter der Figur zeichnen den Umriss nach
	float back = clamp(-ndl, 0.0, 1.0);
	DIFFUSE_LIGHT += LIGHT_COLOR * ATTENUATION * rim_edge * back * rim_strength / PI;
}
