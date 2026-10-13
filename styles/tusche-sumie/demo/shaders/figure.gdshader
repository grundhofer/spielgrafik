// Figur, erster Durchgang: Papier in der Silhouette (A der Textur), per Bildschirmkoordinate aus demselben
// Reispapier wie der Hintergrund, damit die Figur nicht als Aufkleber auf dem Papier liegt und der Kai hinter
// dem Papierweiß der Figur (Hemd, Gesicht, Bauch) nicht durchscheint.
shader_type canvas_item;

uniform sampler2D paper : filter_linear;
uniform float breathe = 0.0;     // Stauchung um die Fußlinie (Atmen im Stehen)
uniform float foot_y = 0.0;      // Fußlinie in lokalen Pixeln
const float ALPHA_FLOOR = 21.0 / 255.0;   // Alpha ist ALPHA_FLOOR + Silhouette * (1 - ALPHA_FLOOR), siehe tools/inkutil.py

void vertex() {
	float k = (foot_y - VERTEX.y);
	VERTEX.y = foot_y - k * (1.0 + breathe);
}

void fragment() {
	vec3 p = texture(paper, SCREEN_UV).rgb;
	COLOR = vec4(p, clamp((COLOR.a - ALPHA_FLOOR) / (1.0 - ALPHA_FLOOR), 0.0, 1.0));
}
