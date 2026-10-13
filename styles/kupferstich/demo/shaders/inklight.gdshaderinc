// Gemeinsame Lichtlogik für Platte und Figur: Licht dünnt die gestochenen Linien aus, statt aufzuhellen.
// ink = Tuschedichte (0 Papier, 1 volle Farbe), ridge = weichgezeichnete Tusche (breite Linien hoch, feine niedrig).
// Mit wachsendem Licht L steigt die Schwelle auf dem Kammfeld: feine Linien verschwinden zuerst, breite werden dünner.
float thin_lines(float ink, float ridge, float L) {
	float thr = L * 1.05;
	float thinned = ink * smoothstep(thr, thr + 0.22, ridge);
	return mix(ink, thinned, clamp(L * 6.0, 0.0, 1.0));
}
