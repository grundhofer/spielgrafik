shader_type canvas_item;
// Bildausgabe der Fantasy-Konsole: Der Bildspeicher (R8, 128x128) enthält je Pixel eine Farbnummer 0-15.
// Der Shader setzt nur die feste 16-Farben-Palette ein; andere Farben kann das Bild nicht enthalten.

const vec3 PAL[16] = vec3[16](
	vec3(0.0, 0.0, 0.0),                  // 0 schwarz        000000
	vec3(29.0, 43.0, 83.0) / 255.0,       // 1 dunkelblau     1d2b53
	vec3(126.0, 37.0, 83.0) / 255.0,      // 2 dunkelviolett  7e2553
	vec3(0.0, 135.0, 81.0) / 255.0,       // 3 dunkelgrün     008751
	vec3(171.0, 82.0, 54.0) / 255.0,      // 4 braun          ab5236
	vec3(95.0, 87.0, 79.0) / 255.0,       // 5 dunkelgrau     5f574f
	vec3(194.0, 195.0, 199.0) / 255.0,    // 6 hellgrau       c2c3c7
	vec3(255.0, 241.0, 232.0) / 255.0,    // 7 weiß           fff1e8
	vec3(255.0, 0.0, 77.0) / 255.0,       // 8 rot            ff004d
	vec3(255.0, 163.0, 0.0) / 255.0,      // 9 orange         ffa300
	vec3(255.0, 236.0, 39.0) / 255.0,     // 10 gelb          ffec27
	vec3(0.0, 228.0, 54.0) / 255.0,       // 11 grün          00e436
	vec3(41.0, 173.0, 255.0) / 255.0,     // 12 blau          29adff
	vec3(131.0, 118.0, 156.0) / 255.0,    // 13 lavendel      83769c
	vec3(255.0, 119.0, 168.0) / 255.0,    // 14 rosa          ff77a8
	vec3(255.0, 204.0, 170.0) / 255.0     // 15 pfirsich      ffccaa
);

void fragment() {
	int i = int(texelFetch(TEXTURE, ivec2(UV * vec2(textureSize(TEXTURE, 0))), 0).r * 255.0 + 0.5);
	COLOR = vec4(PAL[i & 15], 1.0);
}
