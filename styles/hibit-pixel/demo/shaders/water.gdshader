// Wasser: zeilenweiser Versatz um ganze Pixel (wie Rasterzeilen-Scroll), Glitzern und die Spiegelung des
// Leuchtfeuers als Säule aus kurzen Strichen. Alles auf dem 640×360-Raster.
// Deckend ist das Wasser nur dort, wo die Ebenenmaske (layers.png, Grün) an der unverschobenen Pixelposition
// Wasser zeigt: Inselchen und Fuß der Landzunge (Fernes) bleiben so sichtbar. Die zeilenweise Auffüllung in
// water.png dient nur als Quelle für die verschobenen Lesezugriffe.
shader_type canvas_item;
render_mode unshaded;

uniform float time = 0.0;
uniform float horizon = 173.0;      // erste Wasserzeile (main.gd setzt sie aus art/bg.json, aus der Maske)
uniform float near_row = 262.0;     // Wasser endet hinter dem Kai (ebenso aus art/bg.json)
uniform sampler2D layer_mask : filter_nearest;   // layers.png: R Himmel, G Wasser, B Fernes
uniform vec2 lamp = vec2(575.0, 88.0);
uniform float lamp_flash = 0.0;     // 0..1, wenn der Strahl zur Kamera zeigt
uniform vec3 tint : source_color = vec3(0.82, 0.8, 0.9);
uniform vec3 lamp_color : source_color = vec3(1.0, 0.86, 0.55);

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void fragment() {
	vec2 size = 1.0 / TEXTURE_PIXEL_SIZE;
	vec2 px = floor(UV * size);
	float water_here = step(0.5, texelFetch(layer_mask, ivec2(px), 0).g);
	float depth = clamp((px.y - horizon) / (near_row - horizon), 0.0, 1.0);
	// Versatz: ferne Zeilen ruhig, nahe Zeilen bis 3 px; Wellenlänge wächst mit der Nähe
	float amp = mix(0.4, 3.2, depth * depth);
	float w = sin(time * 1.3 + px.y * mix(1.9, 0.45, depth)) + 0.5 * sin(time * 2.1 - px.y * 0.83);
	float sh = floor(w * amp * 0.67 + 0.5);
	vec2 uv = (vec2(mod(px.x + sh, size.x), px.y) + 0.5) / size;
	vec4 c = texture(TEXTURE, uv);
	// Glitzern: einzelne Striche (2–4 px) blitzen kurz auf, dichter nahe dem Horizontlicht
	float seg = floor((px.x + sh) / 3.0);
	float hsh = hash(vec2(seg, px.y));
	float ph = fract(time * (0.35 + hsh * 0.5) + hsh * 7.0);
	float glint = step(0.93, hsh) * step(ph, 0.18) * (1.0 - depth * 0.6);
	c.rgb *= tint;
	c.rgb = mix(c.rgb, vec3(1.0, 0.82, 0.70), glint * 0.55);
	// Spiegelung des Leuchtfeuers: Säule unter der Lampe, Striche schwanken um ganze Pixel
	float row = px.y - horizon;
	float wob = floor(sin(time * 2.0 + px.y * 0.9) * (1.0 + depth * 2.5) + 0.5);
	float halfw = 1.0 + depth * 3.0;
	float dx = abs(px.x - (lamp.x + wob));
	float dash = step(0.35, fract(px.y * 0.37 + time * 0.6 + hash(vec2(px.y, 3.0)) * 0.3));
	float col = step(dx, halfw) * dash * (1.0 - smoothstep(0.0, 70.0, row));
	float refl = col * (0.18 + 0.7 * lamp_flash);
	c.rgb += lamp_color * refl;
	COLOR = vec4(c.rgb, c.a * water_here) * COLOR;
}
