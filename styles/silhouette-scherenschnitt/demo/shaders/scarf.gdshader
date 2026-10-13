// Schalende: das starre Papierteil wird beim Abtasten zu einer laufenden Welle gebogen (zum Ende hin
// stärker), der Ansatz bleibt fest. Die Textur hat oben und unten Rand für die Auslenkung.
shader_type canvas_item;

uniform float t = 0.0;
uniform vec2 tex_size = vec2(100.0, 50.0);
uniform float root_x = 88.0;       // Ansatz in Texturpixeln (rechts)
uniform float amp = 2.5;
uniform float wavelength = 34.0;
uniform float speed = 9.0;
uniform float phase = 0.0;

void fragment() {
	vec2 p = UV * tex_size;
	float s = clamp((root_x - p.x) / root_x, 0.0, 1.0);
	float d = amp * s * s * sin((root_x - p.x) * 6.2831853 / wavelength - t * speed + phase);
	float a = texture(TEXTURE, (p - vec2(0.0, d)) / tex_size).a;
	COLOR = vec4(COLOR.rgb, COLOR.a * a);
}
