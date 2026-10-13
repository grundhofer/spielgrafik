// Leuchtfeuer: der Strahl dreht sich um die senkrechte Achse (eine Umdrehung je Periode). Zur Seite zeigend
// ist er ein langer Lichtkeil nach links, zur Kamera ein Aufblitzen, nach hinten vom Turm verdeckt.
shader_type canvas_item;
render_mode blend_add;

uniform float t = 0.0;
uniform vec2 rect_size = vec2(1280.0, 260.0);
uniform vec2 lamp = vec2(1137.0, 118.0);
uniform float period = 7.0;
uniform float phase0 = 0.0;
uniform vec4 tint : source_color = vec4(1.0, 0.86, 0.58, 1.0);

void fragment() {
	vec2 p = UV * rect_size;
	float ph = 6.2831853 * t / period + phase0;
	float side = -cos(ph);                 // > 0: Strahl zeigt nach links
	float toward = sin(ph);                // > 0: zur Kamera
	vec2 d = p - lamp;
	float dist = length(d);
	// Keil nach links, leicht nach unten geneigt, Öffnung wächst mit der Entfernung
	float ang = atan(d.y, -d.x) - 0.04;
	float open = 0.035 + 0.05 * (1.0 - abs(side));
	float wedge = 1.0 - smoothstep(open * 0.55, open, abs(ang));
	wedge *= step(0.0, -d.x);
	float reach = 950.0 * max(side, 0.0);
	float fall = 1.0 - smoothstep(reach * 0.25, reach, dist);
	float beam = wedge * fall * max(side, 0.0) * 0.32;
	float flash = pow(max(toward, 0.0), 6.0);
	float halo = exp(-dist * dist / (2.0 * pow(5.0 + 15.0 * flash, 2.0))) * (0.35 + 0.55 * flash);
	vec3 c = tint.rgb * (beam + halo);
	COLOR = vec4(c, 1.0);
}
