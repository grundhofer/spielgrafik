// Gemeinsame Bausteine des PS1-Looks. Alle Werte kommen als globale Uniforms aus main.gd
// (project.godot -> [shader_globals]); Farben sind dort bereits linear.
//
// Was die Konsole tat und wie es hier nachgebaut ist:
//  - Geometrie-Prozessor rechnet Eckpunkte auf ganze Bildschirmpixel  -> ps1_snap(): Clip-Position auf
//    das 320×240-Raster runden (kein Subpixel). Bewegt sich etwas, springen die Ecken einzeln: "Wackeln".
//  - Licht nur je Eckpunkt (Umgebung + Sonne + bis zu 3 Punktlichter), dazwischen Gouraud. Statische
//    Geometrie trägt zusätzlich vorberechnete Vertexfarben (Umgebungsverdeckung aus Blender)  -> ps1_light()
//  - Nebel als "depth cueing" je Eckpunkt über die Vertexfarben: Die Farbe, mit der die Textur moduliert
//    wird, verliert mit der Entfernung an Gewicht, die Ferne-Farbe kommt als zweite Vertexfarbe hinzu
//    (ps1_fog() im vertex() der Shader). Im Fragment bleibt nur Textur × Farbe + Farbe.
//  - Texturen ohne Perspektivkorrektur (affin)  -> UV*w und w als Varyings; im Fragment teilen.
//    Die perspektivische Interpolation beider Werte hebt sich dann auf, übrig bleibt die lineare
//    Interpolation im Bildraum wie beim Rasterizer der Konsole. Dasselbe gilt für die Gouraud-Farben:
//    Die Konsole interpoliert auch sie linear im Bildraum, Godot perspektivisch korrekt; deshalb werden
//    die Vertexfarben ebenfalls mit w multipliziert übergeben und im Fragment geteilt (ps1_affine_vc).
//  - Kein Z-Puffer: Die Konsole sortierte Polygone nach ihrer mittleren Tiefe in eine "Ordering Table"
//    und malte von hinten nach vorn. Nachbau: Jedes Dreieck schreibt statt der Tiefe je Pixel eine feste
//    Tiefe für das ganze Dreieck (Mittelpunkt, aus CUSTOM0, siehe main.gd -> _ot_mesh()). Der Tiefentest
//    vergleicht dann ganze Polygone wie der Maleralgorithmus: Das Polygon mit dem näheren Mittelpunkt
//    gewinnt überall, auch wo es eigentlich dahinter liegt -> ps1_ot_depth(). Boden und Meer liegen wie
//    in Spielen der Zeit in einer hinteren Ebene (ot_bias in Metern).
//  - Texturen ohne Mipmaps (Nearest): In der Ferne fallen mehrere Texel auf ein Pixel, bei Bewegung
//    flimmert es. ps1_mip = 1 schaltet zum Vergleich Mipmaps ein.

global uniform vec2 ps1_snap_res;
global uniform vec4 ps1_ambient;
global uniform vec3 ps1_sun_dir;        // Richtung, in die das Licht läuft (Welt)
global uniform vec4 ps1_sun_color;
global uniform vec4 ps1_light0_pos;     // xyz Welt, w Reichweite
global uniform vec4 ps1_light0_color;   // rgb * Stärke
global uniform vec4 ps1_light1_pos;
global uniform vec4 ps1_light1_color;
global uniform vec4 ps1_light2_pos;
global uniform vec4 ps1_light2_color;
global uniform vec4 ps1_fog_color;
global uniform vec2 ps1_fog_range;      // Beginn, Ende in m (Kameraabstand)
global uniform float ps1_time;
global uniform float ps1_affine;        // 1 = affin wie die Konsole, 0 = perspektivisch korrekt (Vergleich)
global uniform float ps1_affine_vc;     // Vertexfarben: 1 = linear im Bildraum wie die Konsole, 0 = perspektivisch
global uniform float ps1_ot;            // 1 = nach Polygonen sortiert (kein Z-Puffer), 0 = Z-Puffer (Vergleich)
global uniform float ps1_mip;           // 0 = ohne Mipmaps wie die Konsole, 1 = mit Mipmaps (Vergleich)
global uniform float ps1_vc_strength;   // Gewicht der vorberechneten Vertexfarben (Umgebungsverdeckung)

vec4 ps1_snap(vec4 clip) {
	if (clip.w > 0.0001) {
		vec2 half_res = ps1_snap_res * 0.5;
		vec2 ndc = clip.xy / clip.w;
		ndc = floor(ndc * half_res + 0.5) / half_res;
		clip.xy = ndc * clip.w;
	}
	return clip;
}

vec3 ps1_point(vec4 lp, vec4 lc, vec3 wpos, vec3 wn) {
	vec3 l = lp.xyz - wpos;
	float d = length(l);
	float att = clamp(1.0 - d / lp.w, 0.0, 1.0);
	// leicht "umhüllend" (0.25), damit Flächen quer zum Licht nicht ganz schwarz bleiben
	float nl = clamp((dot(wn, l / max(d, 0.001)) + 0.25) / 1.25, 0.0, 1.0);
	return lc.rgb * att * att * nl;
}

// Gouraud-Farbe eines Eckpunkts. vc = vorberechnete Vertexfarbe (Umgebungsverdeckung, 1 = frei);
// sie dämpft Grundlicht und Sonne, nicht die Punktlichter (Laterne, Fenster, Leuchtfeuer).
vec3 ps1_light(vec3 wpos, vec3 wn, float vc) {
	float occ = mix(1.0, vc, ps1_vc_strength);
	vec3 c = ps1_ambient.rgb * occ;
	c += ps1_sun_color.rgb * max(dot(wn, -normalize(ps1_sun_dir)), 0.0) * mix(1.0, occ, 0.6);
	c += ps1_point(ps1_light0_pos, ps1_light0_color, wpos, wn);
	c += ps1_point(ps1_light1_pos, ps1_light1_color, wpos, wn);
	c += ps1_point(ps1_light2_pos, ps1_light2_color, wpos, wn);
	return min(c, vec3(2.0));   // Vertexfarbe sättigt wie auf der Konsole bei 2×
}

float ps1_fog(float depth) {
	float f = clamp((depth - ps1_fog_range.x) / (ps1_fog_range.y - ps1_fog_range.x), 0.0, 1.0);
	return f * (2.0 - f);       // schneller Anstieg, weiches Ende
}

// Feste Tiefe für ein ganzes Polygon (Abstand zur Kamera in m) als Wert für DEPTH.
float ps1_ot_depth(float dist, mat4 proj) {
	vec4 c = proj * vec4(0.0, 0.0, -max(dist, 0.05), 1.0);
	float d = c.z / c.w;
#if CURRENT_RENDERER == RENDERER_COMPATIBILITY
	d = d * 0.5 + 0.5;
#endif
	return d;
}
