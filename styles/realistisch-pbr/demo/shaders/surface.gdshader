shader_type spatial;
// PBR-Oberfläche mit Kacheltexturen (CC0) für die gemeinsamen Modelle aus shared/3d.
//
// Die Smart-UV-Inseln der Modelle liegen beliebig gedreht; Mauern, Bretter und Dachschiefer
// brauchen aber eine feste Richtung. Deshalb projiziert der Shader je Material:
//   0 = Mesh-UV (1 UV-Einheit = 1 m), z. B. Figur
//   1 = dreiachsig in Weltkoordinaten (Gelände, Felsen, Poller)
//   2 = dreiachsig im Objektraum (bewegte Objekte: Boote, Taurolle)
//   3 = eben an der Flächennormale, Bildoberkante nach oben (Mauern, Dach, Kisten, Steg), Welt
//   4 = wie 3 im Objektraum
//   5 = zylindrisch um die lokale y-Achse (Fässer, Leuchtturm), Deckel eben
// Alle Abtastungen mit textureGrad und Ableitungen aus der stetigen Position, damit an Kanten
// und an der atan-Naht keine Mip-Nähte entstehen. Licht rechnet Godot (Standard-PBR).
render_mode cull_back, depth_draw_opaque;

uniform sampler2D tex_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform int mapping = 3;
uniform float tile_m = 2.0;                 // Meter je Kachel
uniform vec2 tile_aspect = vec2(1.0, 1.0);  // Seil: 2:1
uniform bool rot90 = false;                 // Textur um 90° drehen (Brettrichtung)
uniform bool detail_mode = false;           // Textur ist Graustufen-Detail (Mittel 0,5), Farbe aus tint
uniform vec3 tint : source_color = vec3(1.0);
uniform float albedo_gain = 1.0;
uniform float normal_strength = 1.0;
uniform float rough_mul = 1.0;
uniform float rough_add = 0.0;
uniform float metal_mul = 1.0;
uniform float ao_strength = 1.0;
uniform float cyl_radius = 0.3;             // Modus 5: Radius für die Abwicklung
uniform float tri_sharpness = 6.0;
uniform float specular_level = 0.5;
uniform float rim_amount = 0.0;             // Stoff: Glanz am Rand (Godot-RIM als Sheen-Näherung)
uniform float rim_tint_amount = 0.5;
// Nässe an der Wasserlinie (Welt-y): dunkler, glatter, unten grünlicher Bewuchs
uniform float wet_top = -100.0;
uniform float wet_band = 0.25;
uniform float algae_top = -100.0;
uniform vec3 algae_color : source_color = vec3(0.16, 0.19, 0.10);
// Nässe auf Oberseiten (feuchter Abend): dunkler und glatter, nur wo die Normale nach oben zeigt
uniform float damp_top = 0.0;
// Zweiter Texturensatz für Oberseiten (Kantensteine auf der Kaimauer)
uniform bool use_top = false;
uniform sampler2D top_a : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D top_n : hint_normal, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D top_orm : hint_default_white, filter_linear_mipmap_anisotropic, repeat_enable;
uniform float top_tile_m = 1.5;
uniform vec3 top_tint : source_color = vec3(1.0);
// Großflächige Helligkeitsschwankung gegen sichtbare Kachelwiederholung (Gelände)
uniform float macro_amount = 0.0;
uniform float macro_scale_m = 23.0;

varying vec3 v_wpos;
varying vec3 v_wnrm;
varying vec3 v_opos;
varying vec3 v_onrm;

struct Smp { vec3 a; vec3 n; vec3 orm; };

void vertex() {
	v_wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_wnrm = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	v_opos = VERTEX;
	v_onrm = NORMAL;
}

vec3 unpack_n(vec4 t) {
	vec2 xy = t.xy * 2.0 - 1.0;
	return vec3(xy * normal_strength, sqrt(max(1.0 - dot(xy, xy), 0.0)));
}

