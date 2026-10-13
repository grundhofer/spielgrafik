// Pixelkonturen und Kantenlicht als Nachbearbeitung in Renderauflösung (1 Pixel = 1 Bildpunkt).
// Ein bildschirmfüllendes Rechteck vor der Kamera liest Tiefe, Normalen und Farbe der deckenden
// Geometrie und schreibt für jeden deckenden Pixel die Farbe neu:
//  - Kontur: Ein Nachbar liegt deutlich weiter hinten -> dieser Pixel ist die Außenkante des vorderen
//    Objekts und wird abgedunkelt (Linie liegt innerhalb der Silhouette, wie bei gezeichneten Sprites).
//    1/z ist auf einer Ebene im Bildraum linear; verglichen wird mit der Vorhersage aus Mitte und
//    Gegenseite, damit flach gesehene Böden keine Fehllinien bekommen.
//  - Kantenlicht: An konvexen Knicken (Normalen weichen ab, Tiefe stetig) wird der Pixel auf der
//    lichtzugewandten Seite aufgehellt.
//  - Gestufter Nebel nach Entfernung.
// Es zeichnet vor dem Wasser (render_priority), damit Linien an Unterwasser-Geometrie vom Wasser
// verdeckt werden.
shader_type spatial;
render_mode unshaded, blend_mix, depth_draw_never, depth_test_disabled, cull_disabled, fog_disabled, shadows_disabled;

#define P3D_NORMALS
#include "res://shaders/p3d_post.gdshaderinc"
