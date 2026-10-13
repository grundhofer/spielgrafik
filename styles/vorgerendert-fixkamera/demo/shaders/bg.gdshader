// Vorgerenderter Hintergrund hinter der festen Kamera.
// Ein Vollbild-Viereck (hängt an der Kamera) zeigt das Renderbild Pixel für Pixel (320×240, texelFetch)
// und schreibt in den Tiefenpuffer die Tiefe aus Blender: So verdecken Häuschen, Fässer und Kaikante
// die echte 3D-Figur, ohne dass ihre Geometrie im Spiel existiert.
// Dazu: Bildfolge-Overlay (nur das bewegte Rechteck, Raster aller Bilder der Schleife) und die
// Lichtebene der Laterne, die mit lantern_k flackert (linear addiert).
shader_type spatial;
render_mode unshaded, cull_disabled, depth_draw_always, shadows_disabled, ambient_light_disabled, fog_disabled;

uniform sampler2D base_tex : filter_nearest;
uniform sampler2D depth_tex : filter_nearest;
uniform sampler2D lantern_tex : filter_nearest;
uniform sampler2D anim_tex : filter_nearest;
uniform ivec4 anim_rect = ivec4(0, 0, 0, 0);   // x, y, Breite, Höhe in Pixeln
uniform int anim_cols = 1;
uniform int anim_frame = 0;
uniform float lantern_k = 1.0;                  // 1 = wie gerendert
uniform float depth_range = 1000.0;
uniform bool use_depth = true;                  // Vergleichsschalter --no-depth
uniform bool use_anim = true;                   // Vergleichsschalter --no-anim
uniform bool key_mode = false;                  // Messlauf: Hintergrund magenta, Tiefe bleibt

vec3 srgb_to_lin(vec3 c) {
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	// Kompatibilitäts-Renderer (OpenGL): ohne Umrechnung, sonst wird das Bild zu dunkel (gemessen:
	// so weicht er im Mittel 3,3 Stufen von Forward+ ab; die Lichtebene addiert hier in sRGB statt linear)
	return c;
#else
	return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
#endif
}

void vertex() {
	// Viereck 2×2 (QuadMesh) direkt als Bildschirmfläche; die Tiefe kommt im fragment() aus dem Bild.
	POSITION = vec4(VERTEX.xy, 0.5, 1.0);
}

void fragment() {
	ivec2 sz = textureSize(base_tex, 0);
	ivec2 px = clamp(ivec2(SCREEN_UV * vec2(sz)), ivec2(0), sz - 1);
	vec3 c = texelFetch(base_tex, px, 0).rgb;
	if (use_anim) {
		ivec2 q = px - anim_rect.xy;
		if (q.x >= 0 && q.y >= 0 && q.x < anim_rect.z && q.y < anim_rect.w) {
			ivec2 cell = ivec2(anim_frame % anim_cols, anim_frame / anim_cols);
			vec4 a = texelFetch(anim_tex, cell * anim_rect.zw + q, 0);
			c = mix(c, a.rgb, a.a);
		}
	}
	vec3 l = srgb_to_lin(c) + (lantern_k - 1.0) * srgb_to_lin(texelFetch(lantern_tex, px, 0).rgb);
	ALBEDO = key_mode ? vec3(1.0, 0.0, 1.0) : max(l, vec3(0.0));

	vec3 e = round(texelFetch(depth_tex, px, 0).rgb * 255.0);
	float d = (e.r * 65536.0 + e.g * 256.0 + e.b) / 16777215.0 * depth_range;
	if (!use_depth) {
		d = depth_range;
	}
	// Punkt auf dem Sehstrahl dieses Pixels, auf Tiefe d (entlang der Blickachse) skaliert
	vec4 r = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, 0.5, 1.0);
	vec3 p = r.xyz / r.w;
	p *= d / -p.z;
	vec4 clip = PROJECTION_MATRIX * vec4(p, 1.0);
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	DEPTH = clip.z / clip.w * 0.5 + 0.5;    // OpenGL: NDC-Tiefe -1..1
#else
	DEPTH = clip.z / clip.w;                // Vulkan/Metal: 0..1 (umgekehrtes Z)
#endif
}
