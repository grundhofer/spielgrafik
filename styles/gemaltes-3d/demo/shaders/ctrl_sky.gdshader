// Himmel der Steuerkamera: Steuerwerte statt Farbe (siehe paint_common.gdshaderinc).
// R = 1 (größte Pinsel; nur der Himmel hat genau 1, die Nachbearbeitung erkennt ihn daran),
// G = Strichrauschen in Zellen fester Winkelgröße (am Himmel festgemacht, wandert beim Schwenken mit),
// B = Wolkendeckung (am Himmel statt der Kantenstärke; die setzt post_paint.gdshader für den Himmel
//     fest), damit die Sterne nur zwischen den Wolken erscheinen.
shader_type sky;

#include "res://shaders/paint_common.gdshaderinc"
#include "res://shaders/sky_common.gdshaderinc"

uniform float cell_rad = 0.0026;   // etwa 2,5 px bei fov 44 und 720 px Bildhöhe

void sky() {
	vec3 d = normalize(EYEDIR);
	float n = mix(vnoise3(d / cell_rad), vnoise3(d / (cell_rad * 3.5) + vec3(17.5)), 0.4);
	n = clamp(0.5 + (n - 0.5) * 1.6, 0.0, 1.0);
	COLOR = vec3(1.0, n, sky_clouds(d).a);
}