Smp smp(vec2 uv, vec2 gx, vec2 gy, bool top) {
	Smp s;
	if (top) {
		s.a = textureGrad(top_a, uv, gx, gy).rgb;
		s.n = unpack_n(textureGrad(top_n, uv, gx, gy));
		s.orm = textureGrad(top_orm, uv, gx, gy).rgb;
	} else {
		s.a = textureGrad(tex_a, uv, gx, gy).rgb;
		s.n = unpack_n(textureGrad(tex_n, uv, gx, gy));
		s.orm = textureGrad(tex_orm, uv, gx, gy).rgb;
	}
	return s;
}

// Ebene Projektion mit Rahmen T (Bild rechts), B (Bild oben); gibt Farbe, Weltnormale (über
// die Störung n.x*T + n.y*B), ORM zurück.
void planar(vec3 p, vec3 dpx, vec3 dpy, vec3 T, vec3 B, float tile, bool top,
		out vec3 a, out vec3 pert, out vec3 orm) {
	if (rot90) { vec3 t0 = T; T = B; B = -t0; }
	vec2 sc = 1.0 / (tile * tile_aspect);
	vec2 uv = vec2(dot(p, T), -dot(p, B)) * sc;
	vec2 gx = vec2(dot(dpx, T), -dot(dpx, B)) * sc;
	vec2 gy = vec2(dot(dpy, T), -dot(dpy, B)) * sc;
	Smp s = smp(uv, gx, gy, top);
	a = s.a;
	pert = T * s.n.x + B * s.n.y;
	orm = s.orm;
}

void frame_for(vec3 n, out vec3 T, out vec3 B) {
	vec3 up = abs(n.y) < 0.75 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, -sign(n.y));
	T = normalize(cross(up, n));
	B = cross(n, T);
}

void fragment() {
	bool obj = (mapping == 2 || mapping == 4 || mapping == 5);
	vec3 p = obj ? v_opos : v_wpos;
	vec3 ng = normalize(obj ? v_onrm : v_wnrm);
	vec3 dpx = dFdx(p);
	vec3 dpy = dFdy(p);
	vec3 wn_geo = normalize(v_wnrm);
	bool top = use_top && wn_geo.y > 0.6;
	float tile = top ? top_tile_m : tile_m;

	vec3 a = vec3(0.5);
	vec3 pert = vec3(0.0);
	vec3 orm = vec3(1.0, 0.8, 0.0);

	if (mapping == 0) {
		vec2 sc = 1.0 / (tile * tile_aspect);
		vec2 uv = UV * sc;
		Smp s = smp(uv, dFdx(UV) * sc, dFdy(UV) * sc, top);
		a = s.a; orm = s.orm;
		// Tangentenraum der Mesh-UVs (Godot liefert TANGENT/BINORMAL in Sichtkoordinaten)
		vec3 Tw = (INV_VIEW_MATRIX * vec4(TANGENT, 0.0)).xyz;
		vec3 Bw = (INV_VIEW_MATRIX * vec4(BINORMAL, 0.0)).xyz;
		pert = Tw * s.n.x + Bw * s.n.y;
		ng = wn_geo;
	} else if (mapping == 1 || mapping == 2) {
		vec3 w = pow(abs(ng), vec3(tri_sharpness));
		w /= (w.x + w.y + w.z);
		vec3 ax, px_, ox; vec3 ay, py_, oy; vec3 az, pz_, oz;
		planar(p, dpx, dpy, vec3(0.0, 0.0, -sign(ng.x)), vec3(0.0, 1.0, 0.0), tile, top, ax, px_, ox);
		planar(p, dpx, dpy, vec3(1.0, 0.0, 0.0), vec3(0.0, 0.0, -sign(ng.y)), tile, top, ay, py_, oy);
		planar(p, dpx, dpy, vec3(sign(ng.z), 0.0, 0.0), vec3(0.0, 1.0, 0.0), tile, top, az, pz_, oz);
		a = ax * w.x + ay * w.y + az * w.z;
		pert = px_ * w.x + py_ * w.y + pz_ * w.z;
		orm = ox * w.x + oy * w.y + oz * w.z;
	} else if (mapping == 3 || mapping == 4) {
		vec3 T, B;
		frame_for(ng, T, B);
		planar(p, dpx, dpy, T, B, tile, top, a, pert, orm);
	} else {
		// zylindrisch um die lokale y-Achse; Deckel (Normale nach oben/unten) eben
		if (abs(ng.y) > 0.7) {
			planar(p, dpx, dpy, vec3(1.0, 0.0, 0.0), vec3(0.0, 0.0, -sign(ng.y)), tile, top, a, pert, orm);
		} else {
			float r = max(length(p.xz), 1e-4);
			float ang = atan(p.x, p.z);
			vec3 T = vec3(cos(ang), 0.0, -sin(ang));
			vec3 B = vec3(0.0, 1.0, 0.0);
			vec2 sc = 1.0 / (tile * tile_aspect);
			// Bogenlänge auf dem festen Radius cyl_radius: senkrechte Fugen bleiben senkrecht
			// (Drehung rot90 gibt es hier nicht; Dauben und Putz laufen senkrecht)
			float k = cyl_radius / r;
			vec2 uv = vec2(ang * cyl_radius, -p.y) * sc;
			vec2 gx = vec2(dot(dpx, T) * k, -dpx.y) * sc;
			vec2 gy = vec2(dot(dpy, T) * k, -dpy.y) * sc;
			Smp s = smp(uv, gx, gy, top);
			a = s.a; orm = s.orm;
			pert = T * s.n.x + B * s.n.y;
		}
	}

	// Störung in Welt- bzw. Objektraum -> Weltnormale
	vec3 nrm;
	if (mapping == 0) {
		nrm = normalize(wn_geo + pert);
	} else if (obj) {
		vec3 pw = (MODEL_MATRIX * vec4(pert, 0.0)).xyz;
		nrm = normalize(wn_geo + pw);
	} else {
		nrm = normalize(wn_geo + pert);
	}

	vec3 base = top ? a * top_tint : (detail_mode ? a * 2.0 * tint : a * tint);
	base *= albedo_gain;
	if (macro_amount > 0.0) {
		vec2 m = v_wpos.xz / macro_scale_m;
		float mac = sin(m.x * 1.7 + sin(m.y * 1.3)) * cos(m.y * 1.1 - 0.7 * sin(m.x * 0.9));
		base *= 1.0 + macro_amount * mac;
	}
	float rough = clamp(orm.g * rough_mul + rough_add, 0.02, 1.0);
	float metal = clamp(orm.b * metal_mul, 0.0, 1.0);
	float ao = mix(1.0, orm.r, ao_strength);

	// Nässe an der Wasserlinie
	float wet = 1.0 - smoothstep(wet_top - wet_band, wet_top, v_wpos.y);
	float algae = 1.0 - smoothstep(algae_top - 0.3, algae_top, v_wpos.y);
	float lum = dot(base, vec3(0.3, 0.55, 0.15));
	base = mix(base, algae_color * (0.6 + 1.2 * lum), algae * 0.75);
	base *= mix(1.0, 0.5, wet);
	rough = mix(rough, 0.18, wet);
	// feuchte Oberseiten
	float up = smoothstep(0.55, 0.9, nrm.y) * damp_top;
	base *= mix(1.0, 0.72, up);
	rough = mix(rough, rough * 0.45, up);

	ALBEDO = clamp(base, 0.0, 1.0);
	ROUGHNESS = rough;
	METALLIC = metal;
	SPECULAR = specular_level;
	AO = ao;
	AO_LIGHT_AFFECT = 0.25;
	if (rim_amount > 0.0) {
		RIM = rim_amount;
		RIM_TINT = rim_tint_amount;
	}
	NORMAL = normalize((VIEW_MATRIX * vec4(nrm, 0.0)).xyz);
}
